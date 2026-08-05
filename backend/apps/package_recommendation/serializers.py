from rest_framework import serializers


class PackageRecommendationRequestSerializer(serializers.Serializer):
    """Accept both the current and legacy itinerary RAG response shapes."""

    status = serializers.CharField(required=False)
    condition = serializers.DictField(required=False)
    conditions = serializers.DictField(required=False)
    itinerary = serializers.JSONField()
    top_k = serializers.IntegerField(required=False, default=3, min_value=1, max_value=10)

    def validate(self, attrs):
        if not attrs.get("condition") and not attrs.get("conditions"):
            raise serializers.ValidationError(
                "condition 또는 conditions에 여행 조건이 필요합니다."
            )
        return attrs
