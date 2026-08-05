from django.urls import path

from .views import PackageRecommendationAPIView


urlpatterns = [
    path("", PackageRecommendationAPIView.as_view(), name="package-recommendations"),
]
