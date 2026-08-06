from django.contrib import admin
from django.urls import include, path

from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
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
