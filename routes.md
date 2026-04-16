# routes

To have logic that your application can use, you must be able to route incoming requests from The Outside:tm: and properly get them to your code and back. There are three different ways to set up this up depending on what works best for your application, and all three can be used together (though this is probably a bad idea).

## `route()` Decorator

In this pattern, you'll create your server at the top of the file and assign it to an object (usually called `app`). Once it's created, you'll be able to use the `@app.route` decorator to assign routes. This is the pattern used by the quickstart app:

```python
from spiderweb import SpiderwebRouter
from spiderweb.response import HttpResponse

app = SpiderwebRouter()

@app.route("/")
def index(request):
    return HttpResponse("HELLO, WORLD!")

if __name__ == "__main__":
    app.start()
```

The `@app.route()` decorator takes two arguments — one required, one optional. The first is the path that your view will be found under; all paths start from the server root (`"/"`). The second is `allowed_methods`, which allows you to limit (or expand) the HTTP methods used for calling your view. For example, you may want to specify that a form view takes in `GET` and `POST` requests:

```python
@app.route("/myform", allowed_methods=["GET", "POST"])
def form_view(request):
    ...
```
If `allowed_methods` isn't passed in, the defaults (`["POST", "GET", "PUT", "PATCH", "DELETE"]`) will be used.

The decorator pattern is recommended simply because it's familiar to many, and for small apps, it's hard to beat the simplicity.

## After Instantiation

Some folks prefer to manually assign routes after the server has been instantiated, perhaps because the route isn't actually determined until runtime. To do this, the built server object has a function you can use:

```python
from spiderweb import SpiderwebRouter
from spiderweb.response import HttpResponse

app = SpiderwebRouter()

def index(request):
    return HttpResponse("HELLO, WORLD!")

if __name__ == "__main__":
    # shown here with the optional `allowed_methods` arg
    app.add_route("/", index, allowed_methods=["GET"])
    app.start()
```
The `allowed_methods` argument, like with the `.route()` decorator, is optional. If it's not passed, the defaults will be used instead. 

## During Instantiation

The third and final way that you can assign routes is in a single block more akin to how Django handles it. This allows you to curate large numbers of routes and pass them all in at the same time with little fuss. Though it may be a little contrived here, you can see how this works in the following example:

```python
from spiderweb import SpiderwebRouter
from spiderweb.response import HttpResponse


def index(request):
    return HttpResponse("HELLO, WORLD!")


if __name__ == "__main__":
    app = SpiderwebRouter(
        routes=[
            ("/", index, {"allowed_methods": ["GET", "POST"]})
        ]
    )
    app.start()
```
To declare routes during instantiation, pass in a list of tuples, where each tuple consists of three things:

```
routes = [
    (path: str, function: Callable, args: dict),
    ...
]
```
The only two args that can be passed here are `allowed_methods` as discussed above and `csrf_exempt`, where the value is a boolean (presumably `True`, as it defaults to `False`). For example, if you had a view that took unverified `POST` requests, you might set it up like this:

```python
routes = [
    ("/submit", submit_view, {"allowed_methods": ["POST"], "csrf_exempt": True})
]
```
Note that passing in `csrf_exempt` is not listed on the other two methods, mostly because it doesn't really make sense for the other methods. Instead, they use a decorator to handle it, which can be found in [the docs for CSRF protection.](middleware/csrf.md?id=marking-views-as-csrf-exempt) You can also use the decorator in the same way for routes assigned in this manner, but when you have a large number of routes, being able to see all the attributes in one place is helpful.

## Passing Data Through Routes

Some views need to be able to take arguments via the URL path, so Spiderweb provides that ability for you. The syntax used is identical to Django's: `/routename/<str:argname>`. In this case, it will slice out that part of the URL, cast it to a string, and pass it as a variable named `argname` to your view. Here's what that looks like in practice:

```python
@app.route("/example/<int:id>")
def example(request, id):  # <- note the additional arg!
    return HttpResponse(body=f"Example with id {id}")
```
You can pass integers, strings, and positive floats with the following types:

- str
- int
- float
- path (see below)

A URL can also have multiple capture groups:

