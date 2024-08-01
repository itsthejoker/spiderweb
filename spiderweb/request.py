import json


class Request:
    def __init__(self, content=None, body=None, method=None, headers=None, path=None, url=None, query_params=None):
        self.content: str = content
        self.body: str = body
        self.method: str = method
        self.headers: dict[str] = headers
        self.path: str = path
        self.url = url
        self.query_params = query_params

    def json(self):
        return json.loads(self.content)


