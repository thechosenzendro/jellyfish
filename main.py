import random
import requests_cache
import yfinance
import asyncio
import pandas as pd

from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, WebSocket
from fastapi import Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse

from db import session
from models import User, TradeNode, Config
from jellyserve.utils import template, sha512

from result import Ok, Err, Result, is_ok, is_err
from datetime import datetime
from pprint import pprint

STATES = ["analyzing", "bought", "shorting", "noop"]

app = FastAPI()
req_session = requests_cache.CachedSession("db/cache")


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


@app.get("/")
async def index(request: Request):
    user_result = get_user(request)
    if is_ok(user_result):
        return RedirectResponse(status_code=302, url="/dashboard")
    return HTMLResponse(template("login.html"))


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
        response.set_cookie(key="session", value=token, httponly=True)

        return response
    else:
        return RedirectResponse(status_code=302, url="/")


@app.get("/dashboard")
async def dashboard(request: Request):
    # This would work so well as a macro! I am starting to get Elixir.
    user_result = get_user(request)
    if is_err(user_result):
        return user_result.err_value
    user: User = user_result.ok_value

    trade_servers = session.query(TradeNode).all()
    currencies = req_session.get("https://data.kurzy.cz/json/meny/b.json").json()[
        "kurzy"
    ]

    currencies[user.config.currency]["selected"] = True
    broker = {"name": Broker.name, "working_hours": Broker.working_hours}

    page = template(
        "dashboard.html",
        trade_servers=trade_servers,
        broker=broker,
        currencies=currencies,
    )
    return HTMLResponse(page)


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


def healthcheck() -> dict:
    # TODO: Do some actual checking
    return {"trade_node_check": True, "broker_api_check": True}


@app.get("/healthcheck")
async def healthcheck_wrapper(request: Request):
    user_result = get_user(request)
    if is_err(user_result):
        return user_result.err_value
    user: User = user_result.ok_value

    return JSONResponse(healthcheck())


@app.get("/view/{ticker}")
async def view(ticker: str, request: Request):
    user_result = get_user(request)
    if is_err(user_result):
        return user_result.err_value

    if ticker == "statistics":
        statistics = {
            "Denní": {
                "number_of_trades": 27,
                "expenditure": "1000 CZK",
                "revenue": "10000 CZK",
                "fee": "10 CZK",
                "profit": "8990 CZK",
                "profit_factor": 1,
            },
            "Týdenní": {
                "number_of_trades": 27,
                "expenditure": "1000 CZK",
                "revenue": "10000 CZK",
                "fee": "10 CZK",
                "profit": "8990 CZK",
                "profit_factor": 1,
            },
            "Měsíční": {
                "number_of_trades": 27,
                "expenditure": "1000 CZK",
                "revenue": "10000 CZK",
                "fee": "10 CZK",
                "profit": "8990 CZK",
                "profit_factor": 1,
            },
            "Roční": {
                "number_of_trades": 27,
                "expenditure": "1000 CZK",
                "revenue": "10000 CZK",
                "fee": "10 CZK",
                "profit": "8990 CZK",
                "profit_factor": 1,
            },
        }
        return HTMLResponse(template("statistics.html", statistics=statistics))
    else:
        statistics = {
            "Denní": {
                "number_of_trades": 27,
                "expenditure": "1000 CZK",
                "revenue": "10000 CZK",
                "fee": "10 CZK",
                "profit": "8990 CZK",
                "profit_factor": 1,
            },
            "Týdenní": {
                "number_of_trades": 27,
                "expenditure": "1000 CZK",
                "revenue": "10000 CZK",
                "fee": "10 CZK",
                "profit": "8990 CZK",
                "profit_factor": 1,
            },
            "Měsíční": {
                "number_of_trades": 27,
                "expenditure": "1000 CZK",
                "revenue": "10000 CZK",
                "fee": "10 CZK",
                "profit": "8990 CZK",
                "profit_factor": 1,
            },
            "Roční": {
                "number_of_trades": 27,
                "expenditure": "1000 CZK",
                "revenue": "10000 CZK",
                "fee": "10 CZK",
                "profit": "8990 CZK",
                "profit_factor": 1,
            },
            "Desetiletý": {
                "number_of_trades": 27,
                "expenditure": "1000 CZK",
                "revenue": "10000 CZK",
                "fee": "10 CZK",
                "profit": "8990 CZK",
                "profit_factor": 1,
            },
        }
        statistics = template("statistics.html", statistics=statistics)
        return HTMLResponse(
            template("ticker.html", ticker=ticker, statistics=statistics)
        )


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


@app.websocket("/sync")
async def sync(websocket: WebSocket):
    await websocket.accept()

    user_result = get_user(websocket)
    if is_err(user_result):
        return user_result.err_value
    user: User = user_result.ok_value

    sync_socket.add_connection(user, websocket)
    try:
        while True:
            request: dict = await websocket.receive_json()
            response = {}

            if request["action"] == "graph_sync":
                stock_data = yfinance.Ticker(request["ticker"]).history(
                    period=request["sync_time"]
                )

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

            await websocket.send_json(response)
    except:
        sync_socket.remove_connection(user)


async def ping():
    while True:
        try:
            tickers = ["AAPL", "MSFT"]
            ticker = tickers[random.randint(0, 1)]
            state = STATES[random.randint(0, len(STATES) - 1)]
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

        except:
            pass
        await asyncio.sleep(1)


asyncio.ensure_future(ping())
