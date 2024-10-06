import json
import socket
import logging
import time
import ssl
from threading import Thread

# set to true on debug environment only
DEBUG = True

# default connection properties
DEFAULT_XAPI_ADDRESS = "xapi.xtb.com"
DEFAULT_XAPI_PORT = 5124
DEFAULT_XAPI_STREAMING_PORT = 5125

# wrapper name and version
WRAPPER_NAME = "python"
WRAPPER_VERSION = "2.5.0"

# API inter-command timeout (in ms)
API_SEND_TIMEOUT = 100

# max connection tries
API_MAX_CONN_TRIES = 3

# logger properties
logger = logging.getLogger("jsonSocket")
FORMAT = "[%(asctime)-15s][%(funcName)s:%(lineno)d] %(message)s"
logging.basicConfig(format=FORMAT)

if DEBUG:
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.CRITICAL)


class TransactionSide(object):
    BUY = 0
    SELL = 1
    BUY_LIMIT = 2
    SELL_LIMIT = 3
    BUY_STOP = 4
    SELL_STOP = 5


class TransactionType(object):
    ORDER_OPEN = 0
    ORDER_CLOSE = 2
    ORDER_MODIFY = 3
    ORDER_DELETE = 4


class JsonSocket(object):
    def __init__(self, address, port, encrypt=False):
        self._ssl = encrypt
        if not self._ssl:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        else:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket = ssl.wrap_socket(sock)
        self.conn = self.socket
        self._timeout = None
        self._address = address
        self._port = port
        self._decoder = json.JSONDecoder()
        self._receivedData = ""

    def connect(self) -> bool:
        for i in range(API_MAX_CONN_TRIES):
            try:
                self.socket.connect((self.address, self.port))
            except socket.error as msg:
                logger.error("SockThread Error: %s" % msg)
                time.sleep(0.25)
                continue
            logger.info("Socket connected")
            return True
        return False

    def _send_obj(self, obj):
        msg = json.dumps(obj)
        self._waiting_send(msg)

    def _waiting_send(self, msg):
        if self.socket:
            sent = 0
            msg = msg.encode("utf-8")
            while sent < len(msg):
                sent += self.conn.send(msg[sent:])
                logger.info("Sent: " + str(msg))
                time.sleep(API_SEND_TIMEOUT / 1000)

    def _read(self, bytes_size=4096):
        resp = None
        if not self.socket:
            raise RuntimeError("socket connection broken")
        while True:
            char = self.conn.recv(bytes_size).decode()
            self._receivedData += char
            try:
                (resp, size) = self._decoder.raw_decode(self._receivedData)
                if size == len(self._receivedData):
                    self._receivedData = ""
                    break
                elif size < len(self._receivedData):
                    self._receivedData = self._receivedData[size:].strip()
                    break
            except ValueError:
                continue
        logger.info("Received: " + str(resp))
        return resp

    def _read_obj(self):
        msg = self._read()
        return msg

    def close(self):
        logger.debug("Closing socket")
        self._close_socket()
        if self.socket is not self.conn:
            logger.debug("Closing connection socket")
            self._close_connection()

    def _close_socket(self):
        self.socket.close()

    def _close_connection(self):
        self.conn.close()

    def _get_timeout(self):
        return self._timeout

    def _set_timeout(self, timeout):
        self._timeout = timeout
        self.socket.settimeout(timeout)

    def _get_address(self):
        return self._address

    def _set_address(self, address):
        pass

    def _get_port(self):
        return self._port

    def _set_port(self, port):
        pass

    def _get_encrypt(self):
        return self._ssl

    def _set_encrypt(self, encrypt):
        pass

    timeout = property(_get_timeout, _set_timeout, doc="Get/set the socket timeout")
    address = property(
        _get_address, _set_address, doc="read only property socket address"
    )
    port = property(_get_port, _set_port, doc="read only property socket port")
    encrypt = property(_get_encrypt, _set_encrypt, doc="read only property socket port")


class APIClient(JsonSocket):
    def __init__(
        self, address=DEFAULT_XAPI_ADDRESS, port=DEFAULT_XAPI_PORT, encrypt=True
    ):
        super(APIClient, self).__init__(address, port, encrypt)
        if not self.connect():
            raise Exception(
                f"Cannot connect to {address}:{port} after {API_MAX_CONN_TRIES} retries"
            )

    def execute(self, dictionary):
        self._send_obj(dictionary)
        return self._read_obj()

    def disconnect(self):
        self.close()

    def command_execute(self, command_name, arguments=None):
        return self.execute(base_command(command_name, arguments))


class APIStreamClient(JsonSocket):
    def __init__(
        self,
        address=DEFAULT_XAPI_ADDRESS,
        port=DEFAULT_XAPI_STREAMING_PORT,
        encrypt=True,
        ss_id=None,
        tick_fun=None,
        trade_fun=None,
        balance_fun=None,
        trade_status_fun=None,
        profit_fun=None,
        news_fun=None,
    ):
        super(APIStreamClient, self).__init__(address, port, encrypt)
        self._ssId = ss_id

        self._tick_fun = tick_fun
        self._trade_fun = trade_fun
        self._balance_fun = balance_fun
        self._trade_status_fun = trade_status_fun
        self._profit_fun = profit_fun
        self._news_fun = news_fun

        if not self.connect():
            raise Exception(
                f"Cannot connect to {address}:{port} after {API_MAX_CONN_TRIES} retries"
            )

        self._running = True
        self._t = Thread(target=self._read_stream, args=())
        self._t.deamon = True
        self._t.start()

    def _read_stream(self):
        while self._running:
            msg = self._read_obj()
            logger.info("Stream received: " + str(msg))
            if msg["command"] == "tickPrices":
                self._tick_fun(msg)
            elif msg["command"] == "trade":
                self._trade_fun(msg)
            elif msg["command"] == "balance":
                self._balance_fun(msg)
            elif msg["command"] == "tradeStatus":
                self._trade_status_fun(msg)
            elif msg["command"] == "profit":
                self._profit_fun(msg)
            elif msg["command"] == "news":
                self._news_fun(msg)

    def disconnect(self):
        self._running = False
        self._t.join()
        self.close()

    def execute(self, dictionary):
        self._send_obj(dictionary)

    def subscribe_price(self, symbol):
        self.execute(
            dict(command="getTickPrices", symbol=symbol, streamSessionId=self._ssId)
        )

    def subscribe_prices(self, symbols):
        for symbolX in symbols:
            self.subscribe_price(symbolX)

    def subscribe_trades(self):
        self.execute(dict(command="getTrades", streamSessionId=self._ssId))

    def subscribe_balance(self):
        self.execute(dict(command="getBalance", streamSessionId=self._ssId))

    def subscribe_trade_status(self):
        self.execute(dict(command="getTradeStatus", streamSessionId=self._ssId))

    def subscribe_profits(self):
        self.execute(dict(command="getProfits", streamSessionId=self._ssId))

    def subscribe_news(self):
        self.execute(dict(command="getNews", streamSessionId=self._ssId))

    def unsubscribe_price(self, symbol):
        self.execute(
            dict(command="stopTickPrices", symbol=symbol, streamSessionId=self._ssId)
        )

    def unsubscribe_prices(self, symbols):
        for symbolX in symbols:
            self.unsubscribe_price(symbolX)

    def unsubscribe_trades(self):
        self.execute(dict(command="stopTrades", streamSessionId=self._ssId))

    def unsubscribe_balance(self):
        self.execute(dict(command="stopBalance", streamSessionId=self._ssId))

    def unsubscribe_trade_status(self):
        self.execute(dict(command="stopTradeStatus", streamSessionId=self._ssId))

    def unsubscribe_profits(self):
        self.execute(dict(command="stopProfits", streamSessionId=self._ssId))

    def unsubscribe_news(self):
        self.execute(dict(command="stopNews", streamSessionId=self._ssId))


# Command templates
def base_command(command_name, arguments=None):
    if arguments is None:
        arguments = dict()
    return dict([("command", command_name), ("arguments", arguments)])


def login_command(user_id, password, app_name=""):
    return base_command(
        "login", dict(userId=user_id, password=password, appName=app_name)
    )


# example function for processing ticks from Streaming socket
def proc_tick_example(msg):
    print("TICK: ", msg)


# example function for processing trades from Streaming socket
def proc_trade_example(msg):
    print("TRADE: ", msg)


# example function for processing trades from Streaming socket
def proc_balance_example(msg):
    print("BALANCE: ", msg)


# example function for processing trades from Streaming socket
def proc_trade_status_example(msg):
    print("TRADE STATUS: ", msg)


# example function for processing trades from Streaming socket
def proc_profit_example(msg):
    print("PROFIT: ", msg)


# example function for processing news from Streaming socket
def proc_news_example(msg):
    print("NEWS: ", msg)


def main():

    # enter your login credentials here
    user_id = 12345
    password = "password"

    # create & connect to RR socket
    client = APIClient()

    # connect to RR socket, login
    login_response = client.execute(login_command(user_id=user_id, password=password))
    logger.info(str(login_response))

    # check if user logged in correctly
    if not login_response["status"]:
        print(f"Login failed. Error code: {login_response['errorCode']}")
        return

    # get ssId from login response
    ssid = login_response["streamSessionId"]

    # second method of invoking commands
    client.command_execute("getAllSymbols")

    # create & connect to Streaming socket with given ssID
    # and functions for processing ticks, trades, profit and tradeStatus
    streaming_client = APIStreamClient(
        ss_id=ssid,
        tick_fun=proc_tick_example,
        trade_fun=proc_trade_example,
        profit_fun=proc_profit_example,
        trade_status_fun=proc_trade_status_example,
    )

    # subscribe for trades
    streaming_client.subscribe_trades()

    # subscribe for prices
    streaming_client.subscribe_prices(["EURUSD", "EURGBP", "EURJPY"])

    # subscribe for profits
    streaming_client.subscribe_profits()

    # this is an example, make it run for 5 seconds
    time.sleep(5)

    # gracefully close streaming socket
    streaming_client.disconnect()

    # gracefully close RR socket
    client.disconnect()


if __name__ == "__main__":
    main()
