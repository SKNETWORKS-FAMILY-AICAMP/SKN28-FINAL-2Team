import os

from django.contrib import admin
from django.conf import settings
from django.db import connections
from django.http import JsonResponse
from django.urls import include, path

from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from src.embeddings.embedder import DEFAULT_EMBEDDING_MODEL
from src.storage.chroma import verify_chroma_collection
from src.storage.tourapi import chroma_config_from_env


def health_check(request):
    return JsonResponse({"status": "ok"})


def readiness_check(request):
    try:
        dependencies = _readiness_status()
    except Exception as exc:
        return JsonResponse(
            {"status": "unavailable", "error": exc.__class__.__name__},
            status=503,
        )
    return JsonResponse({"status": "ready", **dependencies})


def _readiness_status():
    for alias in ("default", "travel"):
        with connections[alias].cursor() as cursor:
            cursor.execute("SELECT 1")

    chroma = verify_chroma_collection(
        chroma_config_from_env(project_root=settings.ROOT_DIR),
        expected_model=os.getenv("OPENAI_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL),
    )
    return {"databases": "ok", "chroma": chroma}


urlpatterns = [
    path("health/", health_check, name="health-check"),
    path("ready/", readiness_check, name="readiness-check"),
    path("admin/", admin.site.urls),

    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("swagger/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),

    path("api/token/", TokenObtainPairView.as_view()),
    path("api/token/refresh/", TokenRefreshView.as_view()),

    path("api/accounts/", include("apps.accounts.urls")),
    path("api/travel/", include("apps.travel.urls")),
    path("api/bookmarks/", include("apps.bookmark.urls")),
    path("api/history/", include("apps.history.urls")),
    path("api/", include("apps.reservation.urls")),
]
