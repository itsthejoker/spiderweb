# middleware

When processing a request, there are often things that need to happen before the request is passed to the view. Middleware is a way to intercept the request and response objects and do something with them before they are passed to the view or returned to the client.

Middleware in Spiderweb is defined as a list of importable strings that looks like this:

```python
from spiderweb import SpiderwebRouter

app = SpiderwebRouter(
    middleware=[
            "spiderweb.middleware.sessions.SessionMiddleware",
            "spiderweb.middleware.csrf.CSRFMiddleware",
            "spiderweb.middleware.pydantic.PydanticMiddleware",
        ],
)
```

Middleware affects both the incoming request AND the outgoing response, so the order that it's defined here is important. When a request comes in, it will be processed through the middleware in the order that it's defined, but after the response is created, it will pass back through the middleware going the opposite direction. Each piece of middleware has two functions: `process_request` and `process_response`.

When a request comes in, after building the request object, Spiderweb will start running through the middleware from the top down. In the example above, that means that it will call `process_request()` on the SessionMiddleware, then CSRFMiddleware, and finally PydanticMiddleware. At this point, control is passed to the view so that you can run your application-specific logic. As part of the view, you'll return a response, and Spiderweb will take over again.

Now that Spiderweb has the response object, it will start from the bottom of the stack (PydanticMiddleware in the example) and call `process_response()`, working its way up back to the top and ending with the `process_response()` of SessionMiddleware.

> [!NOTE]
> Middleware must be declared when instantiating the server; they can't be added on afterward. Once the server has been started, every piece of middleware will run for every request and every response.

There are a few pieces of middleware built into Spiderweb that you can immediately put to use; they're described on the following pages.
