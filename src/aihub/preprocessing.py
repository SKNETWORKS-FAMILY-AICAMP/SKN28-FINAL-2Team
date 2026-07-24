"""AIHub Jeju travel-log preprocessing service.

This script merges the Training and Validation label data, keeps Jeju trips
and Jeju visits only, removes personal-place visits, and cascades the retained
travel/visit keys to the related tables. GPS, the nationwide POI master, image
data, and other unlisted files are intentionally excluded.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

from src.common.paths import AIHUB_DATA_ROOT

DEFAULT_DATASET_ROOT = AIHUB_DATA_ROOT / "raw"
DEFAULT_OUTPUT_ROOT = AIHUB_DATA_ROOT / "processed" / "aihub"

JEJU_LONGITUDE = (126.0, 127.0)
JEJU_LATITUDE = (33.0, 34.0)
EXCLUDED_VISIT_TYPES = {"21", "22", "23"}

INPUT_FILES = {
    "traveller": "tn_traveller_master_여행객 Master_H.csv",
    "travel": "tn_travel_여행_H.csv",
    "visit": "tn_visit_area_info_방문지정보_H.csv",
    "companion": "tn_companion_info_동반자정보_H.csv",
    "activity": "tn_activity_his_활동내역_H.csv",
    "activity_consume": "tn_activity_consume_his_활동소비내역_H.csv",
    "lodge_consume": "tn_lodge_consume_his_숙박소비내역_H.csv",
    "movement_consume": "tn_mvmn_consume_his_이동수단소비내역_H.csv",
    "advance_consume": "tn_adv_consume_his_사전소비내역_H.csv",
    "move": "tn_move_his_이동내역_H.csv",
}

CODE_FILES = {
    "code_a": "tc_codea_코드A.csv",
    "code_b": "tc_codeb_코드B.csv",
    "sgg_code": "tc_sgg_시군구코드.csv",
}

OUTPUT_FILES = {
    "traveller": "jeju_traveller.csv",
    "travel": "jeju_travel.csv",
    "visit": "jeju_visit.csv",
    "companion": "jeju_companion.csv",
    "activity": "jeju_activity.csv",
    "activity_consume": "jeju_activity_consume.csv",
    "lodge_consume": "jeju_lodge_consume.csv",
    "movement_consume": "jeju_movement_consume.csv",
    "advance_consume": "jeju_advance_consume.csv",
    "move": "jeju_move.csv",
    "code_a": "code_a.csv",
    "code_b": "code_b.csv",
    "sgg_code": "sgg_code.csv",
}

DATE_ONLY_COLUMNS = {
    "travel_start_ymd",
    "travel_end_ymd",
    "visit_start_ymd",
    "visit_end_ymd",
}

DATETIME_COLUMNS = {
    "payment_dt",
    "chk_in_dt_min",
    "chk_out_dt_min",
    "start_dt_min",
    "end_dt_min",
}

INTEGER_COLUMNS = {
    "visit_order",
    "residence_time_min",
    "dgstfn",
    "revisit_intention",
    "rcmdtn_intention",
    "payment_amt_won",
}

FLOAT_COLUMNS = {"x_coord", "y_coord"}
NUMERIC_COLUMNS = INTEGER_COLUMNS | FLOAT_COLUMNS


def snake_case(name: str) -> str:
    value = name.strip().lower()
    value = re.sub(r"[^0-9a-zA-Z가-힣]+", "_", value)
    return value.strip("_")


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"입력 파일을 찾을 수 없습니다: {path}")
    return pd.read_csv(
        path,
        dtype=str,
        encoding="utf-8-sig",
        keep_default_na=True,
        na_values=[""],
        low_memory=False,
    )


def merge_train_validation(
    filename: str,
    training_dir: Path,
    validation_dir: Path,
) -> pd.DataFrame:
    training = read_csv(training_dir / filename)
    validation = read_csv(validation_dir / filename)
    return pd.concat([training, validation], ignore_index=True)


def normalize_strings(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result.columns = [snake_case(column) for column in result.columns]
    for column in result.columns:
        if result[column].dtype == "object":
            result[column] = result[column].str.strip()
            result[column] = result[column].replace("", pd.NA)
    return result


def normalize_dates_and_numbers(
    frame: pd.DataFrame,
    conversion_failures: dict[str, int],
    table_name: str,
) -> pd.DataFrame:
    result = frame.copy()

    for column in DATE_ONLY_COLUMNS & set(result.columns):
        original = result[column].copy()
        parsed = pd.to_datetime(original, errors="coerce")
        conversion_failures[f"{table_name}.{column}"] = int(
            (original.notna() & parsed.isna()).sum()
        )
        formatted = parsed.dt.strftime("%Y-%m-%d")
        result[column] = formatted.where(parsed.notna(), original)

    for column in DATETIME_COLUMNS & set(result.columns):
        original = result[column].copy()
        parsed = pd.to_datetime(original, errors="coerce")
        conversion_failures[f"{table_name}.{column}"] = int(
            (original.notna() & parsed.isna()).sum()
        )
        formatted = parsed.dt.strftime("%Y-%m-%d %H:%M:%S")
        result[column] = formatted.where(parsed.notna(), original)

    for column in NUMERIC_COLUMNS & set(result.columns):
        original = result[column].copy()
        parsed = pd.to_numeric(original, errors="coerce")
        conversion_failures[f"{table_name}.{column}"] = int(
            (original.notna() & parsed.isna()).sum()
        )
        if column in INTEGER_COLUMNS:
            fractional = parsed.dropna().mod(1).ne(0)
            result[column] = (
                parsed.astype("Int64")
                if not fractional.any()
                else parsed.where(parsed.notna(), original)
            )
        else:
            result[column] = parsed.where(parsed.notna(), original)

    return result


def remove_exact_duplicates(frame: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    duplicate_count = int(frame.duplicated().sum())
    return frame.drop_duplicates().reset_index(drop=True), duplicate_count


def jeju_location_mask(visits: pd.DataFrame) -> pd.Series:
    road_address = visits["road_nm_addr"].fillna("").str.contains("제주", regex=False)
    lot_address = visits["lotno_addr"].fillna("").str.contains("제주", regex=False)
    sgg = visits["sgg_cd"].fillna("").str.startswith("50")
    longitude = pd.to_numeric(visits["x_coord"], errors="coerce")
    latitude = pd.to_numeric(visits["y_coord"], errors="coerce")
    coordinate = longitude.between(*JEJU_LONGITUDE) & latitude.between(*JEJU_LATITUDE)
    return road_address | lot_address | sgg | coordinate


def key_index(frame: pd.DataFrame, left: str, right: str) -> pd.MultiIndex:
    return pd.MultiIndex.from_frame(frame[[left, right]].fillna(""))


def filter_visit_children(
    frame: pd.DataFrame,
    retained_visit_keys: pd.MultiIndex,
) -> pd.DataFrame:
    keys = key_index(frame, "travel_id", "visit_area_id")
    return frame.loc[keys.isin(retained_visit_keys)].copy()


def filter_moves(
    frame: pd.DataFrame,
    retained_visit_keys: pd.MultiIndex,
) -> pd.DataFrame:
    retained_key_set = set(retained_visit_keys.tolist())

    def endpoint_valid(travel_id: object, visit_area_id: object) -> bool:
        if pd.isna(visit_area_id) or str(visit_area_id).strip() == "":
            return True
        return (str(travel_id), str(visit_area_id)) in retained_key_set

    start_valid = [
        endpoint_valid(travel_id, visit_area_id)
        for travel_id, visit_area_id in zip(
            frame["travel_id"], frame["start_visit_area_id"], strict=False
        )
    ]
    end_valid = [
        endpoint_valid(travel_id, visit_area_id)
        for travel_id, visit_area_id in zip(
            frame["travel_id"], frame["end_visit_area_id"], strict=False
        )
    ]
    has_endpoint = frame["start_visit_area_id"].notna() | frame[
        "end_visit_area_id"
    ].notna()
    mask = pd.Series(start_valid, index=frame.index) & pd.Series(
        end_valid, index=frame.index
    )
    return frame.loc[mask & has_endpoint].copy()


def write_csv(frame: pd.DataFrame, output_dir: Path, filename: str) -> None:
    frame.to_csv(
        output_dir / filename,
        index=False,
        encoding="utf-8",
        lineterminator="\n",
    )


def preprocess(dataset_root: Path, output_root: Path) -> dict[str, object]:
    data_root = dataset_root / "3.개방데이터" / "1.데이터"
    training_dir = data_root / "Training" / "02.라벨링데이터"
    validation_dir = data_root / "Validation" / "02.라벨링데이터"
    data_output_dir = output_root / "data"
    code_output_dir = output_root / "code"
    report_output_dir = output_root / "reports"

    for output_dir in (data_output_dir, code_output_dir, report_output_dir):
        output_dir.mkdir(parents=True, exist_ok=True)

    raw_tables: dict[str, pd.DataFrame] = {}
    counts: dict[str, dict[str, int]] = {}
    duplicate_counts: dict[str, int] = {}
    conversion_failures: dict[str, int] = {}

    for table_name, filename in INPUT_FILES.items():
        merged = merge_train_validation(filename, training_dir, validation_dir)
        counts[table_name] = {"input_rows": int(len(merged))}
        raw_tables[table_name] = normalize_strings(merged)

    codes: dict[str, pd.DataFrame] = {}
    for table_name, filename in CODE_FILES.items():
        frame = normalize_strings(read_csv(training_dir / filename))
        counts[table_name] = {"input_rows": int(len(frame))}
        codes[table_name] = frame

    traveller = raw_tables["traveller"]
    travel = raw_tables["travel"]

    jeju_traveller = traveller.loc[
        traveller["travel_status_destination"].eq("제주")
    ].copy()
    jeju_traveller_ids = set(jeju_traveller["traveler_id"].dropna())

    jeju_travel = travel.loc[travel["traveler_id"].isin(jeju_traveller_ids)].copy()
    jeju_travel_ids = set(jeju_travel["travel_id"].dropna())

    selected: dict[str, pd.DataFrame] = {
        "traveller": jeju_traveller,
        "travel": jeju_travel,
    }

    for table_name in (
        "visit",
        "companion",
        "activity",
        "activity_consume",
        "lodge_consume",
        "movement_consume",
        "advance_consume",
        "move",
    ):
        frame = raw_tables[table_name]
        selected[table_name] = frame.loc[
            frame["travel_id"].isin(jeju_travel_ids)
        ].copy()
        counts[table_name]["after_jeju_travel_filter"] = int(
            len(selected[table_name])
        )

    counts["traveller"]["after_jeju_travel_filter"] = int(len(jeju_traveller))
    counts["travel"]["after_jeju_travel_filter"] = int(len(jeju_travel))

    visit_before_location = selected["visit"]
    local_mask = jeju_location_mask(visit_before_location)
    visit_after_location = visit_before_location.loc[local_mask].copy()
    personal_mask = visit_after_location["visit_area_type_cd"].isin(
        EXCLUDED_VISIT_TYPES
    )
    retained_visits = visit_after_location.loc[~personal_mask].copy()

    counts["visit"]["removed_non_jeju_location"] = int((~local_mask).sum())
    counts["visit"]["removed_personal_place"] = int(personal_mask.sum())

    retained_visits, duplicate_counts["visit"] = remove_exact_duplicates(
        retained_visits
    )
    retained_visit_keys = key_index(retained_visits, "travel_id", "visit_area_id")
    selected["visit"] = retained_visits

    for table_name in ("activity", "activity_consume"):
        selected[table_name] = filter_visit_children(
            selected[table_name], retained_visit_keys
        )

    selected["move"] = filter_moves(selected["move"], retained_visit_keys)

    for table_name, frame in selected.items():
        normalized = normalize_dates_and_numbers(
            frame, conversion_failures, table_name
        )
        if table_name != "visit":
            normalized, duplicate_counts[table_name] = remove_exact_duplicates(
                normalized
            )
        selected[table_name] = normalized
        counts[table_name]["output_rows"] = int(len(normalized))
        counts[table_name]["exact_duplicates_removed"] = duplicate_counts[table_name]

    for table_name, frame in codes.items():
        if table_name == "sgg_code":
            frame = frame.loc[
                frame["sgg_cd"].fillna("").str.startswith("50")
                | frame["sido_nm"].fillna("").str.contains("제주", regex=False)
            ].copy()
        frame, duplicate_count = remove_exact_duplicates(frame)
        codes[table_name] = frame
        counts[table_name]["output_rows"] = int(len(frame))
        counts[table_name]["exact_duplicates_removed"] = duplicate_count

    retained_key_set = set(retained_visit_keys.tolist())
    validations = {
        "all_travellers_are_jeju_destination": bool(
            selected["traveller"]["travel_status_destination"].eq("제주").all()
        ),
        "travel_refs_valid_traveller": bool(
            selected["travel"]["traveler_id"]
            .isin(set(selected["traveller"]["traveler_id"]))
            .all()
        ),
        "all_visits_are_jeju": bool(jeju_location_mask(selected["visit"]).all()),
        "no_personal_visit_types": bool(
            ~selected["visit"]["visit_area_type_cd"]
            .isin(EXCLUDED_VISIT_TYPES)
            .any()
        ),
        "visit_composite_key_unique": bool(
            ~selected["visit"].duplicated(["travel_id", "visit_area_id"]).any()
        ),
        "activity_refs_valid_visit": bool(
            set(
                key_index(
                    selected["activity"], "travel_id", "visit_area_id"
                ).tolist()
            ).issubset(retained_key_set)
        ),
        "activity_consume_refs_valid_visit": bool(
            set(
                key_index(
                    selected["activity_consume"], "travel_id", "visit_area_id"
                ).tolist()
            ).issubset(retained_key_set)
        ),
    }

    move_refs_valid = True
    for row in selected["move"].itertuples(index=False):
        travel_id = str(row.travel_id)
        for endpoint in (row.start_visit_area_id, row.end_visit_area_id):
            if pd.notna(endpoint) and str(endpoint).strip():
                if (travel_id, str(endpoint)) not in retained_key_set:
                    move_refs_valid = False
                    break
        if not move_refs_valid:
            break
    validations["move_refs_valid_visit"] = move_refs_valid

    for table_name in (
        "companion",
        "lodge_consume",
        "movement_consume",
        "advance_consume",
    ):
        validations[f"{table_name}_refs_valid_travel"] = bool(
            selected[table_name]["travel_id"].isin(jeju_travel_ids).all()
        )

    failed_validations = [
        name for name, passed in validations.items() if not passed
    ]
    if failed_validations:
        raise RuntimeError(
            "전처리 검증에 실패했습니다: " + ", ".join(failed_validations)
        )

    for table_name, frame in selected.items():
        write_csv(frame, data_output_dir, OUTPUT_FILES[table_name])
    for table_name, frame in codes.items():
        write_csv(frame, code_output_dir, OUTPUT_FILES[table_name])

    count_frame = pd.DataFrame(
        {"table": table_name, **metrics}
        for table_name, metrics in counts.items()
    ).fillna(0)
    count_frame.to_csv(
        report_output_dir / "preprocessing_counts.csv",
        index=False,
        encoding="utf-8",
        lineterminator="\n",
    )

    report: dict[str, object] = {
        "rules": {
            "jeju_destination": "TRAVEL_STATUS_DESTINATION == 제주",
            "jeju_longitude": list(JEJU_LONGITUDE),
            "jeju_latitude": list(JEJU_LATITUDE),
            "excluded_visit_types": sorted(EXCLUDED_VISIT_TYPES),
            "training_validation_marker_added": False,
            "gps_included": False,
            "poi_master_included": False,
            "photo_data_included": False,
        },
        "counts": counts,
        "conversion_failures": conversion_failures,
        "validations": validations,
        "output_files": sorted(
            str(path.relative_to(output_root)).replace("\\", "/")
            for path in output_root.rglob("*.csv")
        ),
    }
    (report_output_dir / "preprocessing_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report
