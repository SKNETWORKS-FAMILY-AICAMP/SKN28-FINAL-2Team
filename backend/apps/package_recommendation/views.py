from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import PackageRecommendationRequestSerializer
from .services import recommend_packages


class PackageRecommendationAPIView(APIView):
    """Recommend stored packages for a completed itinerary RAG response."""

    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Package Recommendation"],
        summary="일정과 가장 유사한 여행 패키지 추천",
        request=PackageRecommendationRequestSerializer,
        responses={
            200: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT,
            503: OpenApiTypes.OBJECT,
        },
    )
    def post(self, request):
        serializer = PackageRecommendationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = dict(serializer.validated_data)
        top_k = int(payload.pop("top_k", 3))
        try:
            result = recommend_packages(payload, top_k=top_k)
        except (TypeError, ValueError) as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except RuntimeError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(result, status=status.HTTP_200_OK)
