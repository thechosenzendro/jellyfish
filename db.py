from jellyserve.orm import ORM

orm = ORM("sqlite:///dev.sqlite")
session = orm.session
