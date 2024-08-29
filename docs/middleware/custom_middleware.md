from spiderweb import HttpResponse

# writing your own middleware

Sometimes you want to run the same code on every request or every response (or both!). Lots of processing happens in the middleware layer, and if you want to write your own, all you have to do is write a quick class and put it in a place that Spiderweb can find it. A piece of middleware only needs two things to be successful:

- it must be a class that inherits from SpiderwebMiddleware
- it must handle either requests, responses, or both!

That's really all there is to it. Here's a template you can copy:

```python
from spiderweb.middleware import SpiderwebMiddleware
from spiderweb.request import Request
from spiderweb.response import HttpResponse


class TestMiddleware(SpiderwebMiddleware):
    def process_request(self, request: Request) -> None:
        # example of a middleware that sets a flag on the request
        request.spiderweb = True

    def process_response(self, request: Request, response: HttpResponse) -> None:
        # example of a middleware that sets a header on the resp
        if hasattr(request, "spiderweb"):
            response.headers["X-Spiderweb"] = "true"
```

Middleware is run twice: once for the incoming request and once for the outgoing response. You only need to include whichever function is required for the functionality you need.

## process_request(self, request):

`process_request` is called before the view is reached in the execution order. You will receive the assembled Request object, and any middleware declared above this one will have already run. Because the request is the single instantiation of a class, you can modify it in-place without returning anything and your changes will stick. 

This function also has a special ability; it can stop execution before the view is called by returning a response. If a response is returned, Spiderweb will immediately skip to applying the response middleware and sending the response back to the client. Here's an example of what that might look like:

```python
class JohnMiddleware(SpiderwebMiddleware):
    def process_request(self, request: Request) -> Optional[HttpResponse]:
        if (
            hasattr(request, "user")
            and user.name == "John"
            and request.path.startswith("/admin")
        ):
            return HttpResponse("Go away, John!", status_code=403)
```

In this case, if the user John tries to access any route that starts with "/admin", he'll immediately get denied and the view will never be called. If the request does not have a user attached to it (or the user is not John), then the middleware will return None and Spiderweb will continue processing.

## process_response(self, request, response):

This function is called after the view has run and returned a response. You will receive the request object and the response object; like with the request object, the response is also a single instantiation of a class, so any changes you make will stick automatically.

Unlike `process_request`, returning a value here doesn't change anything. We're already processing a request, and there are opportunities to turn away requests / change the response at both the `process_request` layer and the view layer, so Spiderweb assumes that whatever it is working on here is what you mean to return to the user. The response object that you receive in the middleware is still prerendered, so any changes you make to it will take effect after it finishes the middleware and renders the response.

## on_error(self, request, triggered_exception):

This is a helper function that is available for you to override; it's not often used by middleware, but there are some ([like the pydantic middleware](pydantic.md)) that call `on_error` when there is a validation failure.

## UnusedMiddleware

```python
from spiderweb.exceptions import UnusedMiddleware
```

If you don't want your middleware to run for some reason, either `process_request` or `process_response` can raise the UnusedMiddleware exception. If this happens, Spiderweb will kick your middleware out of the processing order for the rest of the life of the server. Note that this applies to the middleware as a whole, so both functions will not be run if an UnusedMiddleware is raised. This is a great way to mark debug middleware that shouldn't run or create time-delay middleware that runs until a certain condition is met! 
