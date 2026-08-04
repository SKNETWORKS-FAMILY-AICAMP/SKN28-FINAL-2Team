from datetime import timedelta
import traceback
import json

from django.db import transaction

from src.api import itinerary_engine

from .models import Itinerary, ItineraryDay, ItineraryItem, Place


@transaction.atomic
def generate_itinerary(itinerary: Itinerary):
    """
    사용자 입력을 이용하여

    1. TravelCondition 생성
    2. AIHub 일정 구조 생성
    3. RAG 검색
    4. Planner 후처리
    5. LLM 일정 생성
    6. Django DB 저장
    """

    print("=" * 80)
    print("===== generate_itinerary 시작 =====")

    try:
        # -------------------------------------------------
        # 기존 일정 삭제
        # -------------------------------------------------
        itinerary.days.all().delete()

        # -------------------------------------------------
        # DB 값 확인
        # -------------------------------------------------
        print("duration_label :", itinerary.duration_label)
        print("companion      :", itinerary.companion_type)
        print("transport      :", itinerary.transport)
        print("style          :", itinerary.style)

        print("display companion :", itinerary.get_companion_type_display())
        print("display transport :", itinerary.get_transport_display())
        print("display style     :", itinerary.get_style_display())

        # -------------------------------------------------
        # LLM 입력 생성
        # -------------------------------------------------
        user_text = (
            f"{itinerary.duration_label}, "
            f"{itinerary.get_companion_type_display()}, "
            f"{itinerary.get_transport_display()}, "
            f"{itinerary.get_style_display()}"
        )

        print("=" * 80)
        print("User Input :", user_text)
        print("repr(User Input) :", repr(user_text))
        print("=" * 80)

        # -------------------------------------------------
        # 전체 파이프라인 실행
        # -------------------------------------------------
        state = itinerary_engine.create_itinerary(user_text)

        print("=" * 80)
        print("Engine 실행 완료")
        print("=" * 80)

        # -------------------------------------------------
        # 최종 일정
        # -------------------------------------------------
        result = state.itinerary

        print("===== LLM 일정 생성 완료 =====")

        print("최종 JSON")
        print(json.dumps(result, indent=2, ensure_ascii=False))

        # -------------------------------------------------
        # DB 저장
        # -------------------------------------------------
        for day_data in result.get("days", []):

            itinerary_day = ItineraryDay.objects.create(
                itinerary=itinerary,
                day_number=day_data["day"],
                date=itinerary.start_date
                + timedelta(days=day_data["day"] - 1),
            )
            for stop in day_data.get("stops", []):
                content_id = stop.get("content_id")

                place = None

                if content_id:
                    place = Place.objects.using("travel").filter(
                        content_id=content_id
                    ).first()

                latitude = place.latitude if place else None
                longitude = place.longitude if place else None

                print(
                    "장소 조회:",
                    content_id,
                    place.title if place else "없음",
                    latitude,
                    longitude,
                )

                ItineraryItem.objects.create(
                    day=itinerary_day,
                    order=stop.get("sequence", 1),
                    time=stop.get("start_time", ""),
                    item_type=ItineraryItem.ItemType.SPOT,
                    title=stop.get("title", ""),
                    description=stop.get("notes", ""),
                    thumbnail="",
                    latitude=latitude,
                    longitude=longitude,
                    cost=0,
                    spot=None,
                    restaurant=None,
                    accommodation=None,
                    memo="",
                )

        print("=" * 80)
        print("===== generate_itinerary 완료 =====")
        print("=" * 80)

        return itinerary

    except Exception as e:
        print("=" * 80)
        print("===== generate_itinerary 실패 =====")
        print("Exception :", e)
        traceback.print_exc()
        print("=" * 80)
        raise