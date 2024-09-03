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

A URL can also have multiple capture groups:

```python
@app.route("/example/<int:id>/<str:name>")
def example(request, id, name):
    return HttpResponse(body=f"Example with id {id} and name {name}")
```
In this case, a valid URL might be `/example/3/james`, and both sections will be split out and passed to the view.

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