from main import orm
from datetime import datetime
from sqlalchemy.orm import relationship
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime


class User(orm.Base):
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


class TradeNode(orm.Base):
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


class Trade(orm.Base):
    __tablename__ = "Trades"
    id = Column(Integer, primary_key=True)
    trade_server_id = Column(Integer, ForeignKey("TradeServers.ticker"))
    amount = Column(Integer)
    opening_price = Column(Integer, nullable=False)
    closing_price = Column(Integer)
    opened = Column(DateTime, default=datetime.now)
    closed = Column(DateTime)


class Config(orm.Base):
    __tablename__ = "Config"
    id = Column(Integer, primary_key=True)
    currency = Column(String)

    def __init__(self, currency: str):
        self.currency = currency


orm.migrate()