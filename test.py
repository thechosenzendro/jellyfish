from db import session
from models import TradeNode


model = session.query(TradeNode).filter_by(ticker="AAPL").first()
model.active = True

session.commit()

try:
    model.start()
except KeyboardInterrupt:
    model.active = False
    session.commit()
