from rest_framework import serializers

from apps.travel.models import Package
from apps.travel.serializers import PackageSerializer

from .models import CartItem, Reservation, ReservationItem


class CartItemSerializer(serializers.ModelSerializer):
    package_detail = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = (
            "id",
            "package_db_id",
            "package_detail",
            "quantity",
            "option_date",
            "option_people",
            "added_at",
        )
        read_only_fields = (
            "id",
            "package_detail",
            "added_at",
        )

    def get_package_detail(self, obj):
        package = (
            Package.objects.using("travel")
            .filter(
                id=obj.package_db_id,
                is_active=True,
            )
            .first()
        )

        if package is None:
            return None

        return PackageSerializer(package).data


class CartSerializer(serializers.Serializer):
    items = CartItemSerializer(many=True)
    total_price = serializers.IntegerField()


class CartItemCreateSerializer(serializers.Serializer):
    package_id = serializers.IntegerField()

    def validate_package_id(self, value):
        exists = (
            Package.objects.using("travel")
            .filter(
                id=value,
                is_active=True,
            )
            .exists()
        )

        if not exists:
            raise serializers.ValidationError(
                "존재하지 않거나 비활성화된 패키지입니다."
            )

        return value


class CartItemUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CartItem
        fields = (
            "quantity",
            "option_date",
            "option_people",
        )

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
        fields = (
            "id",
            "package_db_id",
            "package_id",
            "name",
            "price",
            "quantity",
            "option_date",
            "option_people",
        )


class ReservationSerializer(serializers.ModelSerializer):
    items = ReservationItemSerializer(many=True, read_only=True)
    status_display = serializers.CharField(
        source="get_status_display",
        read_only=True,
    )

    class Meta:
        model = Reservation
        fields = (
            "id",
            "itinerary",
            "total_price",
            "payment_method",
            "status",
            "status_display",
            "items",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "total_price",
            "status",
            "created_at",
            "updated_at",
        )


class ReservationCreateSerializer(serializers.Serializer):
    """
    장바구니를 예약으로 전환하거나,
    package_ids를 직접 넘겨 바로 예약할 수 있다.
    """

    itinerary_id = serializers.IntegerField(
        required=False,
        allow_null=True,
    )

    package_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True,
    )

    cart_item_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True,
    )

    payment_method = serializers.CharField(
        required=False,
        allow_blank=True,
    )