from db import session
from main import TradeNode
from multiprocessing import Queue

model = session.query(TradeNode).filter_by(ticker="AAPL").first()
model.active = True

mock_queue = Queue()

session.commit()

try:
    model.start(mock_queue)
except KeyboardInterrupt:
    model.active = False
    session.commit()
