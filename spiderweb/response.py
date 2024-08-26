import datetime
import json
import re
from os import PathLike
from typing import Any
import urllib.parse
import mimetypes
from wsgiref.util import FileWrapper

from spiderweb.constants import REGEX_COOKIE_NAME
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
        headers: dict[str, Any] = None,
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

    def set_cookie(
        self,
        name: str,
        value: str,
        domain: str = None,
        expires: datetime.datetime = None,
        http_only: bool = None,
        max_age: int = None,
        partitioned: bool = None,
        path: str = None,
        secure: bool = False,
        same_site: str = None,
    ):
        if not bool(re.match(REGEX_COOKIE_NAME, name)):
            url = "https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Set-Cookie#attributes"
            raise GeneralException(
                f"Cookie name has illegal characters. See {url} for information on"
                f" allowed characters."
            )
        additions = {}
        booleans = []

        if domain:
            additions["Domain"] = domain
        if expires:
            additions["Expires"] = expires.strftime("%a, %d %b %Y %H:%M:%S GMT")
        if max_age:
            additions["Max-Age"] = int(max_age)
        if path:
            additions["Path"] = path
        if same_site:
            valid_values = ["strict", "lax", "none"]
            if same_site.lower() not in valid_values:
                raise GeneralException(
                    f"Invalid value {same_site} for `same_site` cookie attribute. Valid"
                    f" options are 'strict', 'lax', or 'none'."
                )
            additions["SameSite"] = same_site.title()

        if http_only:
            booleans.append("HttpOnly")
        if partitioned:
            booleans.append("Partitioned")
        if secure:
            booleans.append("Secure")

        attrs = [f"{k}={v}" for k, v in additions.items()]
        attrs += booleans
        attrs = [urllib.parse.quote_plus(value)] + attrs
        cookie = f"{name}={'; '.join(attrs)}"

        if "Set-Cookie" in self.headers:
            self.headers["Set-Cookie"].append(cookie)
        else:
            self.headers["Set-Cookie"] = [cookie]

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
    def __init__(
        self,
        request: Request,
        template_path: PathLike | str = None,
        template_string: str = None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.context["request"] = request
        self.template_path = template_path
        self.template_string = template_string
        self.template_loader = None
        self.string_loader = None
        self._template = None
        if not template_path and not template_string:
            raise GeneralException("TemplateResponse requires a template.")

    def render(self) -> str:
        if self.template_loader is None:
            if not self.template_string:
                raise GeneralException(
                    "TemplateResponse has no loader. Did you set templates_dirs?"
                )
            else:
                self._template = self.string_loader.from_string(self.template_string)
        else:
            self._template = self.template_loader.get_template(self.template_path)

        return self._template.render(**self.context)

    def set_template_loader(self, loader):
        self.template_loader = loader

    def set_string_loader(self, loader):
        self.string_loader = loader
