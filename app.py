from fastapi import FastAPI
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import create_engine

app = FastAPI()

Base = declarative_base()
engine = create_engine("sqlite:///dev.db", echo=True)
_Session = sessionmaker(bind=engine)

session = _Session()
