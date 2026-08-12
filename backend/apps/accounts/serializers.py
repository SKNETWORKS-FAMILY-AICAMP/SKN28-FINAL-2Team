from rest_framework import serializers

from .models import User


class SocialLoginSerializer(serializers.Serializer):
    token = serializers.CharField()

class KakaoLoginSerializer(serializers.Serializer):
    code = serializers.CharField()

class TokenPairSerializer(serializers.Serializer):
    """소셜 로그인 성공 시 응답 형태 (문서화 전용)."""

    access = serializers.CharField()
    refresh = serializers.CharField()


class ErrorSerializer(serializers.Serializer):
    """오류 응답 형태 (문서화 전용)."""

    detail = serializers.CharField()


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class UserMeSerializer(serializers.ModelSerializer):
    """M001-F-003 사용자 정보 관리: 조회/수정용 시리얼라이저."""

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "nickname",
            "profile_image",
            "provider",
            "preferred_style",
            "date_joined",
        )
        read_only_fields = ("id", "email", "provider", "date_joined")