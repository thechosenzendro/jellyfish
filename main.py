from fastapi import Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse

from app import Base, session, engine, app
from utils import template, sha512
from sqlalchemy import Column, Integer, String
import random


# Models
class User(Base):
    __tablename__ = "Users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True)
    password = Column(String)
    session = Column(String, unique=True)

    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password

    def __repr__(self):
        return "<User(id='%s', username='%s')>" % (self.id, self.username)


Base.metadata.create_all(engine)

# Create default admin
if session.query(User).filter_by(username="admin").first() is None:
    session.add(User(username="admin", password=sha512("admin")))
    session.commit()


# Routes
@app.get("/")
async def index():
    page = template("login.html").render()
    return HTMLResponse(page)


@app.post("/login")
async def login(request: Request):
    form_data = await request.form()
    username, password = form_data["username"], form_data["password"]
    user = session.query(User).filter_by(username=username, password=sha512(password)).first()

    if user is not None:
        token = sha512(random.randint(0, 100000))
        user.session = token
        session.commit()

        response = RedirectResponse(status_code=302, url="/dashboard")
        response.set_cookie(key="session", value=token, httponly=True)
        return response
    else:
        return RedirectResponse(status_code=302, url="/")


@app.middleware("http")
async def is_logged_in(request: Request, call_next):
    response = await call_next(request)
    if "/dashboard" in str(request.url):
        session_token = request.cookies.get("session")
        if session_token:
            user = session.query(User).filter_by(session=session_token).first()
            if user is not None:
                return response
            else:
                return RedirectResponse(status_code=302, url="/")
        else:
            return RedirectResponse(status_code=302, url="/")
    else:
        return response


@app.get("/dashboard")
async def dashboard():
    page = template("dashboard.html").render()
    return HTMLResponse(page)


@app.post("/logout")
async def logout(request: Request, response: Response):
    session_token = request.cookies.get("session")

    if session_token:
        user = session.query(User).filter_by(session=session_token).first()
        if user is not None:
            user.session = ""
            session.commit()
            response.delete_cookie("session")
        else:
            return {"error": f"No user with token {session_token}"}
    else:
        return {"error": "Empty token"}
    return RedirectResponse(status_code=302, url="/")
