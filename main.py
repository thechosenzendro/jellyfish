from fastapi import FastAPI
from typing import Any
from fastapi import Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from jellyserve.utils import template, sha512
from jellyserve.orm import ORM
import random
import requests
from dataclasses import dataclass


app = FastAPI()
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

if session.query(Config).first() is None:
    session.add(Config(currency="USD"))


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
    page = template("login.html").render()
    return HTMLResponse(page)


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
    response = await call_next(request)
    if "/dashboard" in str(request.url):
        session_token = request.cookies.get("session")
        if session_token:
            user = session.query(User).filter_by(session=session_token).first()
            if user is not None:
                return response
            else:
                return RedirectResponse(status_code=302, url="/")
        else:
            return RedirectResponse(status_code=302, url="/")
    else:
        return response


@app.get("/dashboard")
async def dashboard():
    trade_servers = session.query(TradeNode).all()
    currencies = requests.get("https://data.kurzy.cz/json/meny/b.json").json()["kurzy"]
    # TODO: Change this to a dict comprehension
    config = session.query(Config).first()
    for currency, data in currencies.items():
        if config.currency == currency:
            data["selected"] = True
    broker = {"name": Broker.name, "working_hours": Broker.working_hours}
    page = template("dashboard.html").render(
        trade_servers=trade_servers, broker=broker, currencies=currencies
    )
    return HTMLResponse(page)


@app.post("/logout")
async def logout(request: Request, response: Response):
    session_token = request.cookies.get("session")

    if session_token:
        user = session.query(User).filter_by(session=session_token).first()
        if user is not None:
            user.session = ""
            session.commit()
            response.delete_cookie("session")
        else:
            return {"error": f"No user with token {session_token}"}
    else:
        return {"error": "Empty token"}
    return RedirectResponse(status_code=302, url="/")


@app.post("/change_currency")
async def change_currency(request: Request):
    currency = (await request.form()).get("currency")
    session.query(Config).first().currency = currency
    session.commit()
    return RedirectResponse(status_code=302, url="/dashboard")


def healthcheck():
    # TODO: Do some actual checking
    return {"trade_node_check": True, "internet_check": True, "broker_api_check": True}


@app.get("/healthcheck")
async def healthcheck_wrapper():
    return JSONResponse(healthcheck())


@app.get("/view/{ticker}")
async def view(ticker: str):
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
        return HTMLResponse(template("statistics.html").render(statistics=statistics))
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
        statistics = template("statistics.html").render(statistics=statistics)
        print(statistics)
        return HTMLResponse(
            template("ticker.html").render(ticker=ticker, statistics=statistics)
        )
