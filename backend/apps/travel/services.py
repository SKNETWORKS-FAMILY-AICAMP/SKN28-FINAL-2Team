from datetime import timedelta
import json
import traceback

from django.db import transaction

from src.api import itinerary_engine
from src.models import ItineraryState
from .models import Itinerary, ItineraryDay, ItineraryItem, Place


def _build_place_coordinate_map(
    state: ItineraryState,
) -> dict[int, tuple[float | None, float | None]]:
    """엔진 상태(state.slots[*].candidates)에서 content_id -> (위도, 경도) 맵을 만든다.

    LLM이 최종 stops에 돌려주는 값은 sequence/title/notes/content_id 뿐이고
    좌표는 포함하지 않으므로(할루시네이션 방지를 위해 일부러 요청하지 않음),
    실제 좌표는 RAG 검색 결과가 담긴 슬롯 후보(candidate.place)에서 가져온다.
    """

    coordinate_map: dict[int, tuple[float | None, float | None]] = {}

    for slot in state.slots:
        for candidate in slot.candidates:
            place = candidate.place or {}

            print(place)   # 추가

            coordinate_map[candidate.content_id] = {
                "latitude": place.get("latitude"),
                "longitude": place.get("longitude"),
                "thumbnail": place.get("image_url")
                    or place.get("thumbnail_url")
                    or "",
            }

    return coordinate_map


def _save_itinerary_result(itinerary: Itinerary, state: ItineraryState):

    result = state.itinerary
    coordinate_map = _build_place_coordinate_map(state)

    # 기존 일정 삭제
    itinerary.days.all().delete()

    for day_data in result.get("days", []):

        itinerary_day = ItineraryDay.objects.create(
            itinerary=itinerary,
            day_number=day_data["day"],
            date=itinerary.start_date
            + timedelta(days=day_data["day"] - 1),
        )

        for stop in day_data.get("stops", []):

            info = coordinate_map.get(
                stop.get("content_id"),
                {
                    "latitude": None,
                    "longitude": None,
                    "thumbnail": "",
                },
            )

            latitude = info["latitude"]
            longitude = info["longitude"]
            thumbnail = info["thumbnail"]

            ItineraryItem.objects.create(
                day=itinerary_day,
                order=stop.get("sequence", 1),
                time=stop.get("start_time", ""),
                item_type=ItineraryItem.ItemType.SPOT,
                title=stop.get("title", ""),
                description=stop.get("notes", ""),
                thumbnail=thumbnail,
                latitude=latitude,
                longitude=longitude,
                cost=0,
                spot=None,
                restaurant=None,
                accommodation=None,
                memo="",
            )

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
        # DB 값 확인
        # -------------------------------------------------
        print("duration_label :", itinerary.duration_label)
        print("companion      :", itinerary.companion_type)
        print("style          :", itinerary.style)

        print(
            "display companion :",
            itinerary.get_companion_type_display(),
        )

        print(
            "display style     :",
            itinerary.get_style_display(),
        )

        # -------------------------------------------------
        # LLM 입력 생성
        # -------------------------------------------------
        user_text = (
            f"{itinerary.duration_label}, "
            f"{itinerary.get_companion_type_display()}, "
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

        # -------------------------------------------------
        # 최종 일정
        # -------------------------------------------------
        result = state.itinerary

        # 이후 채팅 수정에 사용할 엔진 상태 저장
        itinerary.engine_state = state.to_dict()
        itinerary.save(update_fields=["engine_state"])

        print("===== LLM 일정 생성 완료 =====")
        print("최종 JSON")
        print(
            json.dumps(
                result,
                indent=2,
                ensure_ascii=False,
            )
        )

        # -------------------------------------------------
        # DB 저장
        # -------------------------------------------------
        _save_itinerary_result(
            itinerary,
            state,
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

@transaction.atomic
def revise_itinerary(
    itinerary: Itinerary,
    user_text: str,
):
    """
    채팅으로 기존 여행 일정을 수정한다.
    """

    print("=" * 80)
    print("===== revise_itinerary 시작 =====")
    print("=" * 80)

    try:
        if not itinerary.engine_state:
            raise ValueError(
                "엔진 상태가 없습니다. 기존 일정을 다시 생성해주세요."
            )

        # 기존 엔진 상태 복원
        state = ItineraryState.from_dict(
            itinerary.engine_state
        )

        # 엔진을 이용하여 일정 수정
        new_state = itinerary_engine.update_itinerary_from_chat(
            state,
            user_text,
        )

        # 수정된 상태 저장
        itinerary.engine_state = new_state.to_dict()
        itinerary.save(update_fields=["engine_state"])

        # 수정된 일정 저장
        _save_itinerary_result(
            itinerary,
            new_state,
        )

        print("=" * 80)
        print("===== revise_itinerary 완료 =====")
        print("=" * 80)

        return itinerary

    except Exception as e:
        print("=" * 80)
        print("===== revise_itinerary 실패 =====")
        print("Exception :", e)
        traceback.print_exc()
        print("=" * 80)
        raise