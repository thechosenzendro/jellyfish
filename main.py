from pprint import pprint
import random
import requests_cache
import yfinance
import asyncio
import pandas as pd

from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, WebSocket
from fastapi import Request, Response
from fastapi.responses import RedirectResponse, JSONResponse

from db import session
from models import User, TradeNode, Config

from jellyserve.utils import sha512
from jellyserve.components import Component, Template

from result import Ok, Err, Result, is_ok, is_err
from datetime import datetime


app = FastAPI()
req_session = requests_cache.CachedSession("dev")

STATES = ["analyzing", "bought", "shorting", "noop"]


# Broker API
class Broker:
    name: str = "Broker"
    working_hours: str = "8:00 - 18:00"

    @staticmethod
    def is_available(ticker: str):
        ...

    @staticmethod
    def sell(ticker: str):
        ...

    @staticmethod
    def buy(ticker: str, amount: int):
        ...


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

    template: Template = Template("templates/dashboard.jinja")


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
    print(randint)
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
        for connection in self.active_connections.values():
            await connection.send_json(_dict)


sync_socket = SyncConnectionManager()


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
        try:
            # Sending new ticker data
            ticker = get_random(tickers)
            state = get_random(STATES)
            now = datetime.now()

            await sync_socket.broadcast_json(
                {
                    "action": "update_graph",
                    "ticker": ticker,
                    "timestamp": now.strftime("%H:%M:%S"),
                    "price": random.randint(0, 200),
                    "state": state,
                }
            )
            print("Sending new graph data!")
            # Sending new status bar data
            await sync_socket.broadcast_json(
                {
                    "action": "update_status_bar",
                    "key": get_random(status_bar_keys),
                    "value": str(random.randint(0, 1000)) + "$",
                }
            )
            print("Sending new status bar data!")

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
            print("Sending new statistics!")
        except:
            pass
        await asyncio.sleep(1)


asyncio.ensure_future(sync_test())
