import json
from urllib.parse import urlparse

from spiderweb.constants import DEFAULT_ENCODING
from spiderweb.utils import get_client_address, Headers


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
        self.COOKIES = {}
        # only used for the session middleware
        self.SESSION = {}
        self._session: dict = {"new_session": False, "id": None}
        # only used for the pydantic middleware and only on POST requests
        self.validated_data = {}

        self.populate_headers()
        self.populate_meta()
        self.populate_cookies()

        content_length = int(self.headers.get("content_length") or 0)
        if content_length:
            self.content = (
                self.environ["wsgi.input"].read(content_length).decode(DEFAULT_ENCODING)
            )

    def populate_headers(self) -> None:
        data = self.headers
        data |= {
            "content_type": self.environ.get("CONTENT_TYPE"),
            "content_length": self.environ.get("CONTENT_LENGTH"),
        }
        for k, v in self.environ.items():
            if k.startswith("HTTP_"):
                data[k] = v
        self.headers = Headers(**{k.lower(): v for k, v in data.items()})

    def populate_meta(self) -> None:
        # all caps fields are from WSGI, lowercase names
        # are custom
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
        for f in self.environ.keys():
            if f.startswith("HTTP_"):
                self.META[f] = self.environ[f]
        self.META["client_address"] = get_client_address(self.environ)

    def populate_cookies(self) -> None:
        if cookies := self.environ.get("HTTP_COOKIE"):
            self.COOKIES = {
                option.split("=")[0]: option.split("=")[1]
                for option in cookies.split("; ")
            }

    def json(self):
        return json.loads(self.content)

    def is_form_request(self) -> bool:
        return (
            "content_type" in self.headers
            and self.headers["content_type"] == "application/x-www-form-urlencoded"
        )
