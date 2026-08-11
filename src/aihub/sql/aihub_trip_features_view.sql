-- AIHub 여행 특성 통합 조회 VIEW
--
-- 목적:
--   여행 한 건(travel_id)을 기준으로 여행자, 동반자, 여행 기간, 여행 스타일,
--   방문 유형을 한 행에서 조회한다.
--
-- 주의:
--   원본 aihub_* 테이블은 변경하지 않는다.
--   동반자와 방문지는 먼저 travel_id별로 집계하여 다대다 JOIN에 따른
--   중복 행 증가를 방지한다.

CREATE OR REPLACE VIEW aihub_trip_features AS
WITH companion_agg AS (
    SELECT
        c.travel_id,
        COUNT(*) AS companion_row_count,
        GROUP_CONCAT(
            DISTINCT c.rel_cd
            ORDER BY CAST(c.rel_cd AS UNSIGNED)
            SEPARATOR ','
        ) AS relation_codes,
        GROUP_CONCAT(
            DISTINCT COALESCE(tcr.cd_nm, CONCAT('미정(', c.rel_cd, ')'))
            ORDER BY CAST(c.rel_cd AS UNSIGNED)
            SEPARATOR ','
        ) AS relation_names,
        MAX(c.rel_cd IN ('2', '3', '4', '6')) AS has_family,
        MAX(c.rel_cd IN ('1', '8')) AS has_couple,
        MAX(c.rel_cd IN ('5', '7', '9', '10')) AS has_friend,
        MAX(c.rel_cd = '11') AS has_other
    FROM aihub_companion AS c
    LEFT JOIN aihub_code_b AS tcr
        ON tcr.cd_a = 'TCR'
       AND tcr.cd_b = c.rel_cd
    GROUP BY c.travel_id
),
visit_type_count AS (
    SELECT
        v.travel_id,
        v.visit_area_type_cd,
        COALESCE(vis.cd_nm, CONCAT('미정(', v.visit_area_type_cd, ')'))
            AS visit_type_name,
        COUNT(*) AS visit_count
    FROM aihub_visit AS v
    LEFT JOIN aihub_code_b AS vis
        ON vis.cd_a = 'VIS'
       AND vis.cd_b = v.visit_area_type_cd
    GROUP BY v.travel_id, v.visit_area_type_cd, vis.cd_nm
),
visit_agg AS (
    SELECT
        travel_id,
        GROUP_CONCAT(
            visit_area_type_cd
            ORDER BY CAST(visit_area_type_cd AS UNSIGNED)
            SEPARATOR ','
        ) AS visit_type_codes,
        GROUP_CONCAT(
            CONCAT(visit_type_name, ':', visit_count)
            ORDER BY visit_count DESC, CAST(visit_area_type_cd AS UNSIGNED)
            SEPARATOR ' | '
        ) AS visit_type_counts,
        GROUP_CONCAT(
            DISTINCT CASE
                WHEN visit_area_type_cd IN ('1', '2', '3', '6', '7', '8')
                    THEN 'visit'
                WHEN visit_area_type_cd IN ('5', '13') THEN 'activity'
                WHEN visit_area_type_cd = '11' THEN 'food'
                WHEN visit_area_type_cd IN ('4', '10') THEN 'shopping'
                ELSE NULL
            END
            ORDER BY CASE
                WHEN visit_area_type_cd IN ('1', '2', '3', '6', '7', '8') THEN 1
                WHEN visit_area_type_cd IN ('5', '13') THEN 2
                WHEN visit_area_type_cd = '11' THEN 3
                WHEN visit_area_type_cd IN ('4', '10') THEN 4
                ELSE 5
            END
            SEPARATOR ','
        ) AS visit_slot_roles
    FROM visit_type_count
    GROUP BY travel_id
),
rag_visit_rank AS (
    SELECT
        travel_id,
        visit_area_type_cd,
        visit_type_name,
        visit_count,
        ROW_NUMBER() OVER (
            PARTITION BY travel_id
            ORDER BY visit_count DESC, CAST(visit_area_type_cd AS UNSIGNED)
        ) AS type_rank
    FROM visit_type_count
    WHERE visit_area_type_cd IN (
        '1', '2', '3', '4', '5', '6', '7', '8', '10', '11', '13'
    )
)
SELECT
    t.travel_id,
    t.traveler_id,
    t.travel_nm AS travel_name,
    t.travel_purpose,
    t.travel_start_ymd AS travel_start_date,
    t.travel_end_ymd AS travel_end_date,
    DATEDIFF(t.travel_end_ymd, t.travel_start_ymd) + 1 AS duration_days,

    r.travel_companions_num AS companion_count,
    r.travel_companions_num + 1 AS total_party_size,
    r.travel_status_accompany,
    ca.relation_codes,
    ca.relation_names,
    CASE
        WHEN COALESCE(r.travel_companions_num, 0) = 0 THEN 'solo'
        WHEN COALESCE(ca.has_family, 0) = 1 THEN 'family'
        WHEN COALESCE(ca.has_couple, 0) = 1 THEN 'couple'
        WHEN COALESCE(ca.has_friend, 0) = 1 THEN 'friend'
        WHEN COALESCE(ca.companion_row_count, 0) = 0
             AND r.travel_status_accompany IN (
                 '자녀 동반 여행', '부모 동반 여행', '2인 가족 여행',
                 '3인 이상 가족 여행(친척 포함)', '3대 동반 여행(친척 포함)'
             ) THEN 'family'
        WHEN COALESCE(ca.companion_row_count, 0) = 0
             AND r.travel_status_accompany IN (
                 '2인 여행(가족 외)', '3인 이상 여행(가족 외)'
             ) THEN 'friend'
        ELSE NULL
    END AS companion_type,

    r.travel_styl_1,
    r.travel_styl_2,
    r.travel_styl_3,
    r.travel_styl_4,
    r.travel_styl_5,
    r.travel_styl_6,
    r.travel_styl_7,
    r.travel_styl_8,
    JSON_OBJECT(
        'travel_styl_1', JSON_OBJECT('code', r.travel_styl_1, 'label', tsy1.cd_nm),
        'travel_styl_2', JSON_OBJECT('code', r.travel_styl_2, 'label', tsy2.cd_nm),
        'travel_styl_3', JSON_OBJECT('code', r.travel_styl_3, 'label', tsy3.cd_nm),
        'travel_styl_4', JSON_OBJECT('code', r.travel_styl_4, 'label', tsy4.cd_nm),
        'travel_styl_5', JSON_OBJECT('code', r.travel_styl_5, 'label', tsy5.cd_nm),
        'travel_styl_6', JSON_OBJECT('code', r.travel_styl_6, 'label', tsy6.cd_nm),
        'travel_styl_7', JSON_OBJECT('code', r.travel_styl_7, 'label', tsy7.cd_nm),
        'travel_styl_8', JSON_OBJECT('code', r.travel_styl_8, 'label', tsy8.cd_nm)
    ) AS travel_style_labels,

    va.visit_type_codes,
    va.visit_type_counts,
    va.visit_slot_roles,
    rvr.visit_area_type_cd AS main_visit_type_code,
    rvr.visit_type_name AS main_visit_type_name,
    rvr.visit_count AS main_visit_type_count
