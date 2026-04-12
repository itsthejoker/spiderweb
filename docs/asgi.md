# asgi

> New in 2.3.0!

Spiderweb supports both WSGI and ASGI from the same `SpiderwebRouter` instance. Your existing WSGI app continues to work exactly as before; ASGI is strictly opt-in.

## Installation

ASGI mode requires `uvicorn`, which is available as an optional extra:

<!-- tabs:start -->

<!-- tab:uv -->

```shell
uv add "spiderweb-framework[asgi]"
```

<!-- tab:pip -->

```shell
pip install "spiderweb-framework[asgi]"
```

<!-- tab:pipenv -->

```shell
pipenv install "spiderweb-framework[asgi]"
```

<!-- tabs:end -->

## The Dev Server

The simplest way to run your app in ASGI mode during development is `app.start_asgi()`. It behaves just like `app.start()`, but runs through uvicorn instead of `wsgiref`.

```python
from spiderweb import SpiderwebRouter
from spiderweb.response import HttpResponse

app = SpiderwebRouter()

@app.route("/")
def index(request):
    return HttpResponse("Hello from ASGI!")

if __name__ == "__main__":
    app.start_asgi()
```

> [!WARNING]
> The dev server is just that: for development. Do not use for production.

## Production Deployment

For production, pass `app.asgi_app` to any ASGI-compatible server. The `asgi_app` property returns the same `ASGIHandler` instance every time, so it's safe to pass once and reuse.

```shell
uvicorn myapp:app.asgi_app --workers 4
```

Or with Hypercorn:

```shell
hypercorn myapp:app.asgi_app
```

## Async Views

Views can be defined as `async def` and they will be awaited natively in ASGI mode. Sync views continue to work too — they're dispatched via `asyncio.to_thread` so they don't block the event loop.

```python
@app.route("/sync")
def sync_view(request):
    return HttpResponse("I'm sync")

@app.route("/async")
async def async_view(request):
    return HttpResponse("I'm async")
```

Both of the above work under both WSGI and ASGI. There's no need to pick one or the other.

## Lifespan Callbacks

You can register startup and shutdown callbacks when creating the router. These are called by the ASGI server during the lifespan protocol — startup before the first request, shutdown after the last.

```python
def on_start():
    print("server is ready")

async def on_stop():
    print("server is shutting down")

app = SpiderwebRouter(
    on_startup=[on_start],
    on_shutdown=[on_stop],
)
```

Both sync and async callbacks are supported. They're no-ops when running under WSGI.

## Async Middleware

Middleware can define `async def` versions of `process_request`, `process_response`, and `post_process`. Spiderweb detects them and awaits them in ASGI mode. Sync middleware works in both modes via `asyncio.to_thread`.

```python
from spiderweb.middleware import SpiderwebMiddleware
from spiderweb.request import Request
from spiderweb.response import HttpResponse


class TimingMiddleware(SpiderwebMiddleware):
    async def process_request(self, request: Request) -> None:
        import time
        request.start_time = time.monotonic()

    async def process_response(self, request: Request, response: HttpResponse) -> None:
        if hasattr(request, "start_time"):
            import time
            elapsed = time.monotonic() - request.start_time
            response.headers["X-Request-Time"] = f"{elapsed:.4f}s"
```

> [!NOTE]
> You only need to define the hooks you actually use. Middleware that only defines `process_request` doesn't need `process_response`, and vice versa.

> See [writing your own middleware](middleware/custom_middleware.md) for the full middleware API.

## Request Body Size Limit

By default, Spiderweb rejects request bodies larger than **10 MB** with a `413` response. You can raise or remove the limit when creating the router:

```python
app = SpiderwebRouter(
    max_request_body_size=50 * 1024 * 1024,  # 50 MB
)
```

Pass `None` to disable the limit entirely:

```python
app = SpiderwebRouter(
    max_request_body_size=None,  # no limit
)
```

> [!WARNING]
> Disabling the size limit means a single request can exhaust your server's memory. Only do this if you have another mechanism (e.g. a reverse proxy) enforcing a limit upstream.

## WSGI and ASGI Side by Side

You can use both protocols at the same time from the same `SpiderwebRouter` instance. The WSGI `__call__` is untouched; `asgi_app` is a separate entry point.

```python
app = SpiderwebRouter()

# WSGI — pass to gunicorn, wsgiref, etc.
wsgi_app = app

# ASGI — pass to uvicorn, hypercorn, etc.
asgi_app = app.asgi_app
```

## Configuration Reference

These `SpiderwebRouter` parameters are specific to ASGI support:

| Parameter | Type | Default | Description |
|---|---|---|---|
| `on_startup` | `list[Callable]` | `[]` | Callbacks invoked during ASGI lifespan startup. |
| `on_shutdown` | `list[Callable]` | `[]` | Callbacks invoked during ASGI lifespan shutdown. |
| `max_request_body_size` | `int \| None` | `10 * 1024 * 1024` | Maximum request body in bytes. `None` disables the limit. |
