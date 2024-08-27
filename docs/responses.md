# responses

Possibly the most important part of a view, a Response allows you to send information back to the browser. Responses also do most of the boring stuff for you of setting headers and making sure everything is encoded correctly.

There are five different types of response in Spiderweb, and each one has a slightly different function.

## HttpResponse

```python
from spiderweb.response import HttpResponse
```

The HttpResponse object is the base class for responses, and if you want to implement your own Response type, this is what you will need to subclass. More information on that at the bottom.

This response is used for raw HTML responses and also contains the helper functions used by the other responses.

Usage:

```python
resp = HttpResponse(
    # the raw string data you want to return
    body: str = None,
    status_code: int = 200,
    # If you want to specify your own headers, you can do
    # so when you instantiate it.
    headers: dict[str, Any] = None,
)
```

## JsonResponse

```python
from spiderweb.response import JsonResponse
```

Sometimes you just need to return JSON, and the JsonResponse is the class you need. It sets up the correct headers for you and is ready to go as soon as you call it.

Usage:

```python
resp = JsonResponse(
    data: dict[str, Any] = None,
    status_code: int = 200,
    headers: dict[str, Any] = None,
)
```

## TemplateResponse

```python
from spiderweb.response import TemplateResponse
```

If you want to render an template using Jinja, you'll need a TemplateResponse. This one is instantiated a little differently from the other responses, but it's to make sure that all your data gets to the places it needs to be.

Usage:

```python
resp = TemplateResponse(
    request: Request,
    template_path: PathLike | str = None,
    template_string: str = None,
    context: dict[str, Any] = None,
    # same as before
    status_code: int = 200,
    headers: dict[str, Any] = None,
)
```

In practice, this is simpler than it looks at first glance.

- `request`: Required. This is the request object that is passed into the view.
- `template_path`: Choose either this or `template_string`. This is the path to the template that you will want to be loading inside your templates directories.
- `template_string`: Choose either this or `template_path`. This is a raw string that will be treated as a template instead of reading from a file.
- `context`: a dict that contains data that will get slotted into the template.

Example (where there is a folder in the local directory called "my_templates", and a file within that directory called "index.html"):

```python
app = SpiderwebRouter(templates_dirs=["my_templates"])


@app.route("/")
def index(request):
    return TemplateResponse(request, "index.html", context={"extra_data": "1, 2, 3"})
```

In this case, the TemplateResponse will load `my_templates/index.html` and use the context dictionary of `{"extra_data": "1, 2, 3"}` to populate it. (The request object will also automatically be added to the context dictionary so that it is accessible in the template during render time.)

Using the `template_string` argument looks like this:

```python
app = SpiderwebRouter(templates_dirs=["my_templates"])


@app.route("/")
def index(request):
    template = """This is where I will display my extra data: {{ extra_data }}"""
    return TemplateResponse(
        request, template_string=template, context={"extra_data": "1, 2, 3"}
    )
```

> [!TIP]
> You can [read more about crafting templates for Jinja here!](https://jinja.palletsprojects.com/en/3.0.x/templates/)

## RedirectResponse

```python
from spiderweb.response import RedirectResponse
```

Occasionally, it's handy to tell the browser to request something else. You can do that with the RedirectResponse:

```python
resp = RedirectResponse(location: str = None)
```

The RedirectResponse will automatically set the status code and headers for you on intitialization, though you can always change them after.

Example:

```python
return RedirectResponse("/")
```

## FileResponse

```python
from spiderweb.response import FileResponse
```

Generic files on the web have two distinct problems: we don't know what kind they are and we don't know how big they are. The FileResponse class handles both setting the headers automatically for the correct mimetype and also breaking the file into chunks to send in a reasonable way.

Ideally, static files and the like will be handled by the reverse proxy aimed at your app (nginx or Apache, usually), but for local developement, being able to serve files is a useful shortcut. You can also use this to serve files directly from your application in other more specific circumstances.

> [!WARNING]
> Using this response is much slower than letting your reverse proxy handle it if you have one; as this is a normal response, it will also undergo processing through the middleware stack each time it's used. For returning a file, it's a waste of computational power.

This is the complete source of the view used to serve static files when using the development server, as it shows nicely how to use this response type:

```python
def send_file(request, filename: str) -> FileResponse:
    for folder in request.server.staticfiles_dirs:
        requested_path = request.server.BASE_DIR / folder / filename
        if os.path.exists(requested_path):
            if not is_safe_path(requested_path):
                raise NotFound
            return FileResponse(filename=requested_path)
    raise NotFound
```
