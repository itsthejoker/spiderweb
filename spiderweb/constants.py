import importlib.metadata

DEFAULT_ALLOWED_METHODS = ["POST", "GET", "PUT", "PATCH", "DELETE"]
DEFAULT_ENCODING = "UTF-8"

try:
    __version__ = importlib.metadata.version("spiderweb-framework")
except importlib.metadata.PackageNotFoundError:
    import tomllib
    from pathlib import Path

    with open(Path(__file__).parent.parent / "pyproject.toml", "rb") as f:
        __version__ = tomllib.load(f)["project"]["version"]

# https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Set-Cookie
REGEX_COOKIE_NAME = r"^[a-zA-Z0-9\s\(\)<>@,;:\/\\\[\]\?=\{\}\"\t]*$"

DEFAULT_CORS_ALLOW_METHODS = (
    "DELETE",
    "GET",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
)
DEFAULT_CORS_ALLOW_HEADERS = (
    "accept",
    "authorization",
    "content-type",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
)
