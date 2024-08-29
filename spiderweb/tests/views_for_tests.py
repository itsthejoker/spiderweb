from spiderweb.decorators import csrf_exempt
from spiderweb.response import JsonResponse, TemplateResponse


EXAMPLE_HTML_FORM = """
<form action="" method="post">
    <input type="text" name="name" />
    <input type="submit" />
</form>
"""

EXAMPLE_HTML_FORM_WITH_CSRF = """
<form action="" method="post">
    <input type="text" name="name" />
    <input type="submit" />
    {{ csrf_token }}
</form>
"""


def form_view_without_csrf(request):
    if request.method == "POST":
        return JsonResponse(data=request.POST)
    else:
        return TemplateResponse(request, template_string=EXAMPLE_HTML_FORM)


@csrf_exempt
def form_csrf_exempt(request):
    if request.method == "POST":
        return JsonResponse(data=request.POST)
    else:
        return TemplateResponse(request, template_string=EXAMPLE_HTML_FORM_WITH_CSRF)


def form_view_with_csrf(request):
    if request.method == "POST":
        return JsonResponse(data=request.POST)
    else:
        return TemplateResponse(request, template_string=EXAMPLE_HTML_FORM_WITH_CSRF)
