"""
Async example server for Spiderweb.

Run with uvicorn directly:
    uvicorn example_async:app.asgi_app --reload

Or via the built-in ASGI runner (requires uvicorn installed):
    python example_async.py

Or as a plain WSGI server (sync handlers still work):
    python example_async.py --wsgi
"""

import asyncio
import sys
from datetime import datetime, timedelta

from spiderweb.decorators import csrf_exempt
from spiderweb.exceptions import ServerError
from spiderweb.main import SpiderwebRouter
from spiderweb.response import (
    HttpResponse,
    JsonResponse,
    TemplateResponse,
    RedirectResponse,
)

# ---------------------------------------------------------------------------
# Lifecycle hooks
# ---------------------------------------------------------------------------


async def on_startup():
    # Async startup hook — good place to open DB connections, warm caches, etc.
    print("[startup] async example server is ready")


async def on_shutdown():
    print("[shutdown] async example server is shutting down")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = SpiderwebRouter(
    templates_dirs=["templates"],
    middleware=[
        "spiderweb.middleware.gzip.GzipMiddleware",
        "spiderweb.middleware.cors.CorsMiddleware",
        "spiderweb.middleware.sessions.SessionMiddleware",
        "spiderweb.middleware.csrf.CSRFMiddleware",
        "example_middleware.TestMiddleware",
        # Async-native middleware
        "example_async_middleware.AsyncTimingMiddleware",
        "example_async_middleware.AsyncRequestIdMiddleware",
        "example_async_middleware.AsyncEchoHeaderMiddleware",
        "example_async_middleware.AsyncUppercasePostProcess",
        # Mixed sync middleware — works fine alongside async
        "example_async_middleware.SyncFlagMiddleware",
        # Self-removing middleware demo
        "example_async_middleware.UnusedAsyncMiddleware",
    ],
    staticfiles_dirs=["static_files"],
    cors_allow_all_origins=True,
    append_slash=False,
    debug=True,
    # Restrict request bodies to 1 MB for this example
    max_request_body_size=1 * 1024 * 1024,
    on_startup=[on_startup],
    on_shutdown=[on_shutdown],
)


# ---------------------------------------------------------------------------
# Sync handlers — work in both WSGI and ASGI, run in thread pool under ASGI
# ---------------------------------------------------------------------------


@app.route("/")
def index(request):
    return TemplateResponse(request, "test.html", context={"value": "ASYNC EXAMPLE"})


@app.route("/redirect")
def redirect(request):
    return RedirectResponse("/")


@app.route("/cookies")
def cookies(request):
    print("request.COOKIES:", request.COOKIES)
    resp = HttpResponse(body="COOKIES! NOM NOM NOM")
    resp.set_cookie(name="nom", value="everyonelovescookies")
    resp.set_cookie(
        name="nomtimed",
        value="expires-soon",
        expires=datetime.utcnow() + timedelta(seconds=30),
        max_age=30,
    )
    return resp


@app.route("/session")
def session(request):
    if "visits" not in request.SESSION:
        request.SESSION["visits"] = 0
    else:
        request.SESSION["visits"] += 1
    return HttpResponse(body=f"Visit count (sync): {request.SESSION['visits']}")


@app.route("/example/<int:id>/<str:name>")
def example_with_params(request, id, name):
    return HttpResponse(body=f"Sync handler — id={id}, name={name}")


@app.route("/error")
def error(request):
    raise ServerError


# ---------------------------------------------------------------------------
# Async handlers — native coroutines, no thread-pool overhead under ASGI
# ---------------------------------------------------------------------------


@app.route("/async/hello")
async def async_hello(request):
    """Simple async handler."""
    return HttpResponse(body="Hello from an async handler!")


@app.route("/async/json")
async def async_json(request):
    """Async handler returning JSON."""
    # Simulate a short async I/O operation (e.g., a cache lookup)
    await asyncio.sleep(0)
    return JsonResponse(
        data={
            "handler": "async",
            "timestamp": datetime.utcnow().isoformat(),
            "path": request.path,
        }
    )


@app.route("/async/echo", allowed_methods=["POST"])
@csrf_exempt
async def async_echo(request):
    """
    Async POST handler — echoes the request body as JSON.
    Send any JSON payload; it will be parsed and returned with metadata.
    """
    try:
        payload = request.json()
    except Exception:
        payload = {"raw": request.content}

    return JsonResponse(
        data={
            "method": request.method,
            "received": payload,
            "content_type": request.META.get("CONTENT_TYPE", ""),
        }
    )


@app.route("/async/session")
async def async_session(request):
    """Async handler that reads and writes the session."""
    # Simulate async work before touching the session
    await asyncio.sleep(0)
    if "async_visits" not in request.SESSION:
        request.SESSION["async_visits"] = 0
    else:
        request.SESSION["async_visits"] += 1
    return HttpResponse(body=f"Visit count (async): {request.SESSION['async_visits']}")


@app.route("/async/delay/<int:ms>")
async def async_delay(request, ms):
    """
    Async handler that waits for `ms` milliseconds before responding.
    Use this to verify that async concurrency is working — multiple requests
    should overlap instead of queuing.

    Example: GET /async/delay/500
    """
    ms = min(ms, 5000)  # cap at 5 s for safety
    await asyncio.sleep(ms / 1000)
    return JsonResponse(
        data={"slept_ms": ms, "timestamp": datetime.utcnow().isoformat()}
    )


@app.route("/async/params/<int:id>/<str:name>")
async def async_with_params(request, id, name):
    return JsonResponse(data={"id": id, "name": name, "handler": "async"})


@app.route("/shout/<str:text>")
async def shout(request, text):
    """
    Response body is upper-cased by AsyncUppercasePostProcess middleware.
    Demonstrates async post_process middleware integration.
    """
    return HttpResponse(body=f"shout: {text}")


@app.route("/async/upload", allowed_methods=["GET", "POST"])
@csrf_exempt
async def async_file_upload(request):
    """Async file upload handler."""
    if request.method == "POST":
        if "file" not in request.FILES:
            return HttpResponse(body="No file found in request", status_code=400)
        file = request.FILES["file"]
        # File reading is synchronous but small — fine in an async handler
        content = file.read()
        filepath = file.save()
        try:
            return JsonResponse(
                data={
                    "filename": file.filename,
                    "size_bytes": len(content),
                    "preview": content.decode("utf-8")[:200],
                    "saved_to": str(filepath),
                }
            )
        except UnicodeDecodeError:
            return JsonResponse(
                data={
                    "filename": file.filename,
                    "size_bytes": len(content),
                    "saved_to": str(filepath),
                },
                status_code=201,
            )
    return TemplateResponse(request, "file_upload.html")


# ---------------------------------------------------------------------------
# Custom error handlers
# ---------------------------------------------------------------------------


@app.error(404)
def http404(request) -> HttpResponse:
    return HttpResponse(body="Page not found", status_code=404)


@app.error(405)
def http405(request) -> HttpResponse:
    return HttpResponse(body="Method not allowed", status_code=405)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if "--wsgi" in sys.argv:
        # Plain WSGI — all handlers work, async ones run synchronously via asyncio.run()
        app.start()
    else:
        # ASGI via uvicorn
        app.start_asgi()
