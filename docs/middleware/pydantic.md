# pydantic form validation

```python
from spiderweb import SpiderwebRouter

app = SpiderwebRouter(
    middleware=["spiderweb.middleware.pydantic.PydanticMiddleware"],
)
```
When working with form data, you may not want to always have to perform your own validation on the incoming data. Spiderweb gives you a way out of the box to perform this validation using Pydantic.

Let's assume that we have a form view that looks like this:

```python
@app.route("/myform", allowed_methods=["GET", "POST"])
def form(request):
    if request.method == "POST":
        if "username" in request.POST and "comment" in request.POST:
            # there's presumably other data in there, but we care about these two
            return JsonResponse(
                data={
                    "username": request.POST["username"],
                    "comment": request.POST["comment"]
                }
            )
    else:
        return TemplateResponse(request, "myform.html")
```

Our form takes in an indeterminate amount of data, but if we really care about some of the fields (or all of them) then we can utilize Pydantic to handle this validation for us. Once the middleware is enabled, we can update our view:

```python
from pydantic import EmailStr

from spiderweb.middleware.pydantic import RequestModel


class CommentForm(RequestModel):
    email: EmailStr
    comment: str

@app.route("/myform", allowed_methods=["GET", "POST"])
def form(request: CommentForm):
    if request.method == "POST":
        return JsonResponse(request.validated_data.dict())
    else:
        return TemplateResponse(request, "myform.html")
```

The Pydantic middleware will automatically detect that the model that you want to use for the request has been added as a type hint, and it will run the validation during the middleware phase so that it can return an error immediately if it fails validation.

> [!NOTE]
> Your validator **must** inherit from RequestModel to function correctly! If it doesn't, it will not trigger.

If the validation fails, the middleware will call `on_error`, which by default will return a 400 with a list of the broken fields. You may not want this behavior, so the easiest way to address it is to subclass PydanticMiddleware with your own version and override `on_error` to do whatever you'd like.

If validation succeeds, the data from the validator will appear on the request object under `request.validated_data` — to access it, just call `.dict()` on the validated data.