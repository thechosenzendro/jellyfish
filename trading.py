import random
from enum import Enum
import time
from numpy import void
from result import Result, Ok, Err


class TradeState(Enum):
    DEFAULT = 1
    BOUGHT = 2
    SHORTING = 3


class AnalysisResult(Enum):
    INSUFFICIENT = 1
    GOING_UP = 2
    GOING_DOWN = 3


# Broker API
class Broker:
    name: str = "Broker"
    working_hours: str = "8:00 - 18:00"

    @staticmethod
    def is_available(ticker: str) -> Result[bool, str]:
        return Ok(True)

    @staticmethod
    def sell(ticker: str) -> Result[None, str]:
        print(f"Selling {ticker}.")
        return Ok(None)

    @staticmethod
    def buy(ticker: str, amount: int) -> Result[None, str]:
        print(f"Buying {amount} {ticker}")
        return Ok(None)


class PriceFeed:
    def __init__(self, ticker: str) -> None:
        self.ticker = ticker

    def __iter__(self):
        return self

    def __next__(self):
        time.sleep(0.1)
        return random.randint(1, 100)
