from rest_framework import serializers

from apps.travel.models import Package
from apps.travel.serializers import PackageSerializer

from .models import Bookmark


class BookmarkSerializer(serializers.ModelSerializer):
    package_detail = serializers.SerializerMethodField()

    class Meta:
        model = Bookmark
        fields = ("id", "package_db_id", "package_detail", "created_at")
        read_only_fields = ( "id", "package_detail", "created_at")

    def get_package_detail(self, obj):
        try:
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

        except Exception:
            return None


class BookmarkCreateSerializer(serializers.Serializer):
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