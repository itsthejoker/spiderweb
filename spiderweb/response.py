import datetime
import json
from typing import Any
import mimetypes
from wsgiref.util import FileWrapper

from spiderweb.constants import DEFAULT_ENCODING
from spiderweb.exceptions import GeneralException
from spiderweb.request import Request


mimetypes.init()


class HttpResponse:
    def __init__(
        self,
        body: str = None,
        data: dict[str, Any] = None,
        context: dict[str, Any] = None,
        status_code: int = 200,
        headers=None,
    ):
        self.body = body
        self.data = data
        self.context = context if context else {}
        self.status_code = status_code
        self.headers = headers if headers else {}
        if not self.headers.get("Content-Type"):
            self.headers["Content-Type"] = "text/html; charset=utf-8"
        self.headers["Server"] = "Spiderweb"
        self.headers["Date"] = datetime.datetime.now(tz=datetime.UTC).strftime(
            "%a, %d %b %Y %H:%M:%S GMT"
        )

    def __str__(self):
        return self.body

    def render(self) -> str:
        return str(self.body)


class FileResponse(HttpResponse):
    def __init__(self, filename, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.filename = filename
        self.content_type = mimetypes.guess_type(self.filename)[0]
        self.headers["Content-Type"] = self.content_type

    def render(self) -> list[bytes]:
        with open(self.filename, "rb") as f:
            self.body = [chunk for chunk in FileWrapper(f)]
        return self.body


class JsonResponse(HttpResponse):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.headers["Content-Type"] = "application/json"

    def render(self) -> str:
        return json.dumps(self.data)


class RedirectResponse(HttpResponse):
    def __init__(self, location: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.status_code = 302
        self.headers["Location"] = location


class TemplateResponse(HttpResponse):
    def __init__(self, request: Request, template=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.context["request"] = request
        self.template = template
        self.loader = None
        self._template = None
        if not template:
            raise GeneralException("TemplateResponse requires a template.")

    def render(self) -> str:
        if self.loader is None:
            raise GeneralException("TemplateResponse requires a template loader.")
        self._template = self.loader.get_template(self.template)
        return self._template.render(**self.context)

    def set_template_loader(self, env):
        self.loader = env
