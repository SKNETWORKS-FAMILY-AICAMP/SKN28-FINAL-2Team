from django.db import transaction
from django.shortcuts import get_object_or_404

from drf_spectacular.utils import extend_schema

from rest_framework import permissions, status
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.travel.models import Itinerary, Package

from .models import CartItem, Reservation, ReservationItem
from .serializers import (
    CartItemCreateSerializer,
    CartItemSerializer,
    CartItemUpdateSerializer,
    CartSerializer,
    ReservationCreateSerializer,
    ReservationSerializer,
)


class CartAPIView(APIView):

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Cart"],
        summary="장바구니 조회",
        responses=CartSerializer,
    )
    def get(self, request):
        items = CartItem.objects.filter(
            user=request.user
        )

        serializer = CartItemSerializer(items, many=True)

        total = 0

        for item in items:
            package = Package.objects.using("travel").filter(
                id=item.package_db_id,
                is_active=True,
            ).first()

            if package:
                total += package.estimated_price * item.quantity

        return Response({
            "items": serializer.data,
            "total_price": total,
        })

    @extend_schema(
        tags=["Cart"],
        summary="장바구니 추가",
        request=CartItemCreateSerializer,
        responses=CartItemSerializer,
    )
    def post(self, request):
        serializer = CartItemCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        package_db_id = serializer.validated_data["package_id"]

        item, created = CartItem.objects.get_or_create(
            user=request.user,
            package_db_id=package_db_id,
        )

        return Response(
            CartItemSerializer(item).data,
            status=(
                status.HTTP_201_CREATED
                if created
                else status.HTTP_200_OK
            ),
        )

    @extend_schema(
        tags=["Cart"],
        summary="장바구니 전체 삭제",
        responses={204: None},
    )
    def delete(self, request):
        CartItem.objects.filter(user=request.user).delete()

        return Response(
            status=status.HTTP_204_NO_CONTENT,
        )


class CartItemDetailAPIView(APIView):

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Cart"],
        summary="장바구니 항목 수정",
        request=CartItemUpdateSerializer,
        responses=CartItemSerializer,
    )
    def patch(self, request, pk):
        item = get_object_or_404(
            CartItem,
            pk=pk,
            user=request.user,
        )

        serializer = CartItemUpdateSerializer(
            item,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            CartItemSerializer(item).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        tags=["Cart"],
        summary="장바구니 삭제",
        responses={204: None},
    )
    def delete(self, request, pk):
        item = get_object_or_404(
            CartItem,
            pk=pk,
            user=request.user,
        )
        item.delete()

        return Response(
            status=status.HTTP_204_NO_CONTENT,
        )


class ReservationListCreateAPIView(ListAPIView):

    serializer_class = ReservationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Reservation.objects.filter(
            user=self.request.user
        ).prefetch_related("items")

    @extend_schema(
        tags=["Reservation"],
        summary="예약 생성",
        request=ReservationCreateSerializer,
        responses={
            201: ReservationSerializer,
            400: None,
        },
    )
    @transaction.atomic
    def post(self, request):
        serializer = ReservationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        package_ids = data.get("package_ids")
        cart_item_ids = data.get("cart_item_ids")

        reservation_items_data = []

        if cart_item_ids is not None:
            cart_items = list(
                CartItem.objects.filter(
                    user=request.user,
                    id__in=cart_item_ids,
                )
            )

            package_db_ids = [
                cart_item.package_db_id
                for cart_item in cart_items
            ]

            packages = list(
                Package.objects.using("travel").filter(
                    id__in=package_db_ids,
                    is_active=True,
                )
            )

            package_map = {
                package.id: package
                for package in packages
            }

            for cart_item in cart_items:
                package = package_map.get(cart_item.package_db_id)

                if package is None:
                    continue

                reservation_items_data.append({
                    "package": package,
                    "quantity": cart_item.quantity,
                    "option_date": cart_item.option_date,
                    "option_people": cart_item.option_people,
                })

        elif package_ids:
            packages = list(
                Package.objects.using("travel").filter(
                    id__in=package_ids,
                    is_active=True,
                )
            )

            for package in packages:
                reservation_items_data.append({
                    "package": package,
                    "quantity": 1,
                    "option_date": None,
                    "option_people": 2,
                })

        else:
            cart_items = list(
                CartItem.objects.filter(
                    user=request.user
                )
            )

            package_db_ids = [
                cart_item.package_db_id
                for cart_item in cart_items
            ]

            packages = list(
                Package.objects.using("travel").filter(
                    id__in=package_db_ids,
                    is_active=True,
                )
            )

            package_map = {
                package.id: package
                for package in packages
            }

            for cart_item in cart_items:
                package = package_map.get(cart_item.package_db_id)

                if package is None:
                    continue

                reservation_items_data.append({
                    "package": package,
                    "quantity": cart_item.quantity,
                    "option_date": cart_item.option_date,
                    "option_people": cart_item.option_people,
                })

        if not packages:
            return Response(
                {
                    "detail": (
                        "예약할 패키지가 없습니다. "
                        "장바구니에 패키지를 담거나 "
                        "package_ids를 지정해주세요."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        itinerary = None
        itinerary_id = data.get("itinerary_id")

        if itinerary_id:
            itinerary = get_object_or_404(
                Itinerary,
                pk=itinerary_id,
                user=request.user,
            )

        total_price = sum(
            item["package"].estimated_price * item["quantity"]
            for item in reservation_items_data
        )

        reservation = Reservation.objects.create(
            user=request.user,
            itinerary=itinerary,
            total_price=total_price,
            payment_method=(
                data.get("payment_method")
                or "신용카드 (**** **** **** 1234)"
            ),
            status=Reservation.Status.CONFIRMED,
        )

        ReservationItem.objects.bulk_create([
            ReservationItem(
                reservation=reservation,
                package_db_id=item["package"].id,
                package_id=item["package"].package_id,
                name=item["package"].title,
                price=item["package"].estimated_price,
                quantity=item["quantity"],
                option_date=item["option_date"],
                option_people=item["option_people"],
            )
            for item in reservation_items_data
        ])

        CartItem.objects.filter(
            user=request.user,
            package_db_id__in=[p.id for p in packages],
        ).delete()

        return Response(
            ReservationSerializer(reservation).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema(
    tags=["Reservation"],
    summary="예약 상세 조회",
)
class ReservationDetailAPIView(RetrieveAPIView):

    serializer_class = ReservationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Reservation.objects.filter(
            user=self.request.user
        ).prefetch_related("items")

@extend_schema(
    tags=["Reservation"],
    summary="예약 취소",
    request=None,
    responses={
        200: ReservationSerializer,
        400: None,
        404: None,
    },
)
class ReservationCancelAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, pk):
        reservation = get_object_or_404(
            Reservation.objects.prefetch_related("items"),
            pk=pk,
            user=request.user,
        )

        if reservation.status == Reservation.Status.CANCELLED:
            return Response(
                {"detail": "이미 취소된 예약입니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        reservation.status = Reservation.Status.CANCELLED
        reservation.save(update_fields=["status", "updated_at"])

        return Response(
            ReservationSerializer(reservation).data,
            status=status.HTTP_200_OK,
        )
