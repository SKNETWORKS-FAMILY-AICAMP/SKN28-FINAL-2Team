from datetime import timedelta
from copy import deepcopy
import json
import traceback

from django.db import transaction

from src.api import itinerary_engine
from src.models import ItineraryState
from .models import Itinerary, ItineraryDay, ItineraryItem, Place
from .route_optimizer import optimize_stops


def _merge_schedule_into_engine_state(
    state: dict,
    schedule: list[dict],
) -> dict:
    merged = deepcopy(state)
    existing_days = {
        int(day["day"]): day
        for day in merged.get("itinerary", {}).get("days", [])
    }
    existing_stops = {
        (day_number, int(stop["sequence"])): stop
        for day_number, day in existing_days.items()
        for stop in day.get("stops", [])
    }
    retained_keys: set[tuple[int, int]] = set()
    merged_days = []

    for scheduled_day in schedule:
        day_number = int(scheduled_day["day"])
        day = deepcopy(existing_days.get(day_number, {"day": day_number}))
        day.update(
            {
                key: deepcopy(value)
                for key, value in scheduled_day.items()
                if key != "stops"
            }
        )
        stops = []
        for scheduled_stop in scheduled_day.get("stops", []):
            key = (day_number, int(scheduled_stop["sequence"]))
            stop = deepcopy(existing_stops.get(key, {}))
            stop.update(deepcopy(scheduled_stop))
            stops.append(stop)
            retained_keys.add(key)
        day["stops"] = stops
        merged_days.append(day)

    merged.setdefault("itinerary", {})["days"] = merged_days
    merged["slots"] = [
        slot
        for slot in merged.get("slots", [])
        if (int(slot["day"]), int(slot["sequence"])) in retained_keys
    ]
    merged["used_content_ids"] = list(
        dict.fromkeys(
            int(stop["content_id"])
            for day in merged_days
            for stop in day.get("stops", [])
            if stop.get("content_id") is not None
        )
    )
    return merged

def _build_place_info_map(
    state: ItineraryState,
) -> dict[int, dict]:
    place_info_map = {}

    for slot in state.slots:
        for candidate in slot.candidates:
            place = candidate.place or {}

            place_info_map[candidate.content_id] = {
                "latitude": place.get("latitude"),
                "longitude": place.get("longitude"),
                "thumbnail": (
                    place.get("image_url")
                    or place.get("thumbnail_url")
                    or ""
                ),
            }

    return place_info_map

def _attach_coordinates_to_stops(
    state: ItineraryState,
):
    """
    OR-Tools 실행 전에 각 stop에 latitude / longitude를 붙인다.
    """

    place_info_map = _build_place_info_map(state)

    for day_data in state.itinerary.get("days", []):
        for stop in day_data.get("stops", []):
            content_id = stop.get("content_id")

            if not content_id:
                continue

            place = (
                Place.objects.using("travel")
                .filter(content_id=content_id)
                .first()
            )

            place_info = place_info_map.get(
                content_id,
                {
                    "latitude": None,
                    "longitude": None,
                },
            )

            latitude = (
                place.latitude
                if place
                else place_info.get("latitude")
            )

            longitude = (
                place.longitude
                if place
                else place_info.get("longitude")
            )

            stop["latitude"] = (
                float(latitude)
                if latitude is not None
                else None
            )

            stop["longitude"] = (
                float(longitude)
                if longitude is not None
                else None
            )


def _optimize_itinerary_routes(
    state: ItineraryState,
):
    """
    각 날짜별 일정의 장소 순서를 OR-Tools로 최적화한다.
    """

    # 먼저 stop에 좌표 추가
    _attach_coordinates_to_stops(state)

    for day_data in state.itinerary.get("days", []):
        stops = day_data.get("stops", [])

        if not stops:
            continue

        print("=" * 80)
        print(
            f"[OR-Tools] DAY {day_data.get('day')} 최적화 전"
        )

        for stop in stops:
            print(
                stop.get("sequence"),
                stop.get("title"),
                stop.get("latitude"),
                stop.get("longitude"),
            )

        optimized_stops = optimize_stops(stops)

        day_data["stops"] = optimized_stops

        print(
            f"[OR-Tools] DAY {day_data.get('day')} 최적화 완료"
        )
        print("=" * 80)

