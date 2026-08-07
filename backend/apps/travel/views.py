import copy

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema

from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import RetrieveAPIView
from rest_framework.response import Response


from .models import Itinerary, Package
from .serializers import ( ItineraryRouteSerializer, ItinerarySerializer, 
        ItineraryShareSerializer, ItineraryRevisionSerializer, PackageSerializer,
)
from .services import generate_itinerary, revise_itinerary
from apps.package_recommendation.services import recommend_packages

class PackageViewSet(viewsets.ReadOnlyModelViewSet):

    serializer_class = PackageSerializer
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=["Package"],
        summary="패키지 목록 조회",
        responses=PackageSerializer(many=True),
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        tags=["Package"],
        summary="패키지 상세 조회",
        responses=PackageSerializer,
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def get_queryset(self):
        qs = (
            Package.objects.using("travel")
            .filter(is_active=True)
            .order_by("id")
        )

        duration_days = self.request.query_params.get("duration_days")
        max_price = self.request.query_params.get("max_price")

        if duration_days:
            qs = qs.filter(duration_days=duration_days)

        if max_price:
            qs = qs.filter(estimated_price__lte=max_price)

        return qs

class ItineraryViewSet(viewsets.ModelViewSet):
    queryset = Itinerary.objects.none()  
    serializer_class = ItinerarySerializer
    permission_classes = [permissions.AllowAny]


    @extend_schema(
        tags=["Itinerary"],
        summary="일정 목록 조회",
        responses=ItinerarySerializer(many=True),
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        tags=["Itinerary"],
        summary="일정 상세 조회",
        responses=ItinerarySerializer,
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        tags=["Itinerary"],
        summary="전체 일정 재생성",
        request=None,
        responses={200: ItinerarySerializer},
    )
    
    @action(detail=True, methods=["post"])
    def regenerate(self, request, pk=None):
        itinerary = self.get_object()
        generate_itinerary(itinerary)
        serializer = self.get_serializer(itinerary)
        return Response(serializer.data)
    


    @extend_schema(
    tags=["Itinerary"],
    summary="채팅으로 일정 수정",
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "example": "협재해변도 가고 싶어",
                }
            },
            "required": ["message"],
        }
    },
    responses={200: ItinerarySerializer},
)
    @action(detail=True, methods=["post"])
    def revise(self, request, pk=None):

        itinerary = self.get_object()

        serializer = ItineraryRevisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        revise_itinerary(
            itinerary,
            serializer.validated_data["message"],
        )

        return Response(
            self.get_serializer(itinerary).data,
            status=status.HTTP_200_OK,
        )
    @extend_schema(
        tags=["Itinerary"],
        summary="일정 생성",
        request=ItinerarySerializer,
        responses={201: ItinerarySerializer},
    )
    def create(self, request, *args, **kwargs):

        serializer = self.get_serializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        itinerary = serializer.save(user=request.user)

        generate_itinerary(itinerary)

        serializer = self.get_serializer(itinerary)

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED
        )

    @extend_schema(
        tags=["Itinerary"],
        summary="일정 수정",
        request=ItinerarySerializer,
        responses=ItinerarySerializer,
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(
        tags=["Itinerary"],
        summary="일정 일부 수정",
        request=ItinerarySerializer,
        responses=ItinerarySerializer,
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @extend_schema(
        tags=["Itinerary"],
        summary="일정 삭제",
        responses={204: None},
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)
    

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Itinerary.objects.none()

        return Itinerary.objects.filter(
            user=self.request.user
        ).prefetch_related("days__items")

    @extend_schema(
        tags=["Package Recommendation"],
        summary="생성된 일정에 맞는 패키지 추천",
        responses={200: OpenApiTypes.OBJECT},
    )
    @action(detail=True, methods=["get"], url_path="package-recommendations")
    def package_recommendations(self, request, pk=None):
        itinerary = self.get_object()
        if not itinerary.engine_state:
            return Response(
                {"detail": "추천에 필요한 일정 엔진 상태가 없습니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            top_k = int(request.query_params.get("top_k", 3))
        except (TypeError, ValueError):
            return Response(
                {"detail": "top_k는 정수여야 합니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not 1 <= top_k <= 10:
            return Response(
                {"detail": "top_k는 1부터 10까지 지정할 수 있습니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            recommendation_payload = copy.deepcopy(itinerary.engine_state)
            conditions = recommendation_payload.setdefault("condition", {})
            conditions["start_date"] = itinerary.start_date.isoformat()
            result = recommend_packages(recommendation_payload, top_k=top_k)
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
    
    @extend_schema(
        tags=["Itinerary"],
        summary="여행 경로 조회",
        responses=ItineraryRouteSerializer(many=True)
        )
    
    @action(detail=True, methods=["get"])
    def route(self, request, pk=None):
        """여행 경로 지도 표시 — 일자별 순서대로의 좌표 목록."""
        itinerary = self.get_object()
        result = []
        for day in itinerary.days.all():
            points = [
                {
                    "order": item.order,
                    "title": item.title,
                    "latitude": item.latitude,
                    "longitude": item.longitude,
                }
                for item in day.items.all()
                if item.latitude is not None and item.longitude is not None
            ]
            result.append({"day_number": day.day_number, "points": points})
        return Response(result)

    @extend_schema(
        tags=["Itinerary"],
        summary="일정 공유",

        request=None,
        responses=ItineraryShareSerializer
        )
    @action(detail=True, methods=["post"])
    def share(self, request, pk=None):
        """ 일정 공유 """
        itinerary = self.get_object()
        token = itinerary.ensure_share_token()
        return Response(
            {
                "share_token": str(token),
                "share_path": f"/api/travel/itineraries/shared/{token}/",
            },
            status=status.HTTP_200_OK,
        )


class SharedItineraryAPIView(RetrieveAPIView):
    """공유 링크로 접근하는 읽기 전용 뷰 (로그인 불필요)."""

    serializer_class = ItinerarySerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = "share_token"
    lookup_url_kwarg = "token"
    queryset = Itinerary.objects.exclude(share_token__isnull=True).prefetch_related("days__items")

    @extend_schema(
        tags=["Itinerary"],
        summary="공유 일정 조회",
        responses=ItinerarySerializer,
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
