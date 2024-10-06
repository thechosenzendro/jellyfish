from dataclasses import dataclass
from enum import Enum

import yfinance
from result import Result, Ok


class TradeState(str, Enum):
    DEFAULT = "analyzing"
    BOUGHT = "bought"
    SHORTING = "shorting"


class AnalysisResult(Enum):
    INSUFFICIENT = 1
    GOING_UP = 2
    GOING_DOWN = 3


# Broker API
class Broker:
    name: str = "Broker"
    working_hours: str = "8:00 - 18:00"

    @staticmethod
    def is_available(_ticker: str) -> Result[bool, str]:
        return Ok(True)

    @staticmethod
    def sell(ticker: str) -> Result[None, str]:
        print(f"Selling {ticker}.")
        return Ok(None)

    @staticmethod
    def buy(ticker: str, amount: int) -> Result[None, str]:
        print(f"Buying {amount} {ticker}")
        return Ok(None)

@dataclass
class Brokerage:
    budget: float
    bought_price: float | None = None
    bought_stocks: int = 0
    mode: TradeState = TradeState.DEFAULT

    def buy(self, price: float, amount: int) -> None:
        total_price = amount * price
        if total_price < self.budget:
            self.bought_price = price
            self.budget -= total_price
            self.bought_stocks = amount
            self.mode = TradeState.BOUGHT

    def sell(self, price: float) -> None:
        total_price = self.bought_stocks * price
        self.budget += total_price
        self.bought_stocks = 0
        self.bought_price = None
        self.mode = TradeState.DEFAULT

    def short(self, price: float, amount: int) -> None:
        self.buy(price, amount)
        self.mode = TradeState.SHORTING

    def end_short(self, price: float) -> None:
        start_price = self.bought_stocks * self.bought_price
        end_price = self.bought_stocks * price

        profit = start_price - end_price

        self.budget += start_price + profit
        self.bought_price = None
        self.bought_stocks = 0
        self.mode = TradeState.DEFAULT

    def end_trading(self, price):
        if self.mode == TradeState.DEFAULT:
            pass
        elif self.mode == TradeState.BOUGHT:
            self.sell(price)
        elif self.mode == TradeState.SHORTING:
            self.end_short(price)
