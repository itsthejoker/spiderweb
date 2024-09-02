from datetime import datetime, timedelta

from spiderweb.decorators import csrf_exempt
from spiderweb.example_validator import CommentForm
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
        "spiderweb.middleware.cors.CorsMiddleware",
        "spiderweb.middleware.sessions.SessionMiddleware",
        "spiderweb.middleware.csrf.CSRFMiddleware",
        "example_middleware.TestMiddleware",
        "example_middleware.RedirectMiddleware",
        "spiderweb.middleware.pydantic.PydanticMiddleware",
        "example_middleware.ExplodingMiddleware",
    ],
    staticfiles_dirs=["static_files"],
    append_slash=False,  # default
    cors_allow_all_origins=True,
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
def form(request: CommentForm):
    if request.method == "POST":
        return JsonResponse(data=request.validated_data.dict())
    else:
        return TemplateResponse(request, "form.html")


@app.route("/session")
def session(request):
    if "test" not in request.SESSION:
        request.SESSION["test"] = 0
    else:
        request.SESSION["test"] += 1
    return HttpResponse(body=f"Session test: {request.SESSION['test']}")


@app.route("/cookies")
def cookies(request):
    print("request.COOKIES: ", request.COOKIES)
    resp = HttpResponse(body="COOKIES! NOM NOM NOM")
    resp.set_cookie(name="nom", value="everyonelovescookies")
    resp.set_cookie(name="nom2", value="seriouslycookies")
    resp.set_cookie(
        name="nom3",
        value="yumyum",
        partitioned=True,
        expires=datetime.utcnow() + timedelta(seconds=10),
        max_age=15,
    )
    return resp


if __name__ == "__main__":
    # can also add routes like this:
    # app.add_route("/", index)
    #
    # If gunicorn is installed, you can run this file directly through gunicorn with
    # `gunicorn --workers=2 "example:app"` -- the biggest thing here is that all
    # configuration must be done using decorators or top level in the file.
    app.start()
