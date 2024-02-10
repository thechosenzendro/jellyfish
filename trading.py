import random
from enum import Enum
import time
from result import Result, Ok, Err
import yfinance


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
    def __new__(cls, *args):
        prices = yfinance.download("AAPL", period="1d", interval="1m")["Close"]
        print(prices)
        return prices


class _PriceFeed:
    def __new__(cls, *args):
        return [
            10,
            20,
            30,
            40,
            50,
            60,
            70,
            80,
            90,
            100,
            110,
            120,
            110,
            100,
            110,
            100,
            90,
            80,
            70,
            60,
            70,
            80,
            90,
            100,
            110,
            130,
            150,
            140,
            145,
            140,
            140,
            150,
            160,
            170,
            180,
            160,
            150,
            140,
            130,
            120,
            110,
            110,
            120,
            100,
            90,
            80,
            80,
            90,
            100,
            110,
            120,
            130,
            140,
            150,
        ]


class _PriceFeed:
    def __init__(self, ticker: str) -> None:
        self.ticker = ticker

    def __iter__(self):
        return self

    def __next__(self):
        time.sleep(0.1)
        return random.randint(1, 100)
