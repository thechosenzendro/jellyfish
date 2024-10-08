import asyncio
import random
from contextlib import asynccontextmanager
from multiprocessing import Process, Queue

import pandas as pd
import requests_cache
import yfinance
from fastapi import FastAPI, WebSocket
from fastapi import Request
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from result import Result, Ok, Err, is_ok, is_err

from db import session
from jellyserve.components import Component, Template
from jellyserve.utils import sha512
from models import User, TradeNode, Settings
from trading import Broker


class SyncConnectionManager:
    def __init__(self) -> None:
        self.active_connections: dict[User, WebSocket | None] = {}

    def add_connection(self, user: User, websocket: WebSocket):
        self.active_connections[user] = websocket

    def remove_connection(self, user: User):
        del self.active_connections[user]

    async def send_json(self, _dict: dict, user: User):
        await self.active_connections[user].send_json(_dict)

    async def broadcast_json(self, _dict: dict):
        for connection in self.active_connections.values():
            await connection.send_json(_dict)


sync_socket = SyncConnectionManager()
_sync_queue = Queue()


async def start_day():
    trade_node = session.query(TradeNode).filter_by(ticker="AAPL").first()
    trade_node.active = True
    session.commit()

    process = Process(target=trade_node.start, args=(_sync_queue,))
    try:
        print(f"Starting process {process}")
        process.start()
    except KeyboardInterrupt:
        process.kill()


async def _start_day():
    print("Starting Jellyfish!")
    budget = 1000

    trade_node_budget = (
        budget * (session.query(Settings).first().allocation_of_funds / 100) / 10
    )

    potential_gainers = pd.read_html("https://finance.yahoo.com/gainers")[0]
    gainers: list[TradeNode] = []

    for _, gainer in potential_gainers.iterrows():
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

    potential_losers = pd.read_html("https://finance.yahoo.com/losers")[0]
    losers: list[TradeNode] = []

    for _, loser in potential_losers.iterrows():
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
async def lifespan(_app: FastAPI):
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


from typing import Any, List, Dict, Literal


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
    _user: User = user_result.ok_value

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
    def graph_sync(_user: User, req: dict) -> list[dict]:
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

    @staticmethod
    def stop_trading(_user: User, _req: dict) -> dict[Literal["result"], str]:
        return {"result": "ok"}

    @staticmethod
    def start_trading(_user: User, _req: dict) -> dict[Literal["result"], str]:
        return {"result": "ok"}


@app.websocket("/sync")
async def sync(websocket: WebSocket):
    user_result = get_user(websocket)

    if is_ok(user_result):
        await websocket.accept()
    else:
        return 1
    user: User = user_result.ok_value

    sync_socket.add_connection(user, websocket)
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
        sync_socket.remove_connection(user)


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
        if not _sync_queue.empty():
            value = _sync_queue.get()
            await sync_socket.broadcast_json(value)
        try:
            # Sending new status bar data
            await sync_socket.broadcast_json(
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
            await sync_socket.broadcast_json(
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
        await asyncio.sleep(0.1)


asyncio.ensure_future(sync_test())
