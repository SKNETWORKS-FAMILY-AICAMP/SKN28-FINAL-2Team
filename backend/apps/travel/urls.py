from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ItineraryViewSet, PackageViewSet, SharedItineraryAPIView

router = DefaultRouter()
router.register("packages", PackageViewSet, basename="package")
router.register("itineraries", ItineraryViewSet, basename="itinerary")

urlpatterns = [
    path("itineraries/shared/<uuid:token>/", SharedItineraryAPIView.as_view(), name="itinerary-shared"),
    path("", include(router.urls)),
]