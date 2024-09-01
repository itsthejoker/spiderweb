import json
import secrets
import string
from http import HTTPStatus
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from spiderweb.request import Request


VALID_CHARS = string.ascii_letters + string.digits


def import_by_string(name):
    # https://stackoverflow.com/a/547867
    components = name.split(".")
    mod = __import__(components[0])
    for comp in components[1:]:
        mod = getattr(mod, comp)
    return mod


def is_safe_path(path: str) -> bool:
    # this cannot possibly catch all issues
    return ".." not in str(path)


def get_http_status_by_code(code: int) -> Optional[str]:
    """
    Get the full HTTP status code required by WSGI by code.

    Example:
        >>> get_http_status_by_code(200)
        '200 OK'
    """
    resp = HTTPStatus(code)
    if resp:
        return f"{resp.value} {resp.phrase}"


def is_form_request(request: "Request") -> bool:
    return (
        "Content-Type" in request.headers
        and request.headers["Content-Type"] == "application/x-www-form-urlencoded"
    )


# https://stackoverflow.com/a/7839576
def get_client_address(environ: dict) -> str:
    try:
        return environ["HTTP_X_FORWARDED_FOR"].split(",")[-1].strip()
    except KeyError:
        return environ.get("REMOTE_ADDR", "unknown")


def generate_key(length=64):
    return "".join(secrets.choice(VALID_CHARS) for _ in range(length))


def is_jsonable(data: str) -> bool:
    try:
        json.dumps(data)
        return True
    except (TypeError, OverflowError):
        return False


class Headers(dict):
    # special dict that forces lowercase for all keys
    def __getitem__(self, key):
        return super().__getitem__(key.lower())

    def __setitem__(self, key, value):
        return super().__setitem__(key.lower(), value)

    def get(self, key, default=None):
        return super().get(key.lower(), default)

    def setdefault(self, key, default = None):
        return super().setdefault(key.lower(), default)