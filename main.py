from multiprocessing import Process
from pprint import pprint
import random
from numpy import broadcast
import requests_cache
import yfinance
import asyncio
import pandas as pd

from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, WebSocket
from fastapi import Request, Response
from fastapi.responses import RedirectResponse, JSONResponse
from contextlib import asynccontextmanager

from db import orm, session

from jellyserve.utils import sha512
from jellyserve.components import Component, Template

from result import Ok, Err, Result, is_ok, is_err
from datetime import datetime
from trading import Broker


class SyncConnectionManager:
    def __init__(self) -> None:
        self.active_connections: dict[User, WebSocket | None] = {}

    def add_connection(self, user: User, websocket: WebSocket):
        self.active_connections[user] = websocket

    def remove_connection(self, user: User):
        self.active_connections[user] = None

    async def send_json(self, _dict: dict, user: User):
        await self.active_connections[user].send_json(_dict)

    async def broadcast_json(self, _dict: dict):
        print(f"Broadcasting {_dict} to {self.active_connections} with id {id(self)}")
        for connection in self.active_connections.values():
            await connection.send_json(_dict)


sync_socket = SyncConnectionManager()


async def start_day():
    trade_node = session.query(TradeNode).filter_by(ticker="AAPL").first()
    trade_node.active = True
    session.commit()

    process = Process(target=trade_node.start)
    try:
        process.start()
    except KeyboardInterrupt:
        process.kill()


async def _start_day():
    print("Starting Jellyfish!")
    BUDGET = 1000

    trade_node_budget = (
        BUDGET * (session.query(Settings).first().allocation_of_funds / 100) / 10
    )

    potentional_gainers = pd.read_html("https://finance.yahoo.com/gainers")[0]
    gainers: list[TradeNode] = []

    for _, gainer in potentional_gainers.iterrows():
        price = gainer["Price (Intraday)"]
        ticker = gainer["Symbol"]

        if price > trade_node_budget:
            continue
        if not Broker.is_available(ticker):
            continue
        if len(gainers) == 5:
            break

        print(ticker, price)
        gainers.append(TradeNode(ticker=ticker, active=True))

    potentional_losers = pd.read_html("https://finance.yahoo.com/losers")[0]
    losers: list[TradeNode] = []

    for _, loser in potentional_losers.iterrows():
        price = loser["Price (Intraday)"]
        ticker = loser["Symbol"]

        if price > trade_node_budget:
            continue
        if not Broker.is_available(ticker):
            continue
        if len(losers) == 5:
            break

        print(ticker, price)
        losers.append(TradeNode(ticker=ticker, active=True))

    for gainer, loser in zip(gainers, losers):
        existing_gainer = (
            session.query(TradeNode).filter_by(ticker=gainer.ticker).first()
        )
        if not existing_gainer:
            session.add(gainer)
        else:
            existing_gainer.active = True
        gainer_process = Process(target=gainer.start)
        try:
            gainer_process.start()
        except KeyboardInterrupt:
            gainer_process.kill()

        existing_loser = session.query(TradeNode).filter_by(ticker=loser.ticker).first()
        if not existing_loser:
            session.add(loser)
        else:
            existing_loser.active = True

        loser_process = Process(target=loser.start)
        try:
            loser_process.start()
        except KeyboardInterrupt:
            loser_process.kill()
    session.commit()


async def end_day():
    print("Stopping Jellyfish!")
    for trade_node in session.query(TradeNode).filter_by(active=True).all():
        await trade_node.stop()
        trade_node.active = False
    session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await start_day()
    yield
    await end_day()


app = FastAPI(lifespan=lifespan)
req_session = requests_cache.CachedSession("dev")

STATES = ["analyzing", "bought", "shorting", "noop"]

# Routes
app.mount("/static", StaticFiles(directory="static"), name="static")


def get_user(request: Request | WebSocket) -> Result[User, RedirectResponse]:
    session_token = request.cookies.get("session")
    if not session_token:
        return Err(RedirectResponse(status_code=302, url="/"))

    user = session.query(User).filter_by(session=session_token).first()
    if user is None:
        return Err(RedirectResponse(status_code=302, url="/"))

    return Ok(user)