```python
@app.route("/example/<int:id>/<str:name>")
def example(request, id, name):
    return HttpResponse(body=f"Example with id {id} and name {name}")
```
In this case, a valid URL might be `/example/3/james`, and both sections will be split out and passed to the view.

The `path` option is special; this is used when you want to capture everything after the slash. For example:

[!badge New in 1.2.0!]

```python
@app.route("/example/<path:rest>")
def example(request, rest):
    return HttpResponse(body=f"Example with {rest}")
```
It will come in as a string, but it will include all the slashes and other characters that are in the URL.

## Adding Error Views

For some apps, you may want to have your own error views that are themed to your particular application. For this, there's a slightly different process, but the gist is the same. There are also three ways to handle error views, all very similar to adding regular views.

An error view has three pieces: the request, the response, and what error code triggers it. The easiest way to do this is with the decorator.

### `.error` Decorator

```python
@app.error(405)
def http405(request) -> HttpResponse:
    return HttpResponse(body="Method not allowed", status_code=405)
```
Note that this is just a basic view with nothing really special about it; the only real difference is that the `.error()` decorator highlights the specific error that will trigger this view. If the server, at any point, hits this error value, it will retrieve this view and return it instead of the requested view.

### After Instantiation

Similar to the regular views, error views can also be added programmatically at runtime like this:

```python
def http405(request) -> HttpResponse:
    return HttpResponse(body="Method not allowed", status_code=405)

app.add_error_route(405, http405)
```
No other attributes or arguments are available.

### During Instantiation

For those with larger numbers of routes, it may make more sense to declare them when the server object is built. For example:

```python
app = SpiderwebRouter(
    error_routes={405: http405},
)
```
As with the `routes` argument, as many routes as you'd like can be registered here without issue.

## Finding Routes Again

[!badge New in 1.1.0!]

If you need to find the path that's associated with a route (for example, for a RedirectResponse), you can use the `app.reverse()` function to find it. This function takes the name of the view and returns the path that it's associated with. For example:

```python
@app.route("/example", name="example")
def example(request):
    return HttpResponse(body="Example")

path = app.reverse("example")
print(path)  # -> "/example"
```

If you have a route that takes arguments, you can pass them in as a dictionary:

```python
@app.route("/example/<int:obj_id>", name="example")
def example(request, obj_id):
    return HttpResponse(body=f"Example with id {obj_id}")

path = app.reverse("example", {'obj_id': 3})
print(path)  # -> "/example/3"
```

You can also provide a dictionary of query parameters to be added to the URL:

```python
path = app.reverse("example", {'obj_id': 3}, query={'name': 'james'})
print(path)  # -> "/example/3?name=james"
```

The arguments you pass in must match what the path expects, or you'll get a `SpiderwebException`. If there's no route with that name, you'll get a `ReverseNotFound` exception instead.

## Route Groups

[!badge New in 2.4.0!]

As your application grows, keeping all of its routes in one file becomes unwieldy. Route groups let you define a set of related routes together — with a shared URL prefix — and then mount them onto your app in one shot.

```python
from spiderweb import SpiderwebRouter, RouteGroup
from spiderweb.response import HttpResponse, JsonResponse

api = RouteGroup(prefix="/api")

@api.route("/users")
def list_users(request):
    return JsonResponse({"users": []})

@api.route("/users/<int:id>")
def get_user(request, id):
    return JsonResponse({"id": id})

app = SpiderwebRouter()
app.include_routegroup(api)

if __name__ == "__main__":
    app.start()
```

The two routes above are registered as `/api/users` and `/api/users/<int:id>`. Everything else works exactly as it would if you had written `@app.route("/api/users")` yourself — URL parameter conversion, `allowed_methods`, all of it.

You can also use `add_route()` on a group directly, without the decorator:

```python
api = RouteGroup(prefix="/api")
api.add_route("/status", status_view, allowed_methods=["GET"], name="status")
```

### Namespaces

If you give a route group a `namespace`, route names inside it are automatically prefixed with `"namespace:"`. This keeps reverse lookups unambiguous when two groups have routes with the same local name.

