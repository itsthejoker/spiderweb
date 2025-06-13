from wsgiref.util import setup_testing_defaults

from peewee import SqliteDatabase

from spiderweb import SpiderwebRouter
from spiderweb.request import Request


class StartResponse:
    def __init__(self):
        self.status = None
        self.headers = None

    def __call__(self, status, headers):
        self.status = status
        self.headers = headers

    def get_headers(self):
        return {h[0]: h[1] for h in self.headers} if self.headers else {}


def setup(**kwargs):
    environ = {}
    setup_testing_defaults(environ)
    if "db" not in kwargs:
        kwargs["db"] = SqliteDatabase("spiderweb-tests.db")
    return (
        SpiderwebRouter(**kwargs),
        environ,
        StartResponse(),
    )


class TestClient:
    def __init__(self, **kwargs):
        self.app, self.environ, self.start_response = setup(**kwargs)
        ...


class RequestFactory:
    @staticmethod
    def create_request(
        environ=None,
        content=None,
        headers=None,
        path=None,
        server=None,
        handler=None,
    ):
        if not environ:
            environ = {}
        setup_testing_defaults(environ)
        environ["HTTP_USER_AGENT"] = "Mozilla/5.0 (testrequest)"
        environ["REMOTE_ADDR"] = "1.1.1.1"
        return Request(
            environ=environ,
            content=content,
            headers=headers,
            path=path,
            server=server,
            handler=handler,
        )
