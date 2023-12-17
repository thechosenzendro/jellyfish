from jinja2 import Template
from typing import Any


def template(location: str, **kwargs) -> Template:
    from jinja2 import Environment, PackageLoader, select_autoescape

    env = Environment(loader=PackageLoader("main"), autoescape=select_autoescape())
    _template = env.get_template(location)
    return _template.render(**kwargs)


def sha512(text: Any) -> str:
    import hashlib

    encoded_text = str(text).encode("utf-8")
    return hashlib.sha512(encoded_text).hexdigest()
