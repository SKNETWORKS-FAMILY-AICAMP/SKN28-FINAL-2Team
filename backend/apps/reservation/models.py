from django.conf import settings
from django.db import models

from apps.travel.models import Itinerary


class CartItem(models.Model):

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cart_items",
    )

    package_db_id = models.BigIntegerField()

    quantity = models.PositiveSmallIntegerField(default=1)
    option_date = models.DateField(null=True, blank=True)
    option_people = models.PositiveSmallIntegerField(default=2)

    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "package_db_id")
        ordering = ["-added_at"]

    def __str__(self):
        return f"{self.user.email} - package {self.package_db_id}"


class Reservation(models.Model):
    """실제 결제 연동 없이 요청 상태만 관리."""

    class Status(models.TextChoices):
        REQUESTED = "requested", "요청됨"
        CONFIRMED = "confirmed", "확정"
        CANCELLED = "cancelled", "취소됨"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reservations",
    )

    itinerary = models.ForeignKey(
        Itinerary,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reservations",
    )

    total_price = models.PositiveIntegerField(default=0)
    payment_method = models.CharField(
        max_length=100,
        blank=True,
        default="신용카드 (**** **** **** 1234)",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.REQUESTED,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Reservation #{self.id} - {self.user.email}"


class ReservationItem(models.Model):
    """예약 시점의 패키지 정보 스냅샷."""

    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.CASCADE,
        related_name="items",
    )

    package_db_id = models.BigIntegerField()

    package_id = models.CharField(
        max_length=50,
        blank=True,
        default="",
    )

    name = models.CharField(max_length=255)
    price = models.PositiveIntegerField(default=0)
    quantity = models.PositiveSmallIntegerField(default=1)
    option_date = models.DateField(null=True, blank=True)
    option_people = models.PositiveSmallIntegerField(default=2)

    def __str__(self):
        return f"{self.name} x{self.quantity}"