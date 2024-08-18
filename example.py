from spiderweb.decorators import csrf_exempt
from spiderweb.main import SpiderwebRouter
from spiderweb.exceptions import ServerError
from spiderweb.response import (
    HttpResponse,
    JsonResponse,
    TemplateResponse,
    RedirectResponse,
)


app = SpiderwebRouter(
    templates_dirs=["templates"],
    middleware=[
        "spiderweb.middleware.csrf.CSRFMiddleware",
        "example_middleware.TestMiddleware",
        "example_middleware.RedirectMiddleware",
        "example_middleware.ExplodingMiddleware",
    ],
    staticfiles_dirs=["static_files"],
    append_slash=False,  # default
)


@app.route("/")
def index(request):
    return TemplateResponse(request, "test.html", context={"value": "TEST!"})


@app.route("/redirect")
def redirect(request):
    return RedirectResponse("/")


@app.route("/json")
def json(request):
    return JsonResponse(data={"key": "value"})


@app.route("/error")
def error(request):
    raise ServerError


@app.route("/middleware")
def middleware(request):
    return HttpResponse(
        body="We'll never hit this because it's redirected in middleware"
    )


@app.route("/example/<int:id>")
def example(request, id):
    return HttpResponse(body=f"Example with id {id}")


@app.error(405)
def http405(request) -> HttpResponse:
    return HttpResponse(body="Method not allowed", status_code=405)


@csrf_exempt
@app.route("/form", allowed_methods=["GET", "POST"])
def form(request):
    if request.method == "POST":
        return JsonResponse(data=request.POST)
    else:
        return TemplateResponse(request, "form.html")


if __name__ == "__main__":
    # can also add routes like this:
    # app.add_route("/", index)
    #
    # If gunicorn is installed, you can run this file directly through gunicorn with
    # `gunicorn --workers=2 "example:app"` -- the biggest thing here is that all
    # configuration must be done using decorators or top level in the file.
    app.start()
