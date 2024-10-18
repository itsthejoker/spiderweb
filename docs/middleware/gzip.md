# Gzip compress middleware

```python
from spiderweb import SpiderwebRouter

app = SpiderwebRouter(
    middleware=["spiderweb.middleware.gzip"],
)
```
When your response is big, you maybe want to reduce traffic between
server and client.

Gzip will help you. This middleware do not cover all possibilities of content compress. Brotli, deflate, zsts or other are out of scope.

This version only check if gzip method is accepted by client, size of content is greater than 500 bytes. Check if response is not already compressed and response status is between 200 and 300.


> [!NOTE]
> Minimal required version is 1.3.1

