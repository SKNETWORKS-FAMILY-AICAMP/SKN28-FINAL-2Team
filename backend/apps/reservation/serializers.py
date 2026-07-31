from rest_framework import serializers

from apps.travel.models import Package
from apps.travel.serializers import PackageSerializer

from .models import CartItem, Reservation, ReservationItem


class CartItemSerializer(serializers.ModelSerializer):
    package_detail = PackageSerializer(source="package", read_only=True)

    class Meta:
        model = CartItem
        fields = ("id", "package", "package_detail", "quantity", "option_date", "option_people","added_at")
        read_only_fields = ("id", "package", "package_detail", "added_at")


class CartSerializer(serializers.Serializer):

    items = CartItemSerializer(many=True)
    total_price = serializers.IntegerField()


class CartItemCreateSerializer(serializers.Serializer):
    package_id = serializers.PrimaryKeyRelatedField(queryset=Package.objects.filter(is_active=True))


class CartItemUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CartItem
        fields = ("quantity","option_date","option_people",)

    def validate_quantity(self, value):
        if value < 1 or value > 9:
            raise serializers.ValidationError(
                "수량은 1개 이상 9개 이하로 설정해주세요."
            )

        return value

    def validate_option_people(self, value):
        if value < 1 or value > 20:
            raise serializers.ValidationError(
                "인원은 1명 이상 20명 이하로 설정해주세요."
            )

        return value

class ReservationItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReservationItem
        fields = ("id", "package", "name", "price", "quantity",  "option_date", "option_people",)


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
    """장바구니를 그대로 예약으로 전환하거나, package_ids를 직접 넘겨 장바구니를 거치지 않고 바로 예약할 수도 있다."""

    itinerary_id = serializers.IntegerField(required=False, allow_null=True)
    package_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, allow_empty=True
    )
    cart_item_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True,
    )
    payment_method = serializers.CharField(required=False, allow_blank=True)
