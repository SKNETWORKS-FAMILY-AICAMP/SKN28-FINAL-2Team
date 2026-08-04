from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AccommodationViewSet,
    ItineraryViewSet,
    PackageViewSet,
    RestaurantViewSet,
    SharedItineraryAPIView,
    TouristSpotViewSet,
)

router = DefaultRouter()
router.register("spots", TouristSpotViewSet, basename="spot")
router.register("accommodations", AccommodationViewSet, basename="accommodation")
router.register("restaurants", RestaurantViewSet, basename="restaurant")
router.register("packages", PackageViewSet, basename="package")
router.register("itineraries", ItineraryViewSet, basename="itinerary")

urlpatterns = [
    path("itineraries/shared/<uuid:token>/", SharedItineraryAPIView.as_view(), name="itinerary-shared"),
    path("", include(router.urls)),
]