class LoginPage(Component):
    template: Template = Template("templates/login.jinja")


@app.get("/")
async def index(request: Request):
    user_result = get_user(request)
    if is_ok(user_result):
        return RedirectResponse(status_code=302, url="/dashboard")

    return LoginPage().html()


@app.post("/login")
async def login(request: Request):
    form_data = await request.form()
    username, password = form_data["username"], form_data["password"]
    user = (
        session.query(User)
        .filter_by(username=username, password=sha512(password))
        .first()
    )

    if user is not None:
        token = sha512(
            str(random.randint(0, 100000))
            + user.username
            + str(random.randint(0, 100000))
        )

        user.session = token
        session.commit()

        response = RedirectResponse(status_code=302, url="/dashboard")
        response.set_cookie(key="session", value=token, httponly=False)

        return response
    else:
        return RedirectResponse(status_code=302, url="/")


from typing import Any, List, Dict


class Dashboard(Component):
    trade_nodes: List[TradeNode]
    broker: Dict[str, str]
    currencies: Dict[str, Any]
    status_bar: Dict[str, str]

    template: Template = Template("templates/dashboard/dashboard.jinja")


@app.get("/dashboard")
async def dashboard(request: Request):
    # This would work so well as a macro! I am starting to get Elixir.
    user_result = get_user(request)
    if is_err(user_result):
        return user_result.err_value
    user: User = user_result.ok_value

    trade_nodes = session.query(TradeNode).all()
    currencies = req_session.get("https://data.kurzy.cz/json/meny/b.json").json()[
        "kurzy"
    ]
    currencies[user.config.currency]["selected"] = True
    broker = {
        "name": Broker.name,
        "working_hours": Broker.working_hours,
    }

    status_bar = {
        "balance": "xxxxxx$",
        "equity": "xxxxxx$",
        "margin": "xxxxxx$",
        "free_margin": "xxxxxx$",
        "level": "xxxxxx$",
    }

    return Dashboard(
        trade_nodes=trade_nodes,
        broker=broker,
        currencies=currencies,
        status_bar=status_bar,
    ).html()


@app.post("/logout")
async def logout(request: Request):
    user_result = get_user(request)
    if is_err(user_result):
        return user_result.err_value
    user: User = user_result.ok_value

    user.session = ""
    session.commit()

    response = RedirectResponse(status_code=302, url="/")
    response.delete_cookie("session")
    return response


@app.post("/change_currency")
async def change_currency(request: Request):
    user_result = get_user(request)
    if is_err(user_result):
        return user_result.err_value
    user: User = user_result.ok_value

    currency = (await request.form()).get("currency")
    user.config.currency = currency
    session.commit()
    return RedirectResponse(status_code=302, url="/dashboard")


async def healthcheck() -> dict:
    # TODO: Do some actual checking
    randint = random.randint(0, 10)
    if randint == 6:
        return {"trade_node_check": False, "broker_api_check": True}
    if randint == 4:
        return {"trade_node_check": True, "broker_api_check": False}
    return {"trade_node_check": True, "broker_api_check": True}


@app.get("/healthcheck")
async def healthcheck_wrapper(request: Request):
    user_result = get_user(request)
    if is_err(user_result):
        return user_result.err_value
    user: User = user_result.ok_value

    return JSONResponse(await healthcheck())


class Statistics(Component):
    statistics: List[Dict[str, str | int]]
    ticker: str

    template: Template = Template("templates/statistics.jinja")


class Ticker(Component):
    statistics: str
    ticker: str

    template: Template = Template("templates/ticker.jinja")


