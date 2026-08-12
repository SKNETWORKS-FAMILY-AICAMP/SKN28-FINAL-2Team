from datetime import timedelta
import traceback
import json

from django.db import transaction

from src.api import itinerary_engine
from src.models import ItineraryState
from .models import Itinerary, ItineraryDay, ItineraryItem, Place
from .route_optimizer import optimize_stops

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


def _optimize_itinerary_routes(
    state: ItineraryState,
    *,
    skip_days: set[int] | frozenset[int] = frozenset(),
):
    """장소 좌표를 보완한 뒤 날짜별 방문 순서를 OR-Tools로 최적화한다.

    ``skip_days`` 에 포함된 day는 경로 최적화(거리 기준 재정렬)를 건너뛴다.
    채팅 엔진이 "A 다음에 B"처럼 순서를 코드 레벨에서 이미 확정한 day가
    여기에 해당한다 - 좌표는 채워주되 순서는 건드리지 않는다.

    카카오 자동차 길찾기는 출발지/도착지가 5m 이내로 붙어있으면 실패하는 등
    외부 API 오류가 날 수 있다. 이 함수는 그런 경우에도 절대 예외를 밖으로
    던지지 않는다 - 최적화만 건너뛰고, 수정된 일정 자체는 그대로 저장되도록
    한다 (경로 최적화 실패가 사용자의 수정 요청 자체를 날려버리면 안 된다).
    """
    place_info_map = _build_place_info_map(state)
    days = state.itinerary.get("days", [])
    content_ids = {
        stop.get("content_id")
        for day in days
        for stop in day.get("stops", [])
        if stop.get("content_id")
    }
    places = {
        place.content_id: place
        for place in Place.objects.using("travel").filter(content_id__in=content_ids)
    }

    for day in days:
        stops = day.get("stops", [])
        for stop in stops:
            content_id = stop.get("content_id")
            place = places.get(content_id)
            fallback = place_info_map.get(content_id, {})
            latitude = place.latitude if place else fallback.get("latitude")
            longitude = place.longitude if place else fallback.get("longitude")
            stop["latitude"] = float(latitude) if latitude is not None else None
            stop["longitude"] = float(longitude) if longitude is not None else None

        if not stops:
            continue

        day_number = day.get("day")
        if day_number in skip_days:
            print(
                f"[route] {day_number}일차는 위치 지정 삽입으로 순서가 "
                "이미 확정되어 경로 최적화를 건너뜁니다."
            )
            continue

        try:
            day["stops"] = optimize_stops(stops)
        except Exception as exc:
            # 카카오 길찾기 실패(예: "출발지와 도착지가 5m 이내") 등으로
            # 최적화 자체가 실패해도, 이미 수정된 일정(stops)은 그대로
            # 유지한 채 최적화만 건너뛴다. 여기서 예외를 다시 던지면
            # /revise/ 요청 전체가 500이 되어 사용자의 수정 내용이
            # 통째로 사라진다.
            print(
                f"[route] {day_number}일차 경로 최적화 실패 -> "
                f"최적화를 건너뛰고 기존 순서를 유지합니다: {exc}"
            )
            traceback.print_exc()


def _save_itinerary_result(
    itinerary: Itinerary,
    state: ItineraryState,
):
    result = state.itinerary
    place_info_map = _build_place_info_map(state)

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
                latitude=latitude,
                longitude=longitude,
                spot=None,
                restaurant=None,
                accommodation=None,
                memo="",
            )

@transaction.atomic
def generate_itinerary(itinerary: Itinerary):

    itinerary.title = (
        f"{itinerary.duration_label} "
        f"{itinerary.get_companion_type_display()} "
        f"{itinerary.style} "
    )
    itinerary.save(update_fields=["title"])

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

        # 카카오 자동차 이동시간을 기준으로 날짜별 방문 순서를 최적화한다.
        _optimize_itinerary_routes(state)

        # -------------------------------------------------
        # 최종 일정
        # -------------------------------------------------
        result = state.itinerary

        itinerary.engine_state = state.to_dict()
        itinerary.save(update_fields=["engine_state"])

        print("===== LLM 일정 생성 완료 =====")

        print("최종 JSON")
        print(json.dumps(result, indent=2, ensure_ascii=False))

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
    채팅으로 기존 여행 일정을 수정하거나, 아직 적용하지 않고 후보만 보여준다.

    반환값은 (itinerary, chat_result) 튜플이다. chat_result.mode 가
    - "recommend" 이면 itinerary는 전혀 수정되지 않았고, chat_result에 담긴
      추천 후보만 화면(채팅창)에 보여주면 된다.
    - "edit" 이면 itinerary가 실제로 갱신된 것이다.
    - "no_change" 이면 사용자의 메시지에서 아무 변경 신호도 찾지 못한 것이다.
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

        # 엔진을 이용하여 일정 수정 (또는 추천만 조회)
        chat_result = itinerary_engine.update_itinerary_from_chat(state, user_text)

        if chat_result.mode != "edit":

            if chat_result.mode == "recommend":
                itinerary.engine_state = chat_result.state.to_dict()
                itinerary.save(
                    update_fields=["engine_state"]
                )

            print("=" * 80)
            print(
                f"===== revise_itinerary 완료 "
                f"(mode={chat_result.mode}, 일정 미변경) ====="
            )
            print("=" * 80)

            return itinerary, chat_result


        new_state = chat_result.state

        _optimize_itinerary_routes(
            new_state,
            skip_days=set(chat_result.locked_days),
        )

        itinerary.engine_state = new_state.to_dict()
        itinerary.save(update_fields=["engine_state"])

        _save_itinerary_result(
            itinerary,
            new_state,
        )

        print("=" * 80)
        print("===== revise_itinerary 완료 =====")
        print("=" * 80)

        return itinerary, chat_result
        
    except Exception as e:

        print("=" * 80)
        print("===== revise_itinerary 실패 =====")
        print("Exception :", e)
        traceback.print_exc()
        print("=" * 80)
        raise