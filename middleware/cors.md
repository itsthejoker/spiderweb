# cors middleware

```python
from spiderweb import SpiderwebRouter

app = SpiderwebRouter(
    middleware=["spiderweb.middleware.cors.CorsMiddleware"],
)
```

CORS, or Cross-Origin Resource Sharing, is an incredibly important piece of how different parts of the web communicate. As such, there is a CORS handler built into Spiderweb.

> [!TIP]
> The CorsMiddleware should be placed as high as possible in the middleware list, as it needs as much control as possible over requests and responses.

This implementation is lovingly ~~ripped~~ ~~lifted~~ borrowed from [Django CORS Headers](https://github.com/adamchainz/django-cors-headers/), an industry-standard implementation for handing CORS that has existed for over a decade. It is essentially and functionally the same. The below doc is ~~copy-and-pasted~~ also borrowed from Django CORS Headers, with updates where needed. (They just already do a great job of explaining these things.)

The available configurations are listed below, and you must set at least one of three following settings:

- `cors_allowed_origins`
- `cors_allowed_origin_regexes` 
- `cors_allow_all_origins`

## cors_allowed_origins

A list of origins that are authorized to make cross-site HTTP requests. The origins in this setting will be allowed, and the requesting origin will be echoed back to the client in the access-control-allow-origin header. Defaults to `[]`.

An Origin is defined as a URI scheme + hostname + port, or one of the special values 'null' or 'file://'. Default ports (HTTPS = 443, HTTP = 80) are optional.

```python
app = SpiderwebRouter(
    cors_allowed_origins=[
        "https://example.com",
        "https://sub.example.com",
        "http://localhost:8080",
        "http://127.0.0.1:9000",
    ]
)
```

## cors_allowed_origin_regexes

A list of strings representing regexes that match Origins that are authorized to make cross-site HTTP requests. Defaults to `[]`. Useful when `cors_allowed_origins` is impractical, such as when you have a large number of subdomains.

```python
app = SpiderwebRouter(
    cors_allowed_origin_regexes=[
        r"^https://\w+\.example\.com$",
    ]
)
```

## cors_allow_all_origins

If `True`, all origins will be allowed. Other settings restricting allowed origins will be ignored. Defaults to `False`.

Setting this to `True` can be _dangerous_, as it allows any website to make cross-origin requests to yours. Generally you'll want to restrict the list of allowed origins with `cors_allowed_origins` or `cors_allowed_origin_regexes`.

```python
app = SpiderwebRouter(
    cors_allow_all_origins=True
)
```

# Optional settings

All the following settings have sensible defaults, but are available if you want to tweak them for your use case. For most cases, you'll just want to leave these alone.

## cors_urls_regex

A regex which restricts the URL's for which the CORS headers will be sent. Defaults to `r'^.*$'`, i.e. match all URL's. Useful when you only need CORS on a part of your site, e.g. an API at /api/.

```python
app = SpiderwebRouter(
    cors_urls_regex=r"^/api/.*$"
)
```

## cors_allow_methods

A list of HTTP verbs that are allowed for the actual request. Defaults to:

```python
DEFAULT_CORS_ALLOW_METHODS = (
    "DELETE",
    "GET",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
)
```

The default can be imported from `spiderweb.constants` so you can just extend it with custom methods. This allows you to keep up to date with any future changes. For example:

```python
from spiderweb.constants import DEFAULT_CORS_ALLOW_METHODS as default_methods

app = SpiderwebRouter(
    cors_allow_methods=(
        *default_methods,
        "POKE",
    )
)
```

## cors_allow_headers

The list of non-standard HTTP headers that you permit in requests from the browser. Sets the `Access-Control-Allow-Headers` header in responses to preflight requests. Defaults to:

```python
CORS_ALLOW_HEADERS = (
    "accept",
    "authorization",
    "content-type",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
)
```

The default can be imported from `spiderweb.constants` so you can extend it with your custom headers. This allows you to keep up to date with any future changes. For example:

```python
from spiderweb.constants import DEFAULT_CORS_ALLOW_HEADERS as default_headers

app = SpiderwebRouter(
    cors_allow_headers=(
        *default_headers,
        "my-custom-header",
    )
)
```

## cors_expose_headers

The list of extra HTTP headers to expose to the browser, in addition to the default [safelisted headers](https://developer.mozilla.org/en-US/docs/Glossary/CORS-safelisted_response_header). If non-empty, these are declared in the [`access-control-expose-headers` header](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Access-Control-Expose-Headers). Defaults to `[]`.

## cors_preflight_max_age

The number of seconds (integer) the browser can cache the preflight response. This sets the [`access-control-max-age` header](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Access-Control-Max-Age) in preflight responses. If this is 0 (or any falsey value), no max age header will be sent. Defaults to `86400` (one day).

Note: Browsers send [preflight requests](https://developer.mozilla.org/en-US/docs/Glossary/Preflight_request) before certain “non-simple” requests, to check they will be allowed. Read more about it in the [CORS MDN article](https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS#preflighted_requests).

## cors_allow_credentials

If `True`, cookies will be allowed to be included in cross-site HTTP requests. This sets the [`Access-Control-Allow-Credentials` header](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/access-control-allow-credentials) in preflight and normal responses. Defaults to `False`.

> [!NOTE]
> The session cookie, by default, uses `Lax` as the security setting, which will prevent the session cookie from being sent cross-domain. If you want to use `cors_allow_credentials`, you will need to change `session_cookie_same_site` to `none` to bypass the security restriction.

## cors_allow_private_network

If `True`, allow requests from sites on “public” IP to this server on a “private” IP. In such cases, browsers send an extra CORS header `access-control-request-private-network`, for which `OPTIONS` responses must contain `access-control-allow-private-network: true`. Defaults to `False`.

Refer to:

- [Local Network Access](https://wicg.github.io/local-network-access/), the W3C Community Draft specification.
- [Private Network Access: introducing preflights](https://developer.chrome.com/blog/private-network-access-preflight/), a blog post from the Google Chrome team.

# A note about CSRF

Most sites will need to take advantage of the Cross-Site Request Forgery protection built into Spiderweb. CORS and CSRF are separate, and Spiderweb wants you to be explicit about how the domains that you work with fit together. If you need to exempt sites from the [`Referer`](https://en.wikipedia.org/wiki/HTTP_referer#Etymology) checking that Spiderweb performs does on secure requests, you can use the `csrf_trusted_origins` setting. For example:

```python
from spiderweb.constants import DEFAULT_CORS_ALLOW_HEADERS as default_headers

app = SpiderwebRouter(
    cors_allowed_origins=[
        "https://read-only.example.com",
        "https://read-and-write.example.com",
    ],
    csrf_trusted_origins=[
        "https://read-and-write.example.com",
    ]
)
```
