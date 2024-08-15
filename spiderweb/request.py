import json
from urllib.parse import urlparse


class Request:
    def __init__(
        self,
        content=None,
        body=None,
        method=None,
        headers=None,
        path=None,
        query_params=None,
        server=None
    ):
        self.content: str = content
        self.body: str = body
        self.method: str = method
        self.headers: dict[str] = headers
        self.path: str = path
        self.url = urlparse(path)
        self.query_params = query_params
        self.server = server
        self.GET = {}
        self.POST = {}

    def json(self):
        return json.loads(self.content)
