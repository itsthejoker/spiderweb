# csrf middleware

```python
from spiderweb import SpiderwebRouter

app = SpiderwebRouter(
    middleware=[
            "spiderweb.middleware.sessions.SessionMiddleware",
            "spiderweb.middleware.csrf.CSRFMiddleware",
        ],
)
```

> [!DANGER]
> The CSRFMiddleware is incomplete at best and dangerous at worst. I am not a security expert, and my implementation is [very susceptible to the thing it is meant to prevent](https://en.wikipedia.org/wiki/Cross-site_request_forgery). While this is an big issue (and moderately hilarious), the middleware is still provided to you in its unfinished state. Be aware.

Cross-site request forgery, put simply, is a method for attackers to make legitimate-looking requests in your name to a service or system that you've previously authenticated to. Ways that we can protect against this involve aggressively expiring session cookies, special IDs for forms that are keyed to a specific user, and more.

> [!TIP]
> Notice that in the example above, SessionMiddleware is also included in the middleware list. The CSRF middleware requires the SessionMiddleware to function, and SessionMiddleware must be placed above it in the middleware list.

## CSRF and Forms

When you create a form, submitting data to the form is the part where things can go wrong. The CSRF middleware grants you two extra pieces in the TemplateResponse response: `csrf_token` and `csrf_token_raw`. `csrf_token` is a preformatted HTML input with preset attributes, ready for use, that you can drop into your template, while `csrf_token_raw` is the token itself with no extra formatting in case you'd like to do something else with it.

Here's an example app that renders a form with two input fields and a checkbox, accepts the form data, and sends back the information as JSON.

```python
# myapp.py
from spiderweb import SpiderwebRouter
from spiderweb.response import JsonResponse, TemplateResponse

app = SpiderwebRouter(
    templates_dirs=["templates"],
    middleware=[
            "spiderweb.middleware.sessions.SessionMiddleware",
            "spiderweb.middleware.csrf.CSRFMiddleware",
        ],
)

@app.route("/", allowed_methods=["GET", "POST"])
def form(request):
    if request.method == "POST":
        return JsonResponse(data=request.POST)
    else:
        return TemplateResponse(request, "form.html")
```

```html
<!-- templates/form.html -->
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Form Demo</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"
          integrity="sha384-QWTKZyjpPEjISv5WaRU9OFeRpok6YctnYmDr5pNlyT2bRjXh0JMhjY6hW+ALEwIH" crossorigin="anonymous">
</head>
<body>
<div class="container">
    <h1>Example Form</h1>
    <form action="" method="post">
    <div class="mb-3">
        <input type="email" class="form-control" name="email" id="emailInput" placeholder="name@example.com">
    </div>
    <div class="mb-3">
        <label for="exampleFormControlTextarea1" class="form-label">Example textarea</label>
        <textarea class="form-control" name="comment" id="exampleFormControlTextarea1" rows="3"></textarea>
    </div>
    <div class="mb-3 form-check">
        <input type="checkbox" name="formcheck" class="form-check-input" id="exampleCheck1">
        <label class="form-check-label" for="exampleCheck1">Check me out</label>
    </div>
    {{ csrf_token }}

    <button type="submit" class="btn btn-primary">Submit</button>
</form>
</div>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"
        integrity="sha384-YvpcrYf0tY3lHB60NNkmXc5s9fDVZLESaAA55NDzOxhy9GkcIdslK1eN7N6jIeHz"
        crossorigin="anonymous"></script>
</body>
</html>
```

With this complete app, it will serve and accept the form. Note towards the bottom of `form.html` the line `{{ csrf_token }}` — this is the inserted key. All you need to do is make sure that line is included inside your form and it will be accepted and parsed. 

## Marking views as CSRF-Exempt

```python
from spiderweb.decorators import csrf_exempt
```

If you want to accept POST data at an endpoint with CSRF verification enabled, you will need to mark the endpoint as CSRF-exempt. Spiderweb provides a decorator for this use case:

```python
@csrf_exempt
@app.route("/form", allowed_methods=["GET", "POST"])
def form(request):
    ...
```

Just drop it above the route information for your function and Spiderweb will not check for a CSRF token when form data is submitted.
