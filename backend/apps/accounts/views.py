from django.conf import settings

from drf_spectacular.utils import extend_schema

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

from .serializers import ErrorSerializer, LogoutSerializer, SocialLoginSerializer, KakaoLoginSerializer, TokenPairSerializer, UserMeSerializer
from .models import User


from .services import google_login, kakao_login, get_kakao_access_token


class DevLoginAPIView(APIView):

    permission_classes = [AllowAny]

    def post(self, request):
        if not settings.DEBUG:
            return Response(status=status.HTTP_404_NOT_FOUND)

        user, _ = User.objects.get_or_create(
            email="developer@local.test",
            defaults={
                "nickname": "개발 사용자",
                "provider": "google",
                "provider_id": "local-development-user",
            },
        )
        refresh = RefreshToken.for_user(user)

        return Response(
            {"access": str(refresh.access_token), "refresh": str(refresh)},
            status=status.HTTP_200_OK,
        )

class GoogleLoginAPIView(APIView):

    @extend_schema(
        tags=["Accounts"],
        summary="Google 로그인",
        request=SocialLoginSerializer,
        responses={200: TokenPairSerializer, 400: ErrorSerializer},
    )
    def post(self, request):
        serializer = SocialLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            user = google_login(serializer.validated_data["token"])

            refresh = RefreshToken.for_user(user)

            return Response(
                {
                    "access": str(refresh.access_token),
                    "refresh": str(refresh),
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {
                    "detail": str(e),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )


class KakaoLoginAPIView(APIView):

    @extend_schema(
        tags=["Accounts"],
        summary="Kakao 로그인",
        request=KakaoLoginSerializer,
        responses={200: TokenPairSerializer, 400: ErrorSerializer},
    )
    def post(self, request):
        serializer = KakaoLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            access_token = get_kakao_access_token(
                serializer.validated_data["code"]
            )

            user = kakao_login(access_token)

            refresh = RefreshToken.for_user(user)

            return Response(
                {
                    "access": str(refresh.access_token),
                    "refresh": str(refresh),
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {
                    "detail": str(e),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )


class LogoutAPIView(APIView):

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Accounts"],
        summary="로그아웃",    
        request=LogoutSerializer,
        responses={205: None, 400: ErrorSerializer},
    )
    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            token = RefreshToken(serializer.validated_data["refresh"])
            token.blacklist()
        except TokenError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(status=status.HTTP_205_RESET_CONTENT)


class MeAPIView(APIView):

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Accounts"],
        summary="내 정보 조회",
        responses=UserMeSerializer
        )
    
    def get(self, request):
        serializer = UserMeSerializer(request.user)
        return Response(serializer.data)

    @extend_schema(
        tags=["Accounts"],
        summary="내 정보 수정",
        request=UserMeSerializer,
        responses=UserMeSerializer
        )
    def patch(self, request):
        serializer = UserMeSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
