from db import orm, session
from models import User, TradeNode, Config
from jellyserve.utils import sha512

orm.migrate()

# Create default admin
if session.query(User).filter_by(username="admin").first() is None:
    admin = User(username="admin", password=sha512("admin"))
    admin.config = Config(currency="USD")
    session.add(admin)

    session.commit()

# Create test TradeServer
if session.query(TradeNode).filter_by(ticker="AAPL").first() is None:
    session.add(TradeNode(ticker="AAPL", active=True))
    session.commit()

if session.query(TradeNode).filter_by(ticker="MSFT").first() is None:
    session.add(TradeNode(ticker="MSFT", active=True))
    session.commit()