@app.get("/view/{ticker}")
async def view(ticker: str, request: Request):
    user_result = get_user(request)
    if is_err(user_result):
        return user_result.err_value
    statistics = [
        {
            "name": "Aktuální",
            "id": "now",
            "number_of_trades": 27,
            "expenditure": "1000 CZK",
            "revenue": "10000 CZK",
            "fee": "10 CZK",
            "profit": "8990 CZK",
            "profit_factor": 1,
        },
        {
            "name": "Denní",
            "id": "daily",
            "number_of_trades": 27,
            "expenditure": "1000 CZK",
            "revenue": "10000 CZK",
            "fee": "10 CZK",
            "profit": "8990 CZK",
            "profit_factor": 1,
        },
        {
            "name": "Týdenní",
            "id": "weekly",
            "number_of_trades": 27,
            "expenditure": "1000 CZK",
            "revenue": "10000 CZK",
            "fee": "10 CZK",
            "profit": "8990 CZK",
            "profit_factor": 1,
        },
        {
            "name": "Měsíční",
            "id": "monthly",
            "number_of_trades": 27,
            "expenditure": "1000 CZK",
            "revenue": "10000 CZK",
            "fee": "10 CZK",
            "profit": "8990 CZK",
            "profit_factor": 1,
        },
        {
            "name": "Roční",
            "id": "yearly",
            "number_of_trades": 27,
            "expenditure": "1000 CZK",
            "revenue": "10000 CZK",
            "fee": "10 CZK",
            "profit": "8990 CZK",
            "profit_factor": 1,
        },
    ]

    if ticker == "statistics":
        return Statistics(statistics=statistics, ticker="global").html()
    else:
        statistics = Statistics(statistics=statistics, ticker=ticker).raw()
        return Ticker(ticker=ticker, statistics=statistics).html()


class SettingsComponent(Component):
    allocation_of_funds: int
    groups: int
    prices_in_groups: int
    compliance: int
    template: Template = Template("templates/dashboard/settings.jinja")


@app.get("/settings")
async def get_settings():
    settings = session.query(Settings).first()
    return SettingsComponent(**vars(settings)).html()


@app.post("/settings")
async def post_settings(request: Request):
    form_data = await request.form()
    settings = session.query(Settings).first()
    settings.allocation_of_funds = form_data["allocation_of_funds"]
    settings.groups = form_data["groups"]
    settings.prices_in_groups = form_data["prices_in_groups"]
    settings.compliance = form_data["compliance"]
    session.commit()

    return RedirectResponse("/dashboard", 302)


class SyncHandler:
    @staticmethod
    def graph_sync(user: User, req: dict) -> list[dict]:
        stock_data = yfinance.Ticker(req["ticker"]).history(period=req["sync_time"])

        timestamps = pd.to_datetime(stock_data.index)
        prices = stock_data["Close"]

        response = [
            {
                "timestamp": timestamp.strftime("%H:%M:%S"),
                "price": price,
                "state": STATES[random.randint(0, len(STATES) - 1)],
            }
            for timestamp, price in zip(timestamps, prices)
        ]
        return response

    def stop_trading(user: User, req: dict) -> list[dict]:
        return {"result": "ok"}

    def start_trading(user: User, req: dict) -> list[dict]:
        return {"result": "ok"}


broadcast_state = sync_socket.sync_socket.broadcast_json


@app.websocket("/sync")
async def sync(websocket: WebSocket):
    user_result = get_user(websocket)

    if is_ok(user_result):
        await websocket.accept()
    else:
        return 1
    user: User = user_result.ok_value

    sync_socket.sync_socket.add_connection(user, websocket)
    try:
        while True:
            request: dict = await websocket.receive_json()
            action = request.get("action", "no_action")
            if hasattr(SyncHandler, action):
                await websocket.send_json(
                    {
                        "action": action,
                        "data": getattr(SyncHandler, request["action"])(user, request),
                    }
                )
            else:
                await websocket.send_json({"error": "No such action"})
    except:
        sync_socket.sync_socket.remove_connection(user)


