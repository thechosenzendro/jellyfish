from ast import Pass
from fastapi import FastAPI
from typing import Any
from fastapi import Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi import APIRouter
from jellyserve.utils import template, sha512
from jellyserve.orm import ORM
from jellyserve.auth import AuthenticatedRequest
from inspect import signature
import random
import requests
import yfinance
from dataclasses import dataclass
from fastapi.staticfiles import StaticFiles

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

orm = ORM()
session = orm.session

from models import User, TradeNode, Config


# Create default admin
if session.query(User).filter_by(username="admin").first() is None:
    session.add(User(username="admin", password=sha512("admin")))
    session.commit()

# Create test TradeServer
if session.query(TradeNode).filter_by(ticker="AAPL").first() is None:
    session.add(TradeNode(ticker="AAPL", active=True))
    session.commit()

# TODO: Make the config dependent on the user


@dataclass
class Result:
    is_ok: bool
    value: Any


# Broker API


class Broker:
    name: str = "Broker"
    working_hours: str = "8:00 - 18:00"

    @staticmethod
    def is_available(ticker: str) -> Result:
        ...

    @staticmethod
    def sell(ticker: str) -> Result:
        ...

    @staticmethod
    def buy(ticker: str, amount: int) -> Result:
        ...


# Routes


@app.get("/")
async def index():
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
        token = sha512(random.randint(0, 100000))
        user.session = token
        session.commit()

        response = RedirectResponse(status_code=302, url="/dashboard")
        response.set_cookie(key="session", value=token, httponly=True)
        return response
    else:
        return RedirectResponse(status_code=302, url="/")


@app.middleware("http")
async def is_logged_in(request: Request, call_next):
    def get_matching_route(request: Request):
        import starlette.routing as routing

        for route in app.routes:
            _match, _ = route.matches(request)
            if _match is not routing.Match.NONE:
                return route

    matched_route = get_matching_route(request)
    if not matched_route:
        return HTMLResponse(status_code=404, content="Not found.")
    if not hasattr(matched_route, "endpoint"):
        response = await call_next(request)
        return response

    route_handler = matched_route.endpoint
    if hasattr(route_handler, "__wrapped__"):
        route_handler = route_handler.__wrapped__

    sig = signature(route_handler)
    if not (
        sig.parameters.get("request", False)
        and sig.parameters["request"].annotation == AuthenticatedRequest
    ):
        response = await call_next(request)
        return response

    session_token = request.cookies.get("session")
    if not session_token:
        return RedirectResponse(status_code=302, url="/")

    user = session.query(User).filter_by(session=session_token).first()
    if user is None:
        return RedirectResponse(status_code=302, url="/")

    request.state.user = user
    response = await call_next(request)
    return response


@app.get("/dashboard")
async def dashboard(request: AuthenticatedRequest):
    trade_servers = session.query(TradeNode).all()
    currencies = requests.get("https://data.kurzy.cz/json/meny/b.json").json()["kurzy"]
    config = session.query(Config).first()

    currencies[config.currency]["selected"] = True
    broker = {"name": Broker.name, "working_hours": Broker.working_hours}

    page = template(
        "dashboard.html",
        trade_servers=trade_servers,
        broker=broker,
        currencies=currencies,
    )
    return HTMLResponse(page)


@app.post("/logout")
async def logout(request: AuthenticatedRequest):
    user: User = request.state.user
    user.session = ""
    session.commit()

    response = RedirectResponse(status_code=302, url="/")
    response.delete_cookie("session")
    return response


@app.post("/change_currency")
async def change_currency(request: AuthenticatedRequest):
    currency = (await request.form()).get("currency")
    session.query(Config).first().currency = currency
    session.commit()
    return RedirectResponse(status_code=302, url="/dashboard")


def healthcheck():
    # TODO: Do some actual checking
    return {"trade_node_check": True, "internet_check": True, "broker_api_check": True}


@app.get("/healthcheck")
async def healthcheck_wrapper(request: AuthenticatedRequest):
    return JSONResponse(healthcheck())


@app.get("/view/{ticker}")
async def view(ticker: str, request: AuthenticatedRequest):
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


sync_router = APIRouter(prefix="/sync")


@sync_router.get("/graph/{ticker}/{sync_time}")
async def update_graph(ticker: str, sync_time: str):
    states = ["analyzing", "bought", "shorting", "noop"]
    graph_data = []

    stock_data = yfinance.Ticker(ticker).history(period=sync_time)

    timestamps = stock_data.index
    prices = stock_data["Close"]

    print(timestamps, prices)

    for timestamp, price in zip(timestamps, prices):
        state = states[random.randint(0, len(states) - 1)]
        graph_data.append(
            {
                "timestamp": str(timestamp),
                "price": price,
                "state": state,
            }
        )
    return JSONResponse(graph_data)


app.include_router(sync_router)