FROM aihub_travel AS t
JOIN aihub_traveller AS r
    ON r.traveler_id = t.traveler_id
LEFT JOIN companion_agg AS ca
    ON ca.travel_id = t.travel_id
LEFT JOIN visit_agg AS va
    ON va.travel_id = t.travel_id
LEFT JOIN rag_visit_rank AS rvr
    ON rvr.travel_id = t.travel_id
   AND rvr.type_rank = 1
LEFT JOIN aihub_code_b AS tsy1 ON tsy1.cd_a = 'TSY' AND tsy1.cd_b = r.travel_styl_1
LEFT JOIN aihub_code_b AS tsy2 ON tsy2.cd_a = 'TSY' AND tsy2.cd_b = r.travel_styl_2
LEFT JOIN aihub_code_b AS tsy3 ON tsy3.cd_a = 'TSY' AND tsy3.cd_b = r.travel_styl_3
LEFT JOIN aihub_code_b AS tsy4 ON tsy4.cd_a = 'TSY' AND tsy4.cd_b = r.travel_styl_4
LEFT JOIN aihub_code_b AS tsy5 ON tsy5.cd_a = 'TSY' AND tsy5.cd_b = r.travel_styl_5
LEFT JOIN aihub_code_b AS tsy6 ON tsy6.cd_a = 'TSY' AND tsy6.cd_b = r.travel_styl_6
LEFT JOIN aihub_code_b AS tsy7 ON tsy7.cd_a = 'TSY' AND tsy7.cd_b = r.travel_styl_7
LEFT JOIN aihub_code_b AS tsy8 ON tsy8.cd_a = 'TSY' AND tsy8.cd_b = r.travel_styl_8;