async def sync_test():
    def get_random(_list: list):
        return _list[random.randint(0, len(_list) - 1)]

    tickers = [
        trade_node.ticker
        for trade_node in session.query(TradeNode).all()
        if trade_node.active
    ]
    tickers.append("global")
    status_bar_keys = [
        "balance",
        "equity",
        "margin",
        "free_margin",
        "level",
    ]
    while True:
        try:
            # Sending new status bar data
            await sync_socket.sync_socket.broadcast_json(
                {
                    "action": "update_status_bar",
                    "key": get_random(status_bar_keys),
                    "value": str(random.randint(0, 1000)) + "$",
                }
            )
            ids = ["now", "daily", "weekly", "monthly", "yearly"]
            keys = [
                "number_of_trades",
                "expenditure",
                "revenue",
                "fee",
                "profit",
                "profit_factor",
            ]

            # Sending new statistic data
            await sync_socket.sync_socket.broadcast_json(
                {
                    "action": "update_statistics",
                    "ticker": get_random(tickers),
                    "stat_id": get_random(ids),
                    "key": get_random(keys),
                    "value": random.randint(0, 1000),
                }
            )
        except:
            pass
        await asyncio.sleep(1)


asyncio.ensure_future(sync_test())

from sqlalchemy.orm import relationship
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime
from trading import TradeState, PriceFeed, AnalysisResult, Broker
from result import Result, Ok, Err, is_ok, is_err


class User(orm.Base):
    __tablename__ = "Users"
    id = Column(Integer, autoincrement=True, primary_key=True)
    username = Column(String, unique=True)
    password = Column(String)
    session = Column(String, unique=True)
    config = relationship("Config", backref="user", uselist=False)

    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password

    def __repr__(self):
        return "<User(id='%s', username='%s')>" % (self.id, self.username)