def _save_itinerary_result(
    itinerary: Itinerary,
    state: ItineraryState,
):
    result = state.itinerary
    place_info_map = _build_place_info_map(state)

    # 기존 일정 삭제
    itinerary.days.all().delete()

    for day_data in result.get("days", []):
        day_number = day_data.get("day")

        if day_number is None:
            continue

        itinerary_day = ItineraryDay.objects.create(
            itinerary=itinerary,
            day_number=day_number,
            date=itinerary.start_date
            + timedelta(days=day_number - 1),
        )

        for stop in day_data.get("stops", []):
            content_id = stop.get("content_id")
            place = None

            if content_id:
                place = (
                    Place.objects.using("travel")
                    .filter(content_id=content_id)
                    .first()
                )

            place_info = place_info_map.get(
                content_id,
                {
                    "latitude": None,
                    "longitude": None,
                    "thumbnail": "",
                },
            )

            latitude = (
                place.latitude
                if place
                else place_info["latitude"]
            )

            longitude = (
                place.longitude
                if place
                else place_info["longitude"]
            )

            thumbnail = (
                stop.get("image_url")
                or stop.get("thumbnail_url")
                or stop.get("thumbnail")
                or place_info["thumbnail"]
                or ""
            )
            print(
                "장소 조회:",
                content_id,
                place.title if place else "없음",
                latitude,
                longitude,
                thumbnail,
            )
            role = stop.get("role")

            item_type_map = {
                "visit": ItineraryItem.ItemType.SPOT,
                "food": ItineraryItem.ItemType.RESTAURANT,
                "shopping": ItineraryItem.ItemType.SHOPPING,
                "activity": ItineraryItem.ItemType.ACTIVITY,
                "accommodation": ItineraryItem.ItemType.ACCOMMODATION,
            }

            item_type = item_type_map.get(
                role,
                ItineraryItem.ItemType.SPOT,
            )

            print(
                "[ITEM TYPE]",
                "role =", role,
                "→ item_type =", item_type,
            )

            ItineraryItem.objects.create(
                day=itinerary_day,
                order=stop.get("sequence", 1),
                time=stop.get("start_time", ""),
                item_type=item_type,
                title=stop.get("title", ""),
                description=stop.get("notes", ""),
                thumbnail=thumbnail,
                latitude=round(latitude, 6) if latitude is not None else None,
                longitude=round(longitude, 6) if longitude is not None else None,
                spot=None,
                restaurant=None,
                accommodation=None,
                memo="",
            )
@transaction.atomic
def generate_itinerary(
    itinerary: Itinerary,
    additional_request: str = "",
):

    """
    사용자 입력을 이용하여

    1. TravelCondition 생성
    2. AIHub 일정 구조 생성
    3. RAG 검색
    4. Planner 후처리
    5. LLM 일정 생성
    6. Django DB 저장
    """

    itinerary.title = (
        f"{itinerary.duration_label} "
        f"{itinerary.get_companion_type_display()} 여행"
    )
    itinerary.save(update_fields=["title"])


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
            itinerary.style,
        )

        # -------------------------------------------------
        # LLM 입력 생성
        #
        # 여행 스타일(itinerary.style)은 미리 정해둔 카테고리로 필터링하지
        # 않는다. 사용자가 자유 입력한 텍스트를 그대로 user_text에 포함시켜
        # LLM의 extract_travel_condition이 선호 방문유형/목적/필수 방문지 등을
        # 직접 추출하게 하고, 그 결과가 RAG 검색 쿼리(generate_style_query)에
        # 반영되어 관광지 후보를 찾아오도록 한다. AIHub 참고 여행 매칭
        # (나이대/기간/동행)에는 style 값을 사용하지 않는다.
        # -------------------------------------------------
        user_text = (
            f"{itinerary.duration_label}, "
            f"{itinerary.get_companion_type_display()}, "
            f"{itinerary.age_group}대"
        )
        if additional_request.strip():
            user_text = f"{user_text}, 추가 요청: {additional_request.strip()}"

        if itinerary.style:
            user_text = f"{user_text}, {itinerary.style}"

        print("=" * 80)
        print("User Input :", user_text)
        print("repr(User Input) :", repr(user_text))
        print("=" * 80)

        # -------------------------------------------------
        # 전체 파이프라인 실행
        # -------------------------------------------------
        state = itinerary_engine.create_itinerary(user_text)

        # -------------------------------------------------
        # OR-Tools 경로 최적화
        # -------------------------------------------------
        _optimize_itinerary_routes(state)

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
        new_state = (
            itinerary_engine.update_itinerary_from_chat(
                state,
                user_text,
            )
        )

        # 수정된 일정도 다시 최적 경로 계산
        _optimize_itinerary_routes(new_state)

        # 수정된 엔진 상태 저장
        itinerary.engine_state = new_state.to_dict()
        itinerary.save(update_fields=["engine_state"])

        # 수정된 일정 DB 저장
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
