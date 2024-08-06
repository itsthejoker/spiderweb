import json
from typing import Any


class HttpResponse:
    def __init__(
            self,
            content: str = None,
            data: dict[str, Any] = None,
            status_code: int = 200,
            headers=None,
    ):
        self.content = content
        self.data = data
        self.status_code = status_code
        self.headers = headers if headers else {}

    def __str__(self):
        return self.content

    def render(self) -> str:
        raise NotImplemented


class JsonResponse(HttpResponse):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.headers["Content-Type"] = "application/json"

    def render(self) -> str:
        return json.dumps(self.data)


class RedirectResponse(HttpResponse):
    ...


class TemplateResponse(HttpResponse):
    ...
