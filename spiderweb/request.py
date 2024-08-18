import json
from urllib.parse import urlparse

from spiderweb.constants import DEFAULT_ENCODING


class Request:
    def __init__(
        self,
        environ=None,
        content=None,
        headers=None,
        path=None,
        server=None,
        handler=None,
    ):
        self.environ = environ
        self.content: str = content
        self.method: str = environ["REQUEST_METHOD"]
        self.headers: dict[str, str] = headers if headers else {}
        self.path: str = path if path else environ["PATH_INFO"]
        self.url = urlparse(path)
        self.query_params = []
        self.server = server
        self.handler = handler  # the view function that will be called
        self.GET = {}
        self.POST = {}
        self.META = {}

        self.populate_headers()
        self.populate_meta()

        content_length = int(self.headers.get("CONTENT_LENGTH") or 0)
        if content_length:
            self.content = (
                self.environ["wsgi.input"].read(content_length).decode(DEFAULT_ENCODING)
            )

    def populate_headers(self) -> None:
        self.headers |= {
            "CONTENT_TYPE": self.environ.get("CONTENT_TYPE"),
            "CONTENT_LENGTH": self.environ.get("CONTENT_LENGTH"),
        }
        for k, v in self.environ.items():
            if k.startswith("HTTP_"):
                self.headers[k] = v

    def populate_meta(self) -> None:
        fields = [
            "SERVER_PROTOCOL",
            "SERVER_SOFTWARE",
            "REQUEST_METHOD",
            "PATH_INFO",
            "QUERY_STRING",
            "REMOTE_HOST",
            "REMOTE_ADDR",
            "SERVER_NAME",
            "GATEWAY_INTERFACE",
            "SERVER_PORT",
            "CONTENT_LENGTH",
            "SCRIPT_NAME",
        ]
        for f in fields:
            self.META[f] = self.environ.get(f)

    def json(self):
        return json.loads(self.content)

    def is_form_request(self) -> bool:
        return (
            "CONTENT_TYPE" in self.headers
            and self.headers["CONTENT_TYPE"] == "application/x-www-form-urlencoded"
        )
