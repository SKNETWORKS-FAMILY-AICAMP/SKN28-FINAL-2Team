from django.conf import settings
from django.db import models

from apps.travel.models import Itinerary, Package


class CartItem(models.Model):
    """장바구니 (M005-F-007 필수) — 선택한 패키지를 담아두는 곳."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cart_items")
    package = models.ForeignKey(Package, on_delete=models.CASCADE, related_name="cart_items")
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "package")
        ordering = ["-added_at"]

    def __str__(self):
        return f"{self.user.email} - {self.package.name}"


class Reservation(models.Model):
    """예약 요청 (M005-F-008 선택, '시연' 수준) — 실제 결제 연동 없이 요청 상태만 관리."""

    class Status(models.TextChoices):
        REQUESTED = "requested", "요청됨"
        CONFIRMED = "confirmed", "확정"
        CANCELLED = "cancelled", "취소됨"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reservations")
    itinerary = models.ForeignKey(
        Itinerary, on_delete=models.SET_NULL, null=True, blank=True, related_name="reservations"
    )

    total_price = models.PositiveIntegerField(default=0)
    payment_method = models.CharField(max_length=100, blank=True, default="신용카드 (**** **** **** 1234)")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.REQUESTED)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Reservation #{self.id} - {self.user.email}"


class ReservationItem(models.Model):
    """예약 시점의 패키지 정보 스냅샷 (이후 패키지 가격이 바뀌어도 예약 내역은 보존)."""

    reservation = models.ForeignKey(Reservation, on_delete=models.CASCADE, related_name="items")
    package = models.ForeignKey(Package, on_delete=models.SET_NULL, null=True, related_name="reservation_items")
    name = models.CharField(max_length=150)
    price = models.PositiveIntegerField(default=0)
    quantity = models.PositiveSmallIntegerField(default=1)

    def __str__(self):
        return f"{self.name} x{self.quantity}"
