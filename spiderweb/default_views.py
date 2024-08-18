import os

from spiderweb.exceptions import NotFound
from spiderweb.response import JsonResponse, FileResponse
from spiderweb.utils import is_safe_path


def http403(request):
    return JsonResponse(data={"error": "Forbidden"}, status_code=403)


def http404(request):
    return JsonResponse(
        data={"error": f"Route {request.url} not found"}, status_code=404
    )


def http405(request):
    return JsonResponse(data={"error": "Method not allowed"}, status_code=405)


def http500(request):
    return JsonResponse(data={"error": "Internal server error"}, status_code=500)


def send_file(request, filename: str) -> FileResponse:
    for folder in request.server.staticfiles_dirs:
        requested_path = request.server.BASE_DIR / folder / filename
        if os.path.exists(requested_path):
            if not is_safe_path(requested_path):
                raise NotFound
            return FileResponse(filename=requested_path)
    raise NotFound
