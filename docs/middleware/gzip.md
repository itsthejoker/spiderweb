# gzip compression middleware

> New in 1.4.0!

```python
from spiderweb import SpiderwebRouter

app = SpiderwebRouter(
    middleware=["spiderweb.middleware.gzip.GzipMiddleware"],
)
```

If your app is serving large responses, you may want to compress them. We don't (currently) have built-in support for Brotli, deflate, zstd, or other compression methods, but we do support gzip. (Want to add support for other methods? We'd love to see a PR!)

The implementation in Spiderweb is simple: it compresses the response body if the client indicates that it is supported. If the client doesn't support gzip, the response is sent uncompressed. Compression happens at the end of the response cycle, so it won't interfere with other middleware.

Error responses and responses with status codes that indicate that the response body should not be sent (like 204, 304, etc.) will not be compressed. Responses with a `Content-Encoding` header already set (e.g. if you're serving pre-compressed files) will be handled the same way.

The available configuration options are:

## gzip_minimum_response_length

The minimum size in bytes of a response before it will be compressed. Defaults to `500`. Responses smaller than this will not be compressed.

```python
app = SpiderwebRouter(
    gzip_minimum_response_length=1000
)
```

## gzip_compression_level

The level of compression to use. Defaults to `6`. This is a number between 0 and 9, where 0 is no compression and 9 is maximum compression. Higher levels will result in smaller files, but will take longer to compress and decompress. Level 6 is a good balance between file size and speed.

```python
app = SpiderwebRouter(
    gzip_compression_level=9
)
```
