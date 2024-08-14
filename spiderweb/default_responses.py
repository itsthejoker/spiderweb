from spiderweb.response import JsonResponse


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
