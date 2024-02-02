from jinja2 import Environment, BaseLoader
from pydantic import BaseModel
from fastapi.responses import HTMLResponse
from dataclasses import dataclass


@dataclass
class Template:
    path: str

    def read(self):
        with open(self.path) as f:
            return f.read()


class Component(BaseModel, arbitrary_types_allowed=True):
    def html(self) -> HTMLResponse:
        template = self.template
        if isinstance(self.template, Template):
            template = self.template.read()

        return HTMLResponse(
            Environment(loader=BaseLoader).from_string(template).render(**vars(self))
        )

    def raw(self) -> str:
        template = self.template
        if isinstance(self.template, Template):
            template = self.template.read()

        return Environment(loader=BaseLoader).from_string(template).render(**vars(self))
