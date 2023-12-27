from jellyserve.orm import ORM

orm = ORM("sqlite:///db/dev.db")
session = orm.session
