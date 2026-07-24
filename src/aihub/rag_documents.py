from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime
import hashlib
from statistics import fmean
from typing import Any, Iterable, Mapping


DOCUMENT_VERSION = "aihub-travel-profiles-v1"
SCHEMA_VERSION = "rag-document-v1"
MIN_LONGITUDE = 126.0
MAX_LONGITUDE = 127.0
MIN_LATITUDE = 33.0
MAX_LATITUDE = 34.0
PERSONAL_VISIT_TYPES = {"21", "22", "23"}


def clean_jeju_coordinate(
    longitude: Any,
    latitude: Any,
) -> tuple[float | None, float | None, str]:
    """Return only coordinates inside a conservative Jeju bounding box."""

    if longitude in (None, "") or latitude in (None, ""):
        return None, None, "missing"
    try:
        lng = float(longitude)
        lat = float(latitude)
    except (TypeError, ValueError):
        return None, None, "invalid"
    if not (MIN_LONGITUDE <= lng <= MAX_LONGITUDE and MIN_LATITUDE <= lat <= MAX_LATITUDE):
        return None, None, "out_of_bounds"
    return round(lng, 7), round(lat, 7), "valid"


def build_aihub_rag_payload(
    connection: Any,
    *,
    max_visits_per_trip: int = 70,
) -> dict[str, Any]:
    if max_visits_per_trip <= 0:
        raise ValueError("max_visits_per_trip must be greater than zero")

    code_maps = _code_maps(connection)
    trips = _fetch_all(
        connection,
        """
        SELECT
            t.travel_id, t.traveler_id, t.travel_purpose,
            t.travel_start_ymd, t.travel_end_ymd, t.mvmn_nm,
            t.travel_persona, t.travel_mission, t.travel_mission_check,
            r.gender, r.age_grp, r.travel_term, r.travel_num,
            r.travel_status_accompany, r.travel_status_ymd,
            r.travel_motive_1, r.travel_motive_2, r.travel_motive_3,
            r.travel_companions_num,
            r.travel_styl_1, r.travel_styl_2, r.travel_styl_3,
            r.travel_styl_4, r.travel_styl_5, r.travel_styl_6,
            r.travel_styl_7, r.travel_styl_8
        FROM aihub_travel t
        JOIN aihub_traveller r ON r.traveler_id = t.traveler_id
        ORDER BY t.travel_id
        """,
    )
    companions = _group_rows(
        _fetch_all(
            connection,
            """
            SELECT travel_id, companion_seq, rel_cd, companion_gender,
                   companion_age_grp, companion_situation
            FROM aihub_companion
            ORDER BY travel_id, companion_seq
            """,
        ),
        "travel_id",
    )
    visits = _group_rows(
        _fetch_all(
            connection,
            """
            SELECT travel_id, visit_area_id, visit_order, visit_area_nm,
                   visit_start_ymd, visit_end_ymd, road_nm_addr,
                   x_coord, y_coord, residence_time_min,
                   visit_area_type_cd, revisit_yn, visit_chc_reason_cd,
                   dgstfn, revisit_intention, rcmdtn_intention, sgg_cd
            FROM aihub_visit
            ORDER BY travel_id, visit_order, visit_area_id
            """,
        ),
        "travel_id",
    )
    activities = _group_rows_by_pair(
        _fetch_all(
            connection,
            """
            SELECT travel_id, visit_area_id, activity_type_cd,
                   activity_type_seq, activity_etc, activity_dtl
            FROM aihub_activity
            ORDER BY travel_id, visit_area_id, activity_type_seq
            """,
        ),
        "travel_id",
        "visit_area_id",
    )
    moves = _group_rows(
        _fetch_all(
            connection,
            """
            SELECT travel_id, trip_id, mvmn_cd_1, mvmn_cd_2
            FROM aihub_move
            ORDER BY travel_id, trip_id
            """,
        ),
        "travel_id",
    )
    spending = _spending_by_trip(connection)

    documents: list[dict[str, Any]] = []
    coordinate_counts: defaultdict[str, int] = defaultdict(int)
    total_source_visits = 0
    total_indexed_visits = 0
    truncated_trip_count = 0

    for trip in trips:
        travel_id = str(trip["travel_id"])
        source_visits = [
            visit
            for visit in visits.get(travel_id, [])
            if str(visit.get("visit_area_type_cd") or "") not in PERSONAL_VISIT_TYPES
        ]
        total_source_visits += len(source_visits)
        if len(source_visits) > max_visits_per_trip:
            truncated_trip_count += 1
        selected_visits = source_visits[:max_visits_per_trip]
        total_indexed_visits += len(selected_visits)

        visit_summaries: list[dict[str, Any]] = []
        place_names: list[str] = []
        visit_type_labels: list[str] = []
        satisfaction_values: list[float] = []
        document_coordinate_counts: defaultdict[str, int] = defaultdict(int)
        for visit in selected_visits:
            longitude, latitude, coordinate_status = clean_jeju_coordinate(
                visit.get("x_coord"), visit.get("y_coord")
            )
            coordinate_counts[coordinate_status] += 1
            document_coordinate_counts[coordinate_status] += 1
            visit_type_code = str(visit.get("visit_area_type_cd") or "")
            visit_type = _label(code_maps, "VIS", visit_type_code)
            visit_activities = activities.get(
                (travel_id, str(visit["visit_area_id"])), []
            )
            activity_labels = _unique(
                _label(code_maps, "ACT", str(activity.get("activity_type_cd") or ""))
                for activity in visit_activities
            )
            activity_details = _unique(
                str(activity.get("activity_dtl") or activity.get("activity_etc") or "").strip()
                for activity in visit_activities
            )
            place_name = str(visit.get("visit_area_nm") or "").strip()
            if place_name and place_name not in place_names:
                place_names.append(place_name)
            if visit_type and visit_type not in visit_type_labels:
                visit_type_labels.append(visit_type)
            satisfaction = _optional_float(visit.get("dgstfn"))
            if satisfaction is not None:
                satisfaction_values.append(satisfaction)
            visit_summaries.append(
                {
                    "order": int(visit.get("visit_order") or 0),
                    "place": place_name,
                    "visit_type": visit_type,
                    "activities": activity_labels,
                    "activity_details": activity_details,
                    "residence_minutes": _optional_int(visit.get("residence_time_min")),
                    "satisfaction": satisfaction,
                    "revisit_intention": _optional_int(visit.get("revisit_intention")),
                    "recommendation_intention": _optional_int(
                        visit.get("rcmdtn_intention")
                    ),
                    "longitude": longitude,
                    "latitude": latitude,
                    "coordinate_status": coordinate_status,
                }
            )

        mission_labels = _labels_from_codes(
            code_maps,
            "MIS",
            _split_codes(trip.get("travel_mission_check") or trip.get("travel_mission")),
        )
        motive_labels = _labels_from_codes(
            code_maps,
            "TMT",
            [
                trip.get("travel_motive_1"),
                trip.get("travel_motive_2"),
                trip.get("travel_motive_3"),
            ],
        )
        companion_relations = _unique(
            _label(code_maps, "TCR", str(item.get("rel_cd") or ""))
            for item in companions.get(travel_id, [])
        )
        transport_labels = _unique(
            _label(code_maps, "MOV", str(value or ""))
            for move in moves.get(travel_id, [])
            for value in (move.get("mvmn_cd_1"), move.get("mvmn_cd_2"))
        )
        duration_days = _duration_days(
            trip.get("travel_start_ymd"), trip.get("travel_end_ymd")
        )
        style_scores = [
            _optional_int(trip.get(f"travel_styl_{index}")) for index in range(1, 9)
        ]
        title = _document_title(trip, duration_days, mission_labels)
        trip_spending = spending.get(travel_id, {"count": 0, "total": 0})
        embedding_text = _embedding_text(
            title=title,
            trip=trip,
            duration_days=duration_days,
            mission_labels=mission_labels,
            motive_labels=motive_labels,
            companion_relations=companion_relations,
            transport_labels=transport_labels,
            style_scores=style_scores,
            visits=visit_summaries,
            spending=trip_spending,
        )
        documents.append(
            {
                "id": f"aihub:trip:{travel_id}",
                "embedding_text": embedding_text,
                "metadata": {
                    "title": title,
                    "dataset": "aihub_domestic_travel_logs",
                    "target_collection": "traveler_profiles",
                    "document_type": "traveler_trip_history",
                    "travel_id": travel_id,
                    "traveler_key": _traveler_key(str(trip["traveler_id"])),
                    "gender": str(trip.get("gender") or ""),
                    "age_group": str(trip.get("age_grp") or ""),
                    "companion": str(trip.get("travel_status_accompany") or ""),
                    "duration_days": duration_days,
                    "mission_labels": mission_labels,
                    "motive_labels": motive_labels,
                    "companion_relations": companion_relations,
                    "transport_labels": transport_labels,
                    "travel_style_scores": style_scores,
                    "visit_place_names": place_names,
                    "visit_type_labels": visit_type_labels,
                    "visit_count": len(visit_summaries),
                    "valid_coordinate_count": document_coordinate_counts["valid"],
                    "missing_coordinate_count": document_coordinate_counts["missing"],
                    "invalid_coordinate_count": (
                        document_coordinate_counts["invalid"]
                        + document_coordinate_counts["out_of_bounds"]
                    ),
                    "average_satisfaction": (
                        round(fmean(satisfaction_values), 3)
                        if satisfaction_values
                        else None
                    ),
                    "payment_count": int(trip_spending["count"]),
                    "total_spend_krw": int(trip_spending["total"]),
                    "document_version": DOCUMENT_VERSION,
                },
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "preprocessing_version": DOCUMENT_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "source": {
            "database": "tour_recommender_aihub",
            "tables": [
                "aihub_traveller",
                "aihub_travel",
                "aihub_companion",
                "aihub_visit",
                "aihub_activity",
                "aihub_move",
                "aihub_activity_consume",
                "aihub_lodge_consume",
                "aihub_movement_consume",
                "aihub_advance_consume",
            ],
        },
        "statistics": {
            "trip_documents": len(documents),
            "source_visits": total_source_visits,
            "indexed_visits": total_indexed_visits,
            "truncated_trip_count": truncated_trip_count,
            "coordinate_status": dict(sorted(coordinate_counts.items())),
        },
        "documents": documents,
    }


def _fetch_all(connection: Any, query: str) -> list[dict[str, Any]]:
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(query)
        return list(cursor.fetchall())
    finally:
        cursor.close()


def _code_maps(connection: Any) -> dict[str, dict[str, str]]:
    rows = _fetch_all(connection, "SELECT cd_a, cd_b, cd_nm FROM aihub_code_b")
    result: dict[str, dict[str, str]] = defaultdict(dict)
    for row in rows:
        result[str(row["cd_a"])][str(row["cd_b"])] = str(row["cd_nm"])
    return dict(result)


def _group_rows(
    rows: Iterable[dict[str, Any]], key: str
) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        result[str(row[key])].append(row)
    return dict(result)


def _group_rows_by_pair(
    rows: Iterable[dict[str, Any]], first: str, second: str
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    result: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        result[(str(row[first]), str(row[second]))].append(row)
    return dict(result)


def _spending_by_trip(connection: Any) -> dict[str, dict[str, int]]:
    queries = (
        "SELECT travel_id, payment_amt_won FROM aihub_activity_consume",
        "SELECT travel_id, payment_amt_won FROM aihub_lodge_consume",
        "SELECT travel_id, payment_amt_won FROM aihub_movement_consume",
        "SELECT travel_id, payment_amt_won FROM aihub_advance_consume",
    )
    result: dict[str, dict[str, int]] = defaultdict(lambda: {"count": 0, "total": 0})
    for query in queries:
        for row in _fetch_all(connection, query):
            travel_id = str(row["travel_id"])
            amount = _optional_int(row.get("payment_amt_won"))
            result[travel_id]["count"] += 1
            result[travel_id]["total"] += max(0, amount or 0)
    return dict(result)


def _label(code_maps: Mapping[str, Mapping[str, str]], group: str, code: str) -> str:
    if not code:
        return ""
    return str(code_maps.get(group, {}).get(code) or code)


def _labels_from_codes(
    code_maps: Mapping[str, Mapping[str, str]], group: str, values: Iterable[Any]
) -> list[str]:
    return _unique(
        _label(code_maps, group, str(value or "").strip()) for value in values
    )


def _split_codes(value: Any) -> list[str]:
    return [part.strip() for part in str(value or "").split(";") if part.strip()]


def _unique(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        cleaned = str(value or "").strip()
        if cleaned and cleaned not in result:
            result.append(cleaned)
    return result


def _optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _duration_days(start: Any, end: Any) -> int:
    if isinstance(start, datetime):
        start = start.date()
    if isinstance(end, datetime):
        end = end.date()
    if isinstance(start, date) and isinstance(end, date):
        return max(1, (end - start).days + 1)
    return 1


def _document_title(
    trip: Mapping[str, Any], duration_days: int, mission_labels: list[str]
) -> str:
    age = str(trip.get("age_grp") or "연령 미상").strip()
    age_text = f"{age}대" if age.isdigit() else age
    gender = str(trip.get("gender") or "성별 미상").strip()
    companion = str(trip.get("travel_status_accompany") or "동반 유형 미상").strip()
    mission = mission_labels[0] if mission_labels else "일반"
    return f"{age_text} {gender} {companion} {duration_days}일 {mission} 제주 여행 이력"


def _embedding_text(
    *,
    title: str,
    trip: Mapping[str, Any],
    duration_days: int,
    mission_labels: list[str],
    motive_labels: list[str],
    companion_relations: list[str],
    transport_labels: list[str],
    style_scores: list[int | None],
    visits: list[dict[str, Any]],
    spending: Mapping[str, int],
) -> str:
    lines = [
        f"여행 이력 제목: {title}",
        f"여행자 페르소나: {trip.get('travel_persona') or '정보 없음'}",
        f"여행 기간: {duration_days}일",
        f"동반 형태: {trip.get('travel_status_accompany') or '정보 없음'}",
        f"동반 관계: {', '.join(companion_relations) if companion_relations else '정보 없음'}",
        f"여행 미션과 테마: {', '.join(mission_labels) if mission_labels else '정보 없음'}",
        f"여행 동기: {', '.join(motive_labels) if motive_labels else '정보 없음'}",
        f"이동 수단: {', '.join(transport_labels) if transport_labels else trip.get('mvmn_nm') or '정보 없음'}",
        "여행 스타일 설문 점수(축1~8): "
        + ", ".join(
            f"축{index}={score if score is not None else '미입력'}"
            for index, score in enumerate(style_scores, start=1)
        ),
        f"기록된 총지출: {int(spending.get('total', 0)):,}원 ({int(spending.get('count', 0))}건)",
        "실제 방문 이력:",
    ]
    for visit in visits:
        detail = [
            f"{visit['order']}. {visit['place']}",
            f"유형 {visit['visit_type']}",
        ]
        if visit["activities"]:
            detail.append("활동 " + ", ".join(visit["activities"]))
        if visit["activity_details"]:
            detail.append("세부 " + ", ".join(visit["activity_details"][:2]))
        if visit["residence_minutes"] is not None:
            detail.append(f"체류 {visit['residence_minutes']}분")
        if visit["satisfaction"] is not None:
            detail.append(f"만족도 {visit['satisfaction']:g}")
        lines.append(" | ".join(detail))
    return "\n".join(lines)


def _traveler_key(traveler_id: str) -> str:
    return hashlib.sha256(traveler_id.encode("utf-8")).hexdigest()[:16]
