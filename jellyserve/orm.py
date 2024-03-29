from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import create_engine


class ORM:
    def __init__(self, engine: str = "sqlite:///dev.db", echo: bool = False):
        self.Base = declarative_base()
        self._engine = create_engine(engine, echo=echo)
        _Session = sessionmaker(bind=self._engine, expire_on_commit=False)
        self.session = _Session()

    def migrate(self):
        self.Base.metadata.create_all(self._engine)
