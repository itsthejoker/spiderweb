from wsgiref.util import setup_testing_defaults

from peewee import SqliteDatabase

from spiderweb import SpiderwebRouter


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
