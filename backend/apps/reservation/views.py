from django.db import transaction
from django.shortcuts import get_object_or_404

from drf_spectacular.utils import extend_schema

from rest_framework import permissions, status
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.package_recommendation.services import recommend_package_comparison
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
        items = CartItem.objects.filter(user=request.user).select_related("itinerary")

        serializer = CartItemSerializer(items, many=True)

        total = 0

        for item in items:
            if item.product_type == CartItem.ProductType.CUSTOM_ITINERARY:
                total += item.unit_price * item.quantity
                continue

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
        data = serializer.validated_data
        product_type = data["product_type"]
        itinerary = None

        if data.get("itinerary_id"):
            itinerary = get_object_or_404(
                Itinerary,
                pk=data["itinerary_id"],
                user=request.user,
            )

        if product_type == CartItem.ProductType.CUSTOM_ITINERARY:
            if itinerary.status != Itinerary.Status.CONFIRMED:
                return Response(
                    {"detail": "Only confirmed itineraries can be added to the cart."},
                    status=status.HTTP_409_CONFLICT,
                )

            comparison = recommend_package_comparison(
                itinerary.engine_state or {},
                itinerary_id=itinerary.pk,
            )
            custom_package = comparison.get("custom_package")
            if not custom_package:
                return Response(
                    {"detail": "The custom itinerary price could not be calculated."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            item, created = CartItem.objects.get_or_create(
                user=request.user,
                product_type=CartItem.ProductType.CUSTOM_ITINERARY,
                itinerary=itinerary,
                defaults={
                    "package_db_id": None,
                    "product_name": itinerary.title or "Custom itinerary package",
                    "unit_price": int(custom_package["price_per_person"]),
                    "option_date": itinerary.start_date,
                },
            )
        else:
            package = get_object_or_404(
                Package.objects.using("travel"),
                id=data["package_id"],
                is_active=True,
            )
            item, created = CartItem.objects.get_or_create(
                user=request.user,
                product_type=CartItem.ProductType.STORED_PACKAGE,
                package_db_id=package.id,
                defaults={
                    "itinerary": itinerary,
                    "product_name": package.title,
                    "unit_price": package.estimated_price,
                    "option_date": itinerary.start_date if itinerary else None,
                },
            )

        if not created:
            return Response(
                {"detail": "This product is already in the cart."},
                status=status.HTTP_409_CONFLICT,
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
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["include_schedule"] = False
        return context
    
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
        itinerary_id = data.get("itinerary_id")

        # 확정한 자유일정은 기존 예약 화면과 Reservation 모델을 그대로
        # 사용한다. package/cart 식별자가 없는 경우에만 이 분기로 들어온다.
        if itinerary_id and package_ids is None and cart_item_ids is None:
            itinerary = get_object_or_404(
                Itinerary,
                pk=itinerary_id,
                user=request.user,
            )

            if itinerary.status != Itinerary.Status.CONFIRMED:
                return Response(
                    {"detail": "확정된 일정만 예약할 수 있습니다."},
                    status=status.HTTP_409_CONFLICT,
                )

            comparison = recommend_package_comparison(
                itinerary.engine_state or {},
                itinerary_id=itinerary.pk,
            )
            custom_package = comparison.get("custom_package")

            if not custom_package:
                return Response(
                    {"detail": "자유일정 가격을 계산할 수 없습니다."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            price = int(custom_package["price_per_person"])
            reservation = Reservation.objects.create(
                user=request.user,
                itinerary=itinerary,
                total_price=price,
                payment_method=(
                    data.get("payment_method")
                    or "신용카드 (**** **** **** 1234)"
                ),
                status=Reservation.Status.CONFIRMED,
            )
            ReservationItem.objects.create(
                reservation=reservation,
                product_type=CartItem.ProductType.CUSTOM_ITINERARY,
                package_db_id=None,
                package_id=f"CUSTOM-{itinerary.pk}",
                name=itinerary.title or "내가 확정한 자유패키지",
                price=price,
                quantity=1,
                option_date=itinerary.start_date,
                option_people=2,
            )

            return Response(
                ReservationSerializer(
                    reservation,
                    context={"include_schedule": False},
                ).data,
                status=status.HTTP_201_CREATED,
            )

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
                if cart_item.product_type == CartItem.ProductType.CUSTOM_ITINERARY:
                    reservation_items_data.append({
                        "product_type": cart_item.product_type,
                        "package": None,
                        "package_id": f"CUSTOM-{cart_item.itinerary_id}",
                        "name": cart_item.product_name or "Custom itinerary package",
                        "price": cart_item.unit_price,
                        "quantity": cart_item.quantity,
                        "option_date": cart_item.option_date,
                        "option_people": cart_item.option_people,
                        "itinerary": cart_item.itinerary,
                    })
                    continue

                package = package_map.get(cart_item.package_db_id)

                if package is None:
                    continue

                reservation_items_data.append({
                    "product_type": CartItem.ProductType.STORED_PACKAGE,
                    "package": package,
                    "package_id": package.package_id,
                    "name": package.title,
                    "price": package.estimated_price,
                    "quantity": cart_item.quantity,
                    "option_date": cart_item.option_date,
                    "option_people": cart_item.option_people,
                    "itinerary": cart_item.itinerary,
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
                    "product_type": CartItem.ProductType.STORED_PACKAGE,
                    "package": package,
                    "package_id": package.package_id,
                    "name": package.title,
                    "price": package.estimated_price,
                    "quantity": 1,
                    "option_date": None,
                    "option_people": 2,
                    "itinerary": None,
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
                if cart_item.product_type == CartItem.ProductType.CUSTOM_ITINERARY:
                    reservation_items_data.append({
                        "product_type": cart_item.product_type,
                        "package": None,
                        "package_id": f"CUSTOM-{cart_item.itinerary_id}",
                        "name": cart_item.product_name or "Custom itinerary package",
                        "price": cart_item.unit_price,
                        "quantity": cart_item.quantity,
                        "option_date": cart_item.option_date,
                        "option_people": cart_item.option_people,
                        "itinerary": cart_item.itinerary,
                    })
                    continue

                package = package_map.get(cart_item.package_db_id)

                if package is None:
                    continue

                reservation_items_data.append({
                    "product_type": CartItem.ProductType.STORED_PACKAGE,
                    "package": package,
                    "package_id": package.package_id,
                    "name": package.title,
                    "price": package.estimated_price,
                    "quantity": cart_item.quantity,
                    "option_date": cart_item.option_date,
                    "option_people": cart_item.option_people,
                    "itinerary": cart_item.itinerary,
                })

        if not reservation_items_data:
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
        if itinerary_id:
            itinerary = get_object_or_404(
                Itinerary,
                pk=itinerary_id,
                user=request.user,
            )
        elif cart_item_ids is not None:
            itinerary_ids = {
                item["itinerary"].id
                for item in reservation_items_data
                if item.get("itinerary") is not None
            }
            if len(itinerary_ids) == 1:
                itinerary = Itinerary.objects.filter(
                    pk=itinerary_ids.pop(),
                    user=request.user,
                ).first()

        total_price = sum(
            item["price"] * item["quantity"]
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
                product_type=item["product_type"],
                package_db_id=(item["package"].id if item["package"] else None),
                package_id=item["package_id"],
                name=item["name"],
                price=item["price"],
                quantity=item["quantity"],
                option_date=item["option_date"],
                option_people=item["option_people"],
            )
            for item in reservation_items_data
        ])

        if cart_item_ids is not None:
            CartItem.objects.filter(
                user=request.user,
                id__in=cart_item_ids,
            ).delete()
        elif package_ids is None:
            CartItem.objects.filter(user=request.user).delete()

        return Response(
            ReservationSerializer(
                reservation,
                context={"include_schedule": False},
            ).data,
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

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["include_schedule"] = True
        return context

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
            ReservationSerializer(
                reservation,
                context={"include_schedule": False},
            ).data,
            status=status.HTTP_200_OK,
        )