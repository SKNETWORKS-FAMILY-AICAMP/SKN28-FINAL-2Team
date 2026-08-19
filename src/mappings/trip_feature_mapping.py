"""
통합 조회의 행 기준은 ``travel_id``로 두고, 사람 검색을 위해 ``traveler_id``도
함께 보존한다. 현재 적재본에서는 두 ID가 1:1이지만 동반자·방문·이동 테이블은
모두 ``travel_id``로 연결된다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Iterable, Literal
from src.models.enums import PartyType, VisitPreference


CompanionType = Literal["solo", "friend", "couple", "family"]
SlotRole = Literal["visit", "activity", "food", "shopping"]


# ---------------------------------------------------------------------------
# 통합 조회에 포함할 필드와 원본
# ---------------------------------------------------------------------------

TRIP_FEATURE_SOURCES: Final[dict[str, str]] = {
    "travel_id": "aihub_travel.travel_id",
    "traveler_id": "aihub_travel.traveler_id",
    "travel_start_date": "aihub_travel.travel_start_ymd",
    "travel_end_date": "aihub_travel.travel_end_ymd",
    "duration_days": "travel_start_ymd와 travel_end_ymd로 계산",
    "companion_count": "aihub_traveller.travel_companions_num",
    "travel_status_accompany": "aihub_traveller.travel_status_accompany",
    "relation_codes": "aihub_companion.rel_cd를 travel_id별 집계",
    "relation_names": "aihub_code_b의 TCR 그룹으로 rel_cd 해석",
    "companion_type": "동반자 통합 규칙으로 파생",
    "travel_style_codes": "aihub_traveller.travel_styl_1 ~ travel_styl_8",
    "travel_style_labels": "aihub_code_b의 TSY 그룹으로 스타일 코드 해석",
    "visit_type_codes": "aihub_visit.visit_area_type_cd를 travel_id별 집계",
    "visit_type_names": "aihub_code_b의 VIS 그룹으로 방문 유형 해석",
    "visit_type_counts": "visit_area_type_cd별 방문 횟수 집계",
    "main_visit_type": "가장 많이 등장한 추천 가능 방문 유형",
}


# ---------------------------------------------------------------------------
# 동반자 관계: Code B의 TCR 그룹
# ---------------------------------------------------------------------------

TCR_LABELS: Final[dict[str, str]] = {
    "1": "배우자",
    "2": "자녀",
    "3": "부모",
    "4": "조부모",
    "5": "형제/자매",
    "6": "친인척",
    "7": "친구",
    "8": "연인",
    "9": "동료",
    "10": "친목 단체/모임",
    "11": "기타",
}

# 사용자 선택 항목은 solo/friend/couple/family 네 가지로 단순화한다.
# - 기타(11)는 분류와 RAG 조건에서 제외한다.
# - 동료(9), 친목 단체/모임(10)은 친구 여행에 포함한다.
# - 친인척(6)은 가족 여행에 포함한다.
COMPANION_TYPE_BY_RELATION_CODE: Final[dict[str, CompanionType | None]] = {
    "1": "couple",
    "2": "family",
    "3": "family",
    "4": "family",
    "5": "friend",
    "6": "family",
    "7": "friend",
    "8": "couple",
    "9": "friend",
    "10": "friend",
    "11": None,
}

# rel_cd가 없을 때만 travel_status_accompany를 보완값으로 사용한다.
ACCOMPANY_LABEL_FALLBACK: Final[dict[str, CompanionType]] = {
    "나홀로 여행": "solo",
    "2인 여행(가족 외)": "friend",
    "3인 이상 여행(가족 외)": "friend",
    "2인 가족 여행": "family",
    "3인 이상 가족 여행(친척 포함)": "family",
    "자녀 동반 여행": "family",
    "부모 동반 여행": "family",
    "3대 동반 여행(친척 포함)": "family",
}
AIHUB_PARTY_LABELS: Final[dict[str, PartyType]] = {
    "나홀로 여행": PartyType.SOLO,
    "2인 여행(가족 외)": PartyType.NON_FAMILY_TWO,
    "3인 이상 여행(가족 외)": PartyType.NON_FAMILY_GROUP,
    "2인 가족 여행": PartyType.FAMILY_TWO,
    "3인 이상 가족 여행(친척 포함)": PartyType.FAMILY_GROUP,
    "자녀 동반 여행": PartyType.WITH_CHILDREN,
    "부모 동반 여행": PartyType.WITH_PARENTS,
    "3대 동반 여행(친척 포함)": PartyType.THREE_GENERATIONS,
}

# 한 여행에 여러 관계가 섞이면 일정 제약이 큰 유형을 대표값으로 선택한다.
COMPANION_TYPE_PRIORITY: Final[tuple[CompanionType, ...]] = (
    "family",
    "couple",
    "friend",
    "solo",
)


def classify_companion_type(
    *,
    companion_count: int | None,
    relation_codes: Iterable[str | int],
    travel_status_accompany: str | None = None,
) -> CompanionType | None:
    """AIHub 동반자 정보를 네 가지 사용자 선택 유형으로 통합한다.

    ``travel_companions_num == 0``이면 rel_cd가 없는 정상적인 혼자 여행이다.
    rel_cd가 있으면 관계 코드를 우선하고, 관계 코드가 전혀 없을 때만
    ``travel_status_accompany``를 보완값으로 사용한다. 관계가 기타(11)뿐인
    여행은 합의대로 ``None``을 반환해 추천 조건에서 제외한다.
    """

    if companion_count == 0:
        return "solo"

    normalized_codes = tuple(
        str(code).strip() for code in relation_codes if str(code).strip()
    )
    mapped_types = {
        mapped
        for code in normalized_codes
        if (mapped := COMPANION_TYPE_BY_RELATION_CODE.get(code)) is not None
    }

    for companion_type in COMPANION_TYPE_PRIORITY:
        if companion_type in mapped_types:
            return companion_type

    # rel_cd가 기타(11)뿐이면 travel_status_accompany로 되살리지 않는다.
    if normalized_codes:
        return None

    return ACCOMPANY_LABEL_FALLBACK.get(
        str(travel_status_accompany or "").strip()
    )


# ---------------------------------------------------------------------------
# 여행 스타일: Code B의 TSY 그룹
# ---------------------------------------------------------------------------

TRAVEL_STYLE_COLUMNS: Final[tuple[str, ...]] = tuple(
    f"travel_styl_{index}" for index in range(1, 9)
)

TSY_LABELS: Final[dict[str, str]] = {
    "1": "자연 선호 매우선호",
    "2": "자연 선호 중간선호",
    "3": "자연 선호 약간선호",
    "4": "중립",
    "5": "도시 선호 약간선호",
    "6": "도시 선호 중간선호",
    "7": "도시 선호 매우선호",
}

# ---------------------------------------------------------------------------
# 제주 여행 지역: 사용자 region -> 검색용 district
# ---------------------------------------------------------------------------

REGION_DISTRICTS: Final[dict[str, tuple[tuple[str, str], ...]]] = {
    "east": (
        ("제주시", "조천읍"), ("제주시", "구좌읍"), ("제주시", "우도면"), ("제주시", "종달동"),
        ("서귀포시", "성산읍"), ("서귀포시", "표선면"), ("서귀포시", "성읍"), ("서귀포시", "신풍하동"),
    ),

    "west": (
        ("제주시", "애월읍"), ("제주시", "한림읍"), ("제주시", "한림북동"), ("제주시", "한경면"),
        ("제주시", "청수동"), ("제주시", "금악동"), ("서귀포시", "대정읍"), ("서귀포시", "안덕면"),
        ("서귀포시", "동광본동"),
    ),

    "south": (
        ("서귀포시", "남원읍"), ("서귀포시", "강정동"), ("서귀포시", "대포동"), ("서귀포시", "동홍동"),
        ("서귀포시", "명동"), ("서귀포시", "법환동"), ("서귀포시", "보목동"), ("서귀포시", "상예동"),
        ("서귀포시", "상효동"), ("서귀포시", "색달동"), ("서귀포시", "서귀동"), ("서귀포시", "서호동"),
        ("서귀포시", "서홍동"), ("서귀포시", "서흥동"), ("서귀포시", "신효동"), ("서귀포시", "영남동"),
        ("서귀포시", "중동"), ("서귀포시", "중문동"), ("서귀포시", "토평동"), ("서귀포시", "하예동"),
        ("서귀포시", "하예하동"), ("서귀포시", "하원동"), ("서귀포시", "하효동"), ("서귀포시", "호근동"),
        ("서귀포시", "회수동"),
    ),

    "north": (
        ("제주시", "가문동"), ("제주시", "건입동"), ("제주시", "구남동"), ("제주시", "내도동"),
        ("제주시", "노형동"), ("제주시", "도남동"), ("제주시", "도두이동"), ("제주시", "도두일동"),
        ("제주시", "도련일동"), ("제주시", "봉개동"), ("제주시", "사라봉동"), ("제주시", "삼도이동"),
        ("제주시", "삼도일동"), ("제주시", "삼양삼동"), ("제주시", "삼양이동"), ("제주시", "삼양일동"),
        ("제주시", "선돌목동"), ("제주시", "아라일동"), ("제주시", "연동"), ("제주시", "연무정동"),
        ("제주시", "영평동"), ("제주시", "오등동"), ("제주시", "오라삼동"), ("제주시", "오라이동"),
        ("제주시", "오라일동"), ("제주시", "외도이동"), ("제주시", "외도일동"), ("제주시", "용담삼동"),
        ("제주시", "용담이동"), ("제주시", "용담일동"), ("제주시", "이도이동"), ("제주시", "이도일동"),
        ("제주시", "이호이동"), ("제주시", "이호일동"), ("제주시", "일도이동"), ("제주시", "일도일동"),
        ("제주시", "진동"), ("제주시", "첨단동"), ("제주시", "탑동"), ("제주시", "하귀동"),
        ("제주시", "해안동"), ("제주시", "화북1동"), ("제주시", "화북이동"), ("제주시", "화북일동"),
        ("제주시", "회천동"),
    ),
}


def get_region_districts(
    region: str | None,
) -> tuple[tuple[str, str], ...]:
    if not region:
        return ()

    return REGION_DISTRICTS.get(
        str(region).strip().lower(),
        (),
    )

# ---------------------------------------------------------------------------
# 방문 유형: Code B의 VIS 그룹 -> 기존 RAG 슬롯/컬렉션
# ---------------------------------------------------------------------------


SLOT_TARGET_COLLECTIONS: Final[dict[SlotRole, tuple[str, ...]]] = {
    "visit": ("attractions",),
    "activity": ("activities", "experience", "attractions"),
    "food": ("restaurants",),
    "shopping": ("shopping",),
}


SLOT_ITINERARY_ROLES: Final[dict[SlotRole, tuple[str, ...]]] = {
    "visit": ("visit",),
    "activity": ("activity", "experience", "visit"),
    "food": ("meal", "cafe_break"),
    "shopping": ("shopping", "market_visit"),
}


@dataclass(frozen=True)
class VisitAreaTypeMapping:
    code_name: str
    normalized_type: str
    slot_role: SlotRole | None
    target_collections: tuple[str, ...]
    itinerary_roles: tuple[str, ...]
    include_in_rag: bool = True


def _visit_mapping(
    code_name: str,
    normalized_type: str,
    slot_role: SlotRole | None,
    *,
    include_in_rag: bool = True,
) -> VisitAreaTypeMapping:
    collections = (
        SLOT_TARGET_COLLECTIONS[slot_role]
        if slot_role else ()
    )

    roles = (
        SLOT_ITINERARY_ROLES[slot_role]
        if slot_role else ()
    )

    return VisitAreaTypeMapping(
        code_name=code_name,
        normalized_type=normalized_type,
        slot_role=slot_role,
        target_collections=collections,
        itinerary_roles=roles,
        include_in_rag=include_in_rag,
    )


VISIT_TYPE_CODES: Final[dict[VisitPreference, tuple[str, ...]]] = {
    VisitPreference.NATURE: ("1",),
    VisitPreference.HISTORY: ("2",),
    VisitPreference.CULTURE: ("3",),
    VisitPreference.MARKET_SHOPPING: ("4", "10"),
    VisitPreference.LEISURE: ("5",),
    VisitPreference.THEME_PARK: ("6",),
    VisitPreference.TRAIL: ("7",),
    VisitPreference.FESTIVAL: ("8",),
    VisitPreference.FOOD_CAFE: ("11",),
    VisitPreference.EXPERIENCE: ("13",),
}


# slot_role은 similarity.py의 _template_role()과 일치시켰다.
VISIT_AREA_TYPE_MAPPINGS: Final[dict[str, VisitAreaTypeMapping]] = {
    "1": _visit_mapping("자연관광지", "nature", "visit"),
    "2": _visit_mapping("역사/유적/종교 시설", "history", "visit"),
    "3": _visit_mapping("문화 시설", "culture", "visit"),
    "4": _visit_mapping("상업지구", "market_shopping", "shopping"),
    "5": _visit_mapping("레저/스포츠 관련 시설", "leisure", "activity"),
    "6": _visit_mapping("테마시설", "theme_park", "activity"),
    "7": _visit_mapping("산책로/둘레길", "trail", "visit"),
    "8": _visit_mapping("지역 축제/행사", "festival", "activity"),
    "9": _visit_mapping("역/터미널/휴게소", "transit", None, include_in_rag=False),
    "10": _visit_mapping("상점", "market_shopping", "shopping"),
    "11": _visit_mapping("식당/카페", "food_cafe", "food"),
    "12": _visit_mapping("기타", "other", None, include_in_rag=False),
    "13": _visit_mapping("체험 활동 관광지", "experience", "activity"),
    "21": _visit_mapping("집", "home", None, include_in_rag=False),
    "22": _visit_mapping("친구/친지집", "private_home", None, include_in_rag=False),
    "23": _visit_mapping("사무실", "office", None, include_in_rag=False),
    "24": _visit_mapping("숙소", "lodging", None, include_in_rag=False),
}


VIS_TO_SLOT_ROLE: Final[dict[str, SlotRole]] = {
    code: mapping.slot_role
    for code, mapping in VISIT_AREA_TYPE_MAPPINGS.items()
    if mapping.slot_role is not None
}

def get_visit_area_type_mapping(
    visit_area_type_cd: str | int | None,
) -> VisitAreaTypeMapping | None:

    if visit_area_type_cd is None:
        return None
    return VISIT_AREA_TYPE_MAPPINGS.get(str(visit_area_type_cd).strip())

