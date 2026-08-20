import copy

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema

from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Itinerary, Package
from .serializers import (
    ItineraryRouteSerializer,
    ItinerarySerializer,
    ItineraryShareSerializer,
    ItineraryRevisionSerializer,
    PackageSerializer,
    PackageListSerializer,
)
from .services import (
    generate_itinerary,
    prepare_itinerary_for_edit,
    revise_itinerary,
)
from .kakao_route_service import get_kakao_day_route_path

from apps.package_recommendation.services import recommend_package_comparison

class PackageViewSet(viewsets.ReadOnlyModelViewSet):

    serializer_class = PackageSerializer
    permission_classes = [permissions.AllowAny]

    def get_serializer_class(self):
        if self.action == "list":
            return PackageListSerializer
        return PackageSerializer

    @extend_schema(
        tags=["Package"],
        summary="패키지 목록 조회",
        responses=PackageListSerializer(many=True),
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
    permission_classes = [IsAuthenticated]

    @staticmethod
    def _confirmed_edit_response():
        return Response(
            {"detail": "확정된 일정은 수정할 수 없습니다."},
            status=status.HTTP_409_CONFLICT,
        )


    @extend_schema(
        tags=["Itinerary"],
        summary="일정 목록 조회",
        responses=ItinerarySerializer(many=True),
    )
    def list(self, request, *args, **kwargs):
        queryset = (
            self.get_queryset()
            .filter(status=Itinerary.Status.CONFIRMED)
        )

        serializer = self.get_serializer(
            queryset,
            many=True,
        )

        return Response(serializer.data)

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
        if itinerary.status == Itinerary.Status.CONFIRMED:
            return self._confirmed_edit_response()

        generate_itinerary(itinerary)
        serializer = self.get_serializer(itinerary)
        return Response(serializer.data)
    


    @extend_schema(
        tags=["Itinerary"],
        summary="채팅으로 일정 수정",
        request=ItineraryRevisionSerializer,
        responses={200: OpenApiTypes.OBJECT},
    )
    
    @action(detail=True, methods=["post"])
    def revise(self, request, pk=None):
        itinerary = self.get_object()
        if itinerary.status == Itinerary.Status.CONFIRMED:
            return self._confirmed_edit_response()

        serializer = ItineraryRevisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        itinerary, chat_result = revise_itinerary(
            itinerary,
            serializer.validated_data["message"],
        )

        if chat_result.mode == "recommend":
            # 일정은 그대로다. 채팅창에만 후보를 보여준다.
            return Response(
                {
                    "mode": "recommend",
                    "message": chat_result.message,
                    "options": chat_result.recommendations,
                },
                status=status.HTTP_200_OK,
            )

        if chat_result.mode == "no_change":
            return Response(
                {
                    "mode": "no_change",
                    "message": "요청에서 변경할 내용을 찾지 못했어요. 조금 더 구체적으로 말씀해주세요.",
                },
                status=status.HTTP_200_OK,
            )

        # mode == "edit": 일정이 실제로 갱신되었다.
        data = self.get_serializer(itinerary).data
        data["mode"] = "edit"
        return Response(
            data,
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

        additional_request = serializer.validated_data.get("additional_request", "")
        itinerary = serializer.save(user=request.user)

        generate_itinerary(
            itinerary,
            additional_request=additional_request,
        )

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
        if self.get_object().status == Itinerary.Status.CONFIRMED:
            return self._confirmed_edit_response()
        return super().update(request, *args, **kwargs)

    @extend_schema(
        tags=["Itinerary"],
        summary="일정 일부 수정",
        request=ItinerarySerializer,
        responses=ItinerarySerializer,
    )
    def partial_update(self, request, *args, **kwargs):
        if self.get_object().status == Itinerary.Status.CONFIRMED:
            return self._confirmed_edit_response()
        return super().partial_update(request, *args, **kwargs)

    @extend_schema(
        tags=["Itinerary"],
        summary="일정 편집 준비",
        request=None,
        responses={200: OpenApiTypes.OBJECT},
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="prepare-edit",
    )
    def prepare_edit(self, request, pk=None):
        itinerary, copied = prepare_itinerary_for_edit(
            self.get_object()
        )
        data = self.get_serializer(itinerary).data
        data["copied"] = copied
        return Response(data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Itinerary"],
        summary="일정 확정",
        request=None,
        responses={200: ItinerarySerializer},
    )
    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        itinerary = self.get_object()

        if not itinerary.engine_state:
            return Response(
                {"detail": "확정할 일정 데이터가 없습니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if itinerary.status != Itinerary.Status.CONFIRMED:
            itinerary.status = Itinerary.Status.CONFIRMED
            itinerary.save(update_fields=["status", "updated_at"])

        return Response(
            self.get_serializer(itinerary).data,
            status=status.HTTP_200_OK,
        )

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

        return (
            Itinerary.objects
            .filter(user=self.request.user)
            .order_by("-id")
        )
    @extend_schema(
        tags=["Package Recommendation"],
        summary="생성된 일정에 맞는 패키지 추천",
        responses={200: OpenApiTypes.OBJECT},
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="package-recommendations",
    )
    def package_recommendations(self, request, pk=None):
        itinerary = self.get_object()

        if itinerary.status != Itinerary.Status.CONFIRMED:
            return Response(
                {"detail": "일정을 먼저 확정해주세요."},
                status=status.HTTP_409_CONFLICT,
            )

        if not itinerary.engine_state:
            return Response(
                {"detail": "추천에 필요한 일정 엔진 상태가 없습니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            recommendation_payload = copy.deepcopy(itinerary.engine_state)
            conditions = recommendation_payload.setdefault("condition", {})
            conditions["start_date"] = itinerary.start_date.isoformat()
            result = recommend_package_comparison(
                recommendation_payload,
                itinerary_id=itinerary.pk,
            )
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

        return Response(
            result,
            status=status.HTTP_200_OK,
        )
    
    @extend_schema(
        tags=["Itinerary"],
        summary="여행 경로 조회",
        responses=ItineraryRouteSerializer(many=True)
        )
    
    @action(detail=True, methods=["get"])
    def route(self, request, pk=None):
        """
        여행 경로 지도 표시.

        - OR-Tools로 최적화되어 저장된 방문 순서를 사용
        - 각 장소의 좌표를 points로 반환
        - Kakao Directions API는 호출하지 않는다.
        """

        itinerary = self.get_object()
        result = []

        for day in itinerary.days.all().order_by("day_number"):

            items = list(
                day.items
                .filter(
                    latitude__isnull=False,
                    longitude__isnull=False,
                )
                .order_by("order")
            )

            points = [
                {
                    "order": item.order,
                    "title": item.title,
                    "latitude": float(item.latitude),
                    "longitude": float(item.longitude),
                }
                for item in items
            ]

            result.append(
                {
                    "day_number": day.day_number,
                    "points": points,
                    "path": [],
                }
            )

        return Response(result)

    @extend_schema(
        tags=["Itinerary"],
        summary="실제 자동차 도로 경로 조회",
        responses=ItineraryRouteSerializer(many=True),
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="road-route",
    )
    def road_route(self, request, pk=None):
        """
        확정된 일정의 실제 자동차 도로 경로 조회.

        - package_id가 없으면 자유일정 경로 조회
        - package_id가 있으면 추천 패키지 경로 조회
        - 저장된 방문 순서를 그대로 사용
        - 하루 일정당 Kakao Directions API 1회 호출
        """

        itinerary = self.get_object()

        if itinerary.status != Itinerary.Status.CONFIRMED:
            return Response(
                {
                    "detail": (
                        "확정된 일정에서만 "
                        "실제 경로를 조회할 수 있습니다."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )

        package_id = request.query_params.get("package_id")

        result = []

        # =========================================================
        # 추천 패키지 실제 경로
        # =========================================================
        if package_id:
            try:
                package = (
                    Package.objects
                    .using("travel")
                    .get(
                        pk=package_id,
                        is_active=True,
                    )
                )
            except Package.DoesNotExist:
                return Response(
                    {
                        "detail": (
                            "추천 패키지를 찾을 수 없습니다."
                        )
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )

            package_data = PackageSerializer(package).data

            course = package_data.get("course") or []

            for day_index, day in enumerate(course):
                day_number = int(
                    day.get("day") or day_index + 1
                )

                items = day.get("items") or []

                points = []

                for item in items:
                    latitude = item.get("latitude")
                    longitude = item.get("longitude")

                    if (
                        latitude is None
                        or longitude is None
                    ):
                        continue

                    points.append(
                        {
                            "order": item.get("sequence"),
                            "title": item.get("title"),
                            "latitude": float(latitude),
                            "longitude": float(longitude),
                        }
                    )

                try:
                    path = get_kakao_day_route_path(
                        points
                    )

                except (ValueError, RuntimeError) as exc:
                    return Response(
                        {
                            "detail": str(exc),
                            "day_number": day_number,
                        },
                        status=(
                            status.HTTP_503_SERVICE_UNAVAILABLE
                        ),
                    )

                result.append(
                    {
                        "day_number": day_number,
                        "points": points,
                        "path": path,
                    }
                )

            return Response(
                result,
                status=status.HTTP_200_OK,
            )

        # =========================================================
        # 자유일정 실제 경로
        # =========================================================
        for day in (
            itinerary.days
            .all()
            .order_by("day_number")
        ):
            items = list(
                day.items
                .filter(
                    latitude__isnull=False,
                    longitude__isnull=False,
                )
                .order_by("order")
            )

            points = [
                {
                    "order": item.order,
                    "title": item.title,
                    "latitude": float(item.latitude),
                    "longitude": float(item.longitude),
                }
                for item in items
            ]

            try:
                path = get_kakao_day_route_path(
                    points
                )

            except (ValueError, RuntimeError) as exc:
                return Response(
                    {
                        "detail": str(exc),
                        "day_number": day.day_number,
                    },
                    status=(
                        status.HTTP_503_SERVICE_UNAVAILABLE
                    ),
                )

            result.append(
                {
                    "day_number": day.day_number,
                    "points": points,
                    "path": path,
                }
            )

        return Response(
            result,
            status=status.HTTP_200_OK,
        )

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
