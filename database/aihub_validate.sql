-- Row-count and referential-integrity checks for the AIHub Jeju load.

SELECT 'aihub_traveller' AS table_name, COUNT(*) AS row_count FROM aihub_traveller
UNION ALL SELECT 'aihub_travel', COUNT(*) FROM aihub_travel
UNION ALL SELECT 'aihub_companion', COUNT(*) FROM aihub_companion
UNION ALL SELECT 'aihub_visit', COUNT(*) FROM aihub_visit
UNION ALL SELECT 'aihub_activity', COUNT(*) FROM aihub_activity
UNION ALL SELECT 'aihub_activity_consume', COUNT(*) FROM aihub_activity_consume
UNION ALL SELECT 'aihub_lodge_consume', COUNT(*) FROM aihub_lodge_consume
UNION ALL SELECT 'aihub_movement_consume', COUNT(*) FROM aihub_movement_consume
UNION ALL SELECT 'aihub_advance_consume', COUNT(*) FROM aihub_advance_consume
UNION ALL SELECT 'aihub_move', COUNT(*) FROM aihub_move
UNION ALL SELECT 'aihub_code_a', COUNT(*) FROM aihub_code_a
UNION ALL SELECT 'aihub_code_b', COUNT(*) FROM aihub_code_b
UNION ALL SELECT 'aihub_sgg_code', COUNT(*) FROM aihub_sgg_code;

SELECT COUNT(*) AS travel_without_traveller
FROM aihub_travel AS t
LEFT JOIN aihub_traveller AS r ON r.traveler_id = t.traveler_id
WHERE r.traveler_id IS NULL;

SELECT COUNT(*) AS visit_without_travel
FROM aihub_visit AS v
LEFT JOIN aihub_travel AS t ON t.travel_id = v.travel_id
WHERE t.travel_id IS NULL;

SELECT COUNT(*) AS activity_without_visit
FROM aihub_activity AS a
LEFT JOIN aihub_visit AS v
  ON v.travel_id = a.travel_id
 AND v.visit_area_id = a.visit_area_id
WHERE v.visit_area_id IS NULL;

SELECT COUNT(*) AS activity_consume_without_activity
FROM aihub_activity_consume AS c
LEFT JOIN aihub_activity AS a
  ON a.travel_id = c.travel_id
 AND a.visit_area_id = c.visit_area_id
 AND a.activity_type_cd = c.activity_type_cd
 AND a.activity_type_seq = c.activity_type_seq
WHERE a.visit_area_id IS NULL;

SELECT COUNT(*) AS non_jeju_or_unknown_visits
FROM aihub_visit
WHERE NOT (
       COALESCE(road_nm_addr, '') LIKE '%제주%'
    OR COALESCE(lotno_addr, '') LIKE '%제주%'
    OR COALESCE(sgg_cd, '') LIKE '50%'
    OR (x_coord BETWEEN 126.0 AND 127.0 AND y_coord BETWEEN 33.0 AND 34.0)
);

SELECT COUNT(*) AS personal_place_visits
FROM aihub_visit
WHERE visit_area_type_cd IN ('21', '22', '23');
