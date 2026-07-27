from django.urls import path

from .views import (
    CartAPIView,
    CartItemDetailAPIView,
    ReservationDetailAPIView,
    ReservationListCreateAPIView,
)

urlpatterns = [
    path("cart/", CartAPIView.as_view(), name="cart"),
    path("cart/<int:pk>/", CartItemDetailAPIView.as_view(), name="cart-item-detail"),
    path("reservations/", ReservationListCreateAPIView.as_view(), name="reservation-list-create"),
    path("reservations/<int:pk>/", ReservationDetailAPIView.as_view(), name="reservation-detail"),
]
