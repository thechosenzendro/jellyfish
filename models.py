from multiprocessing import Queue
from sqlalchemy.orm import relationship
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime
import queue
from db import orm, session
from trading import TradeState, PriceFeed, AnalysisResult
import asyncio
from trading import Broker
from datetime import datetime


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
        self.ticker = ticker
        self.active = active

    def _analyze(self, groups: list[list[int]]) -> AnalysisResult:
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
        # TODO: Change
        res = []
        for group in comparison_results:
            print(group)
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
            print(f"{groups} {comparison_results}: GOING_UP")
            return AnalysisResult.GOING_UP

        for group in res:
            if not group == SmallerThan:
                break
        else:
            print(f"{groups} {comparison_results}: GOING_DOWN")
            return AnalysisResult.GOING_DOWN

        print(f"{groups} {comparison_results}: INSUFFICIENT")
        return AnalysisResult.INSUFFICIENT

    def start(self, sync_queue: Queue):
        asyncio.run(self.trade(sync_queue))

    async def trade(self, sync_queue: Queue):
        self.state = TradeState.DEFAULT

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
                sync_queue.put(
                    {
                        "action": "update_graph",
                        "ticker": self.ticker,
                        "timestamp": datetime.now().strftime("%H:%M:%S"),
                        "price": price,
                        "state": self.state,
                    }
                )
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
            amount = budget / price

            print(self.state, analysis_result)
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
                    Broker.sell(self.ticker)
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
                    Broker.buy(self.ticker, amount)
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
                    Broker.sell(self.ticker)
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
                    Broker.buy(self.ticker, amount)
                    self.state = TradeState.DEFAULT

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
