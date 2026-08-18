from django.http import JsonResponse


def health_check_middleware(get_response):
    def middleware(request):
        if request.path == "/health/":
            return JsonResponse({"status": "ok"})
        return get_response(request)

    return middleware