class TradeNode(orm.Base):
    __tablename__ = "TradeNodes"
    ticker = Column(String, primary_key=True, nullable=False, unique=True)
    active = Column(Boolean, nullable=False)
    trades = relationship("Trade", backref="trade_node")

    def __init__(self, ticker: str, active: bool = False):
        self.ticker = ticker
        self.active = active

    def _analyze(self, groups: list[list[int]]):
        comparison_results = []
        for group in groups:
            comparison_results.append(
                [group[i] > group[i - 1] for i in range(1, len(group))]
            )

        res = [
            sum(group) >= session.query(Settings).first().compliance
            for group in comparison_results
        ]

        if not False in res:
            return AnalysisResult.GOING_UP

        res = [
            not len(group) - sum(group) >= session.query(Settings).first().compliance
            for group in comparison_results
        ]
        if not False in res:
            return AnalysisResult.GOING_DOWN
        else:
            return AnalysisResult.INSUFFICIENT

    def start(self):
        asyncio.run(self.trade())

    async def trade(self):
        self.state = TradeState.DEFAULT

        # TODO: Make this not horrible

        group = []
        groups = []
        for price in PriceFeed(self.ticker):
            if not self.active:
                break

            # Accumulating the values
            if len(group) == session.query(Settings).first().prices_in_groups:
                groups.append(group)
                group = []
            else:
                group.append(price)
                continue
            if not len(groups) == session.query(Settings).first().groups:
                group.append(price)
                continue

            print("Doing an action!")

            analysis_result = self._analyze(groups)

            group.clear()
            groups.clear()
            BUDGET = 1000
            budget = (
                BUDGET
                * (session.query(Settings).first().allocation_of_funds / 100)
                / 10
            )

            amount = int(budget / price)
            if self.state == TradeState.BOUGHT:
                if analysis_result == AnalysisResult.GOING_UP:
                    # Send "bought" to frontend

                    await sync_socket.broadcast_json(
                        {
                            "action": "update_graph",
                            "ticker": self.ticker,
                            "timestamp": datetime.now().strftime("%H:%M:%S"),
                            "price": price,
                            "state": "bought",
                        }
                    )

                elif analysis_result == AnalysisResult.GOING_DOWN:
                    # Send "analyzing" to frontend
                    Broker.sell(self.ticker)
                    self.state = TradeState.DEFAULT

                    await sync_socket.broadcast_json(
                        {
                            "action": "update_graph",
                            "ticker": self.ticker,
                            "timestamp": datetime.now().strftime("%H:%M:%S"),
                            "price": price,
                            "state": "analyzing",
                        }
                    )

                elif analysis_result == AnalysisResult.INSUFFICIENT:
                    # Send "bought" to frontend

                    await sync_socket.broadcast_json(
                        {
                            "action": "update_graph",
                            "ticker": self.ticker,
                            "timestamp": datetime.now().strftime("%H:%M:%S"),
                            "price": price,
                            "state": "bought",
                        }
                    )

            elif self.state == TradeState.DEFAULT:
                if analysis_result == AnalysisResult.GOING_UP:
                    # Send "bought" to frontend
                    Broker.buy(self.ticker, amount)
                    self.state = TradeState.BOUGHT

                    await sync_socket.broadcast_json(
                        {
                            "action": "update_graph",
                            "ticker": self.ticker,
                            "timestamp": datetime.now().strftime("%H:%M:%S"),
                            "price": price,
                            "state": "bought",
                        }
                    )

                elif analysis_result == AnalysisResult.GOING_DOWN:
                    # Send "shorting" to frontend
                    Broker.sell(self.ticker)
                    self.state = TradeState.SHORTING

                    await sync_socket.broadcast_json(
                        {
                            "action": "update_graph",
                            "ticker": self.ticker,
                            "timestamp": datetime.now().strftime("%H:%M:%S"),
                            "price": price,
                            "state": "shorting",
                        }
                    )

                elif analysis_result == AnalysisResult.INSUFFICIENT:
                    # Send "analyzing" to frontend

                    await sync_socket.broadcast_json(
                        {
                            "action": "update_graph",
                            "ticker": self.ticker,
                            "timestamp": datetime.now().strftime("%H:%M:%S"),
                            "price": price,
                            "state": "analyzing",
                        }
                    )

            elif self.state == TradeState.SHORTING:
                if analysis_result == AnalysisResult.GOING_UP:
                    # Send "analyzing" to frontend
                    Broker.buy(self.ticker, amount)
                    self.state = TradeState.DEFAULT

                    await sync_socket.broadcast_json(
                        {
                            "action": "update_graph",
                            "ticker": self.ticker,
                            "timestamp": datetime.now().strftime("%H:%M:%S"),
                            "price": price,
                            "state": "analyzing",
                        }
                    )

                elif analysis_result == AnalysisResult.GOING_DOWN:
                    # Send "shorting" to frontend

                    await sync_socket.broadcast_json(
                        {
                            "action": "update_graph",
                            "ticker": self.ticker,
                            "timestamp": datetime.now().strftime("%H:%M:%S"),
                            "price": price,
                            "state": "shorting",
                        }
                    )

                elif analysis_result == AnalysisResult.INSUFFICIENT:
                    # Send "shorting" to frontend

                    await sync_socket.broadcast_json(
                        {
                            "action": "update_graph",
                            "ticker": self.ticker,
                            "timestamp": datetime.now().strftime("%H:%M:%S"),
                            "price": price,
                            "state": "shorting",
                        }
                    )

    async def stop(self): ...


class Trade(orm.Base):
    __tablename__ = "Trades"
    id = Column(Integer, primary_key=True)
    trade_server_id = Column(Integer, ForeignKey("TradeNodes.ticker"))
    amount = Column(Integer)
    opening_price = Column(Integer, nullable=False)
    closing_price = Column(Integer)
    opened = Column(DateTime, default=datetime.now)
    closed = Column(DateTime)


class Config(orm.Base):
    __tablename__ = "Configs"
    id = Column(Integer, autoincrement=True, primary_key=True)
    currency = Column(String)
    user_id = Column(Integer, ForeignKey("Users.id"))

    def __init__(self, currency: str):
        self.currency = currency


class Settings(orm.Base):
    __tablename__ = "Settings"
    id = Column(Integer, autoincrement=True, primary_key=True)

    allocation_of_funds = Column(Integer, nullable=False)
    groups = Column(Integer, nullable=False)
    prices_in_groups = Column(Integer, nullable=False)
    compliance = Column(Integer, nullable=False)

    def __init__(
        self,
        allocation_of_funds: int,
        groups: int,
        prices_in_groups: int,
        compliance: int,
    ):
        self.allocation_of_funds = allocation_of_funds
        self.groups = groups
        self.prices_in_groups = prices_in_groups
        self.compliance = compliance
