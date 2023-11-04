from typing import Any
from datetime import datetime
from fastapi import Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import relationship
from app import Base, session, engine, app
from utils import template, sha512
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime
import random
import requests
from dataclasses import dataclass


# TODO: Change structure.

# Models
class User(Base):
    __tablename__ = "Users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True)
    password = Column(String)
    session = Column(String, unique=True)

    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password

    def __repr__(self):
        return "<User(id='%s', username='%s')>" % (self.id, self.username)


class TradeNode(Base):
    __tablename__ = "TradeServers"
    ticker = Column(String, primary_key=True, nullable=False, unique=True)
    active = Column(Boolean, nullable=False)
    trades = relationship('Trade', backref="trade_node")

    def __init__(self, ticker: str, active: bool = False):
        self.ticker = ticker
        self.active = active

    def start(self):
        ...

    def stop(self):
        ...


class Trade(Base):
    __tablename__ = "Trades"
    id = Column(Integer, primary_key=True)
    trade_server_id = Column(Integer, ForeignKey("TradeServers.ticker"))
    amount = Column(Integer)
    opening_price = Column(Integer, nullable=False)
    closing_price = Column(Integer)
    opened = Column(DateTime, default=datetime.now)
    closed = Column(DateTime)


class Config(Base):
    __tablename__ = "Config"
    id = Column(Integer, primary_key=True)
    currency = Column(String)

    def __init__(self, currency: str):
        self.currency = currency


Base.metadata.create_all(engine)

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
    user = session.query(User).filter_by(username=username, password=sha512(password)).first()

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
    print(currencies)
    config = session.query(Config).first()
    for currency, data in currencies.items():
        if config.currency == currency:
            data["selected"] = True
    print(currencies)
    broker = {
        "name": Broker.name,
        "working_hours": Broker.working_hours
    }
    page = template("dashboard.html").render(trade_servers=trade_servers, broker=broker, currencies=currencies)
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
    return {
        "trade_node_check": True,
        "internet_check": True,
        "broker_api_check": True
    }


@app.get("/healthcheck")
async def healthcheck_wrapper():
    return JSONResponse(healthcheck())
