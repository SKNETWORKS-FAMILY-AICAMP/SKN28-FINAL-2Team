from rest_framework import serializers

from apps.travel.models import Package
from apps.travel.serializers import PackageSerializer

from .models import CartItem, Reservation, ReservationItem


class CartItemSerializer(serializers.ModelSerializer):
    package_detail = PackageSerializer(source="package", read_only=True)

    class Meta:
        model = CartItem
        fields = ("id", "package", "package_detail", "added_at")
        read_only_fields = ("id", "added_at")


class CartSerializer(serializers.Serializer):
    """GET /api/cart/ 응답 형태 (장바구니 항목 목록 + 합계)."""

    items = CartItemSerializer(many=True)
    total_price = serializers.IntegerField()


class CartItemCreateSerializer(serializers.Serializer):
    package_id = serializers.PrimaryKeyRelatedField(queryset=Package.objects.filter(is_active=True))


class ReservationItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReservationItem
        fields = ("id", "package", "name", "price", "quantity")


class ReservationSerializer(serializers.ModelSerializer):
    items = ReservationItemSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Reservation
        fields = (
            "id", "itinerary", "total_price", "payment_method",
            "status", "status_display", "items", "created_at", "updated_at",
        )
        read_only_fields = ("id", "total_price", "status", "created_at", "updated_at")


class ReservationCreateSerializer(serializers.Serializer):
    """M005-F-008 예약 요청 시연: 장바구니를 그대로 예약으로 전환하거나,
    package_ids를 직접 넘겨 장바구니를 거치지 않고 바로 예약할 수도 있다."""

    itinerary_id = serializers.IntegerField(required=False, allow_null=True)
    package_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, allow_empty=True
    )
    payment_method = serializers.CharField(required=False, allow_blank=True)
