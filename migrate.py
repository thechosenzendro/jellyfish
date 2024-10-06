from db import orm, session
from jellyserve.utils import sha512
from models import User, TradeNode, Config, Settings


def migrate():
    orm.migrate()

    # Create default admin
    if session.query(User).filter_by(username="admin").first() is None:
        admin = User(username="admin", password=sha512("admin"))
        admin.config = Config(currency="USD")
        session.add(admin)

    if session.query(TradeNode).filter_by(ticker="AAPL").first() is None:
        session.add(TradeNode("AAPL", active=True))

    if session.query(Settings).first() is None:
        session.add(
            Settings(allocation_of_funds=50, groups=2, prices_in_groups=5, compliance=3)
        )

    session.commit()


if __name__ == "__main__":
    migrate()