```python
v1 = RouteGroup(prefix="/v1", namespace="v1")
v2 = RouteGroup(prefix="/v2", namespace="v2")

@v1.route("/ping", name="ping")
def ping_v1(request):
    return HttpResponse("v1")

@v2.route("/ping", name="ping")
def ping_v2(request):
    return HttpResponse("v2")

app = SpiderwebRouter()
app.include_routegroup(v1)
app.include_routegroup(v2)

app.reverse("v1:ping")  # -> "/v1/ping"
app.reverse("v2:ping")  # -> "/v2/ping"
```

Without a namespace, route names pass through unchanged, so existing apps that don't need namespacing work exactly as before.

> [!TIP]
> You can include as many route groups as you like on the same app. Groups don't know about each other, so two groups that share the same prefix are fine as long as their individual paths don't clash.

## Custom Path-Parameter Converters

[!badge New in 2.4.0!]

The built-in converters (`str`, `int`, `float`, `path`) cover the common cases, but sometimes you need a custom pattern — a UUID, a slug, a date string, and so on. You can teach Spiderweb new converters with `register_converter()`.

A converter is any class with two things:

- a `regex` class attribute — the pattern that must match the URL segment
- a `to_python()` method — converts the matched string to whatever Python type you want

```python
from spiderweb import SpiderwebRouter
from spiderweb.response import HttpResponse

class SlugConverter:
    regex = r"[-a-z0-9_]+"
    name = "slug"

    def to_python(self, value):
        return str(value)

app = SpiderwebRouter()
app.register_converter(SlugConverter)

@app.route("/posts/<slug:post_slug>")
def get_post(request, post_slug):
    return HttpResponse(f"post: {post_slug}")
```

The `name` attribute controls what you write in the route path — `<slug:...>` in this case. If you leave `name` off the class, Spiderweb derives it automatically by lower-casing the class name and stripping a trailing `"converter"` (so `SlugConverter` becomes `"slug"` either way).

### A more complete example

Here's a UUID converter that hands you a proper `uuid.UUID` object in your view:

```python
import uuid

class UUIDConverter:
    regex = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    name = "uuid"

    def to_python(self, value):
        return uuid.UUID(value)

app.register_converter(UUIDConverter)

@app.route("/records/<uuid:record_id>")
def get_record(request, record_id):
    # record_id is a uuid.UUID instance here
    return HttpResponse(str(record_id))
```

Custom converters work inside route groups too — just register them on the app before calling `include_routegroup()`:

```python
app.register_converter(SlugConverter)

blog = RouteGroup(prefix="/blog", namespace="blog")

@blog.route("/<slug:post_slug>", name="post")
def blog_post(request, post_slug):
    return HttpResponse(post_slug)

app.include_routegroup(blog)

app.reverse("blog:post", {"post_slug": "hello-world"})  # -> "/blog/hello-world"
```

> [!NOTE]
> Custom converters don't replace the built-ins. You can mix `<int:id>` and `<uuid:uid>` in the same app without any conflict.

## Class-Based Views

Sometimes a single view function becomes unwieldy because it has to handle `GET`, `POST`, and maybe other HTTP methods all in one place. For these situations, Spiderweb provides a `View` class that you can inherit from to create Class-Based Views. 

Instead of checking the request method inside your function, you can define a class method for each HTTP verb you want to support. The base `View` class will automatically route the request to the correct method or return a `405 Method Not Allowed` if the method isn't implemented. It also automatically handles `OPTIONS` requests for you!

Here's an example of how to set one up:

```python
from spiderweb import SpiderwebRouter
from spiderweb.response import HttpResponse
from spiderweb.routes import View

app = SpiderwebRouter()

class Index(View):
    def get(self, request, *args, **kwargs):
        return HttpResponse("This is a GET request from a class!")

    def post(self, request, *args, **kwargs):
        return HttpResponse("This is a POST request from a class!")

# You can register it using add_route:
app.add_route("/", Index)
```

You can also use the `@app.route()` decorator directly on the class if you prefer that style:

```python
@app.route("/about")
class About(View):
    def get(self, request):
        return HttpResponse("About us")
```

> [!NOTE]
> When using Class-Based Views, the `View` class automatically allows any HTTP methods that you have defined on your subclass, meaning you don't need to manually configure `allowed_methods` for the route.
