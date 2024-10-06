import asyncio
import random
from datetime import datetime
from multiprocessing import Queue
from typing import Iterator, Literal

from sqlalchemy import Column, Float, Integer, String, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship

from db import orm, session
from trading import Brokerage
from trading import TradeState, AnalysisResult


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


class BiggerThan: ...


class SmallerThan: ...


class Equals: ...


class TradeNode(orm.Base):
    __tablename__ = "TradeNodes"
    ticker = Column(String, primary_key=True, nullable=False, unique=True)
    active = Column(Boolean, nullable=False)
    trades = relationship("Trade", backref="trade_node")

    def __init__(self, ticker: str, active: bool = False):
        self.state = TradeState.DEFAULT
        self.ticker = ticker
        self.active = active
    @staticmethod
    def _analyze(groups: list[list[float]]) -> AnalysisResult:
        comparison_results = []
        for group in groups:
            comparison_results.append(
                [
                    (
                        BiggerThan
                        if group[i] > group[i - 1]
                        else SmallerThan if group[i] < group[i - 1] else Equals
                    )
                    for i in range(1, len(group))
                ]
            )

        res = []
        for group in comparison_results:
            up_occurrences = len([e for e in group if e == BiggerThan])
            down_occurrences = len([e for e in group if e == SmallerThan])

            if up_occurrences >= session.query(Settings).first().compliance:
                res.append(BiggerThan)
            elif down_occurrences >= session.query(Settings).first().compliance:
                res.append(SmallerThan)
            else:
                res.append(Equals)

        for group in res:
            if not group == BiggerThan:
                break
        else:
            return AnalysisResult.GOING_UP

        for group in res:
            if not group == SmallerThan:
                break
        else:
            return AnalysisResult.GOING_DOWN

        return AnalysisResult.INSUFFICIENT

    def start(self, sync_queue: Queue) -> Brokerage:
        return asyncio.run(self.trade(sync_queue))

    @staticmethod
    def price_feed() -> Iterator[dict[Literal["price"], float]]:
        while True:
            yield {"price": random.random() * 100}

    async def trade(self, sync_queue: Queue) -> Brokerage:
        trade_node = session.query(TradeNode).filter_by(ticker=self.ticker).first()
        self.state = TradeState.DEFAULT

        brokerage = Brokerage(1000)
        group = []
        groups: list[list[float]] = []
        last_price = None
        price = None
        for i, price in enumerate(datapoint["price"] for datapoint in self.price_feed()):
            print(price)
            if not self.active:
                break

            if i == 0:
                last_price = price
                continue

            try:
                last_trade: Trade | None = trade_node.trades[-1]
            except IndexError:
                last_trade = None
            if last_trade is not None and not last_trade.closing_price:
                if self.state == TradeState.BOUGHT:
                    if price < last_trade.opening_price:
                        brokerage.sell(price)
                        last_trade.closed = datetime.now()
                        last_trade.closing_price = price
                        session.commit()
                        self.state = TradeState.DEFAULT

                elif self.state == TradeState.SHORTING:
                    if price > last_trade.opening_price:
                        brokerage.end_short(price)
                        last_trade.closed = datetime.now()
                        last_trade.closing_price = price
                        session.commit()
                        self.state = TradeState.DEFAULT

            if self.state == TradeState.BOUGHT:
                if last_price > price:
                    brokerage.sell(price)
                    last_trade.closed = datetime.now()
                    last_trade.closing_price = price
                    session.commit()
                    self.state = TradeState.DEFAULT

            elif self.state == TradeState.SHORTING:
                if last_price < price:
                    brokerage.end_short(price)
                    last_trade.closed = datetime.now()
                    last_trade.closing_price = price
                    session.commit()
                    self.state = TradeState.DEFAULT

            # Accumulating the values
            if len(group) == session.query(Settings).first().prices_in_groups:
                groups.append(group)
                group = []
            else:
                group.append(price)
                sync_queue.put(
                    {
                        "action": "update_graph",
                        "ticker": self.ticker,
                        "timestamp": datetime.now().strftime("%H:%M:%S"),
                        "price": price,
                        "state": self.state,
                    }
                )
                last_price = price
                continue
            if not (len(groups) == session.query(Settings).first().groups):
                group.append(price)
                sync_queue.put(
                    {
                        "action": "update_graph",
                        "ticker": self.ticker,
                        "timestamp": datetime.now().strftime("%H:%M:%S"),
                        "price": price,
                        "state": self.state,
                    }
                )
                last_price = price
                continue

            analysis_result = self._analyze(groups)

            group.clear()
            groups.clear()
            budget = 1000
            budget = (
                budget
                * (session.query(Settings).first().allocation_of_funds / 100)
                / 10
            )
            amount = budget / price

            if self.state == TradeState.BOUGHT:
                if analysis_result == AnalysisResult.GOING_UP:
                    # Send "bought" to frontend
                    sync_queue.put(
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
                    brokerage.sell(price)
                    last_trade.closed = datetime.now()
                    last_trade.closing_price = price
                    session.commit()

                    self.state = TradeState.DEFAULT

                    sync_queue.put(
                        {
                            "action": "update_graph",
                            "ticker": self.ticker,
                            "timestamp": datetime.now().strftime("%H:%M:%S"),
                            "price": price,
                            "state": "bought",
                        }
                    )

                elif analysis_result == AnalysisResult.INSUFFICIENT:
                    # Send "bought" to frontend

                    sync_queue.put(
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
                    brokerage.buy(price, amount)
                    trade_node.trades.append(
                        Trade(amount=amount, opening_price=price, opened=datetime.now())
                    )
                    session.commit()

                    self.state = TradeState.BOUGHT

                    sync_queue.put(
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
                    brokerage.short(price, amount)

                    trade_node.trades.append(
                        Trade(amount=amount, opening_price=price, opened=datetime.now())
                    )
                    session.commit()

                    self.state = TradeState.SHORTING

                    sync_queue.put(
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

                    sync_queue.put(
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
                    brokerage.end_short(price)

                    last_trade.closed = datetime.now()
                    last_trade.closing_price = price
                    session.commit()

                    sync_queue.put(
                        {
                            "action": "update_graph",
                            "ticker": self.ticker,
                            "timestamp": datetime.now().strftime("%H:%M:%S"),
                            "price": price,
                            "state": "shorting",
                        }
                    )

                elif analysis_result == AnalysisResult.GOING_DOWN:
                    # Send "shorting" to frontend

                    sync_queue.put(
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

                    sync_queue.put(
                        {
                            "action": "update_graph",
                            "ticker": self.ticker,
                            "timestamp": datetime.now().strftime("%H:%M:%S"),
                            "price": price,
                            "state": "shorting",
                        }
                    )
            last_price = price
        brokerage.end_trading(price)
        return brokerage

    async def stop(self): ...


class Trade(orm.Base):
    __tablename__ = "Trades"
    id = Column(Integer, primary_key=True)
    trade_server_id = Column(Integer, ForeignKey("TradeNodes.ticker"))
    amount = Column(Integer)
    opening_price = Column(Float, nullable=False)
    closing_price = Column(Float)
    opened = Column(DateTime, default=datetime.now)
    closed = Column(DateTime)

    def __init__(self, amount: int, opening_price: float, opened):
        self.amount = amount
        self.opening_price = opening_price
        self.opened = opened


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
