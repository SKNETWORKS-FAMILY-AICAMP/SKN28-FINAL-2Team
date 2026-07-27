-- AIHub domestic travel-log tables for the Jeju recommendation project.
-- Only tables with the aihub_ prefix are created by this script.

CREATE TABLE IF NOT EXISTS aihub_code_a (
    cd_a VARCHAR(10) PRIMARY KEY,
    idx INT NOT NULL,
    cd_nm VARCHAR(100) NOT NULL,
    cd_memo VARCHAR(500),
    cd_memo2 VARCHAR(500),
    del_flag CHAR(1) NOT NULL,
    order_num INT NOT NULL,
    perm_write CHAR(1),
    perm_edit CHAR(1),
    perm_delete CHAR(1),
    ins_dt DATETIME,
    edit_dt DATETIME,
    UNIQUE KEY uq_aihub_code_a_idx (idx)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS aihub_code_b (
    cd_a VARCHAR(10) NOT NULL,
    cd_b VARCHAR(10) NOT NULL,
    idx INT NOT NULL,
    cd_nm VARCHAR(200) NOT NULL,
    cd_memo VARCHAR(1000),
    cd_memo2 VARCHAR(1000),
    del_flag CHAR(1) NOT NULL,
    order_num INT NOT NULL,
    ins_dt DATETIME,
    edit_dt DATETIME,
    PRIMARY KEY (cd_a, cd_b),
    UNIQUE KEY uq_aihub_code_b_idx (idx),
    CONSTRAINT fk_aihub_code_b_group FOREIGN KEY (cd_a)
        REFERENCES aihub_code_a (cd_a)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS aihub_sgg_code (
    sgg_cd VARCHAR(20) PRIMARY KEY,
    sgg_cd1 VARCHAR(10) NOT NULL,
    sgg_cd2 VARCHAR(10),
    sgg_cd3 VARCHAR(10),
    sgg_cd4 VARCHAR(10),
    sido_nm VARCHAR(100) NOT NULL,
    sgg_nm VARCHAR(100),
    dong_nm VARCHAR(100),
    ri_nm VARCHAR(100),
    INDEX idx_aihub_sgg_names (sido_nm, sgg_nm, dong_nm)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS aihub_traveller (
    traveler_id VARCHAR(20) PRIMARY KEY,
    residence_sgg_cd VARCHAR(20) NOT NULL,
    gender VARCHAR(10) NOT NULL,
    age_grp VARCHAR(10) NOT NULL,
    edu_nm VARCHAR(10) NOT NULL,
    edu_fnsh_se VARCHAR(10) NOT NULL,
    marr_stts VARCHAR(10) NOT NULL,
    family_memb SMALLINT,
    job_nm VARCHAR(20) NOT NULL,
    job_etc VARCHAR(255),
    income VARCHAR(20) NOT NULL,
    house_income VARCHAR(20),
    travel_term VARCHAR(20) NOT NULL,
    travel_num SMALLINT,
    travel_like_sido_1 VARCHAR(20) NOT NULL,
    travel_like_sgg_1 VARCHAR(20) NOT NULL,
    travel_like_sido_2 VARCHAR(20) NOT NULL,
    travel_like_sgg_2 VARCHAR(20) NOT NULL,
    travel_like_sido_3 VARCHAR(20) NOT NULL,
    travel_like_sgg_3 VARCHAR(20) NOT NULL,
    travel_styl_1 TINYINT,
    travel_styl_2 TINYINT,
    travel_styl_3 TINYINT,
    travel_styl_4 TINYINT,
    travel_styl_5 TINYINT,
    travel_styl_6 TINYINT,
    travel_styl_7 TINYINT,
    travel_styl_8 TINYINT,
    travel_status_residence VARCHAR(100) NOT NULL,
    travel_status_destination VARCHAR(50) NOT NULL,
    travel_status_accompany VARCHAR(100) NOT NULL,
    travel_status_ymd VARCHAR(50) NOT NULL,
    travel_motive_1 VARCHAR(20) NOT NULL,
    travel_motive_2 VARCHAR(20),
    travel_motive_3 VARCHAR(20),
    travel_companions_num SMALLINT,
    INDEX idx_aihub_traveller_profile (gender, age_grp),
    INDEX idx_aihub_traveller_destination (travel_status_destination)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS aihub_travel (
    travel_id VARCHAR(20) PRIMARY KEY,
    travel_nm VARCHAR(20) NOT NULL,
    traveler_id VARCHAR(20) NOT NULL,
    travel_purpose VARCHAR(200) NOT NULL,
    travel_start_ymd DATE NOT NULL,
    travel_end_ymd DATE NOT NULL,
    mvmn_nm VARCHAR(100),
    travel_persona VARCHAR(255) NOT NULL,
    travel_mission VARCHAR(200) NOT NULL,
    travel_mission_check VARCHAR(100) NOT NULL,
    INDEX idx_aihub_travel_traveler (traveler_id),
    INDEX idx_aihub_travel_dates (travel_start_ymd, travel_end_ymd),
    CONSTRAINT fk_aihub_travel_traveller FOREIGN KEY (traveler_id)
        REFERENCES aihub_traveller (traveler_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS aihub_companion (
    travel_id VARCHAR(20) NOT NULL,
    companion_seq SMALLINT NOT NULL,
    rel_cd VARCHAR(20) NOT NULL,
    companion_gender VARCHAR(10) NOT NULL,
    companion_age_grp VARCHAR(10) NOT NULL,
    companion_situation VARCHAR(10) NOT NULL,
    PRIMARY KEY (travel_id, companion_seq),
    CONSTRAINT fk_aihub_companion_travel FOREIGN KEY (travel_id)
        REFERENCES aihub_travel (travel_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS aihub_visit (
    travel_id VARCHAR(20) NOT NULL,
    visit_area_id VARCHAR(20) NOT NULL,
    visit_order SMALLINT NOT NULL,
    visit_area_nm VARCHAR(255) NOT NULL,
    visit_start_ymd DATE NOT NULL,
    visit_end_ymd DATE NOT NULL,
    road_nm_addr VARCHAR(500),
    lotno_addr VARCHAR(500),
    x_coord DECIMAL(16, 12),
    y_coord DECIMAL(16, 12),
    road_nm_cd VARCHAR(20),
    lotno_cd VARCHAR(20),
    poi_id VARCHAR(50),
    poi_nm VARCHAR(255),
    residence_time_min INT,
    visit_area_type_cd VARCHAR(20) NOT NULL,
    revisit_yn CHAR(1),
    visit_chc_reason_cd VARCHAR(20),
    lodging_type_cd VARCHAR(20),
    dgstfn TINYINT,
    revisit_intention TINYINT,
    rcmdtn_intention TINYINT,
    sgg_cd VARCHAR(20),
    PRIMARY KEY (travel_id, visit_area_id),
    INDEX idx_aihub_visit_name (visit_area_nm),
    INDEX idx_aihub_visit_poi (poi_id),
    INDEX idx_aihub_visit_type (visit_area_type_cd),
    INDEX idx_aihub_visit_region (sgg_cd),
    INDEX idx_aihub_visit_coordinates (x_coord, y_coord),
    INDEX idx_aihub_visit_scores (dgstfn, revisit_intention, rcmdtn_intention),
    CONSTRAINT fk_aihub_visit_travel FOREIGN KEY (travel_id)
        REFERENCES aihub_travel (travel_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS aihub_activity (
    travel_id VARCHAR(20) NOT NULL,
    visit_area_id VARCHAR(20) NOT NULL,
    activity_type_cd VARCHAR(20) NOT NULL,
    activity_type_seq SMALLINT NOT NULL,
    activity_etc VARCHAR(500),
    activity_dtl TEXT,
    rsvt_yn CHAR(1),
    expnd_se VARCHAR(20),
    admission_se VARCHAR(20),
    PRIMARY KEY (
        travel_id,
        visit_area_id,
        activity_type_cd,
        activity_type_seq
    ),
    INDEX idx_aihub_activity_type (activity_type_cd),
    CONSTRAINT fk_aihub_activity_visit FOREIGN KEY (travel_id, visit_area_id)
        REFERENCES aihub_visit (travel_id, visit_area_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS aihub_activity_consume (
    travel_id VARCHAR(20) NOT NULL,
    visit_area_id VARCHAR(20) NOT NULL,
    activity_type_cd VARCHAR(20) NOT NULL,
    activity_type_seq SMALLINT NOT NULL,
    consume_his_seq SMALLINT NOT NULL,
    consume_his_sno SMALLINT NOT NULL,
    payment_num SMALLINT NOT NULL,
    brno VARCHAR(20),
    store_nm VARCHAR(255),
    road_nm_addr VARCHAR(500),
    lotno_addr VARCHAR(500),
    road_nm_cd VARCHAR(20),
    lotno_cd VARCHAR(20),
    payment_dt DATETIME,
    payment_mthd_se VARCHAR(20) NOT NULL,
    payment_amt_won BIGINT,
    payment_etc TEXT,
    sgg_cd VARCHAR(20),
    PRIMARY KEY (
        travel_id,
        visit_area_id,
        activity_type_cd,
        activity_type_seq,
        consume_his_seq,
        consume_his_sno
    ),
    INDEX idx_aihub_activity_consume_payment (payment_dt, payment_amt_won),
    INDEX idx_aihub_activity_consume_store (store_nm),
    INDEX idx_aihub_activity_consume_region (sgg_cd),
    CONSTRAINT fk_aihub_activity_consume_activity FOREIGN KEY (
        travel_id,
        visit_area_id,
        activity_type_cd,
        activity_type_seq
    ) REFERENCES aihub_activity (
        travel_id,
        visit_area_id,
        activity_type_cd,
        activity_type_seq
    ) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS aihub_move (
    travel_id VARCHAR(20) NOT NULL,
    trip_id VARCHAR(20) NOT NULL,
    start_visit_area_id VARCHAR(20),
    end_visit_area_id VARCHAR(20),
    start_dt_min DATETIME,
    end_dt_min DATETIME,
    mvmn_cd_1 VARCHAR(20),
    mvmn_cd_2 VARCHAR(20),
    PRIMARY KEY (travel_id, trip_id),
    INDEX idx_aihub_move_start (travel_id, start_visit_area_id),
    INDEX idx_aihub_move_end (travel_id, end_visit_area_id),
    INDEX idx_aihub_move_transport (mvmn_cd_1, mvmn_cd_2),
    CONSTRAINT fk_aihub_move_travel FOREIGN KEY (travel_id)
        REFERENCES aihub_travel (travel_id) ON DELETE CASCADE,
    CONSTRAINT fk_aihub_move_start_visit FOREIGN KEY (
        travel_id, start_visit_area_id
    ) REFERENCES aihub_visit (travel_id, visit_area_id),
    CONSTRAINT fk_aihub_move_end_visit FOREIGN KEY (
        travel_id, end_visit_area_id
    ) REFERENCES aihub_visit (travel_id, visit_area_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS aihub_lodge_consume (
    lodge_consume_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    travel_id VARCHAR(20) NOT NULL,
    lodging_nm VARCHAR(255) NOT NULL,
    lodging_payment_seq SMALLINT NOT NULL,
    lodging_type_cd VARCHAR(20) NOT NULL,
    rsvt_yn CHAR(1) NOT NULL,
    chk_in_dt_min DATETIME,
    chk_out_dt_min DATETIME,
    payment_num SMALLINT NOT NULL,
    brno VARCHAR(20),
    store_nm VARCHAR(255),
    road_nm_addr VARCHAR(500),
    lotno_addr VARCHAR(500),
    road_nm_cd VARCHAR(20),
    lotno_cd VARCHAR(20),
    payment_dt DATETIME,
    payment_mthd_se VARCHAR(20) NOT NULL,
    payment_amt_won BIGINT NOT NULL,
    payment_etc TEXT,
    INDEX idx_aihub_lodge_travel (travel_id),
    INDEX idx_aihub_lodge_name (lodging_nm),
    INDEX idx_aihub_lodge_payment (payment_dt, payment_amt_won),
    CONSTRAINT fk_aihub_lodge_travel FOREIGN KEY (travel_id)
        REFERENCES aihub_travel (travel_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS aihub_movement_consume (
    movement_consume_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    travel_id VARCHAR(20) NOT NULL,
    mvmn_se VARCHAR(20) NOT NULL,
    payment_se VARCHAR(20) NOT NULL,
    payment_seq SMALLINT NOT NULL,
    mvmn_se_nm VARCHAR(100) NOT NULL,
    rsvt_yn CHAR(1),
    payment_num SMALLINT NOT NULL,
    brno VARCHAR(20),
    store_nm VARCHAR(255),
    payment_dt DATETIME,
    payment_mthd_se VARCHAR(20),
    payment_amt_won BIGINT NOT NULL,
    payment_etc TEXT,
    INDEX idx_aihub_movement_travel (travel_id),
    INDEX idx_aihub_movement_type (mvmn_se),
    INDEX idx_aihub_movement_payment (payment_dt, payment_amt_won),
    CONSTRAINT fk_aihub_movement_travel FOREIGN KEY (travel_id)
        REFERENCES aihub_travel (travel_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS aihub_advance_consume (
    travel_id VARCHAR(20) NOT NULL,
    adv_seq SMALLINT NOT NULL,
    adv_nm VARCHAR(255) NOT NULL,
    payment_num SMALLINT NOT NULL,
    brno VARCHAR(20),
    store_nm VARCHAR(255),
    road_nm_addr VARCHAR(500),
    lotno_addr VARCHAR(500),
    road_nm_cd VARCHAR(20),
    lotno_cd VARCHAR(20),
    payment_dt DATETIME,
    payment_mthd_se VARCHAR(20) NOT NULL,
    payment_amt_won BIGINT NOT NULL,
    payment_etc TEXT,
    sgg_cd VARCHAR(20),
    PRIMARY KEY (travel_id, adv_seq),
    INDEX idx_aihub_advance_payment (payment_dt, payment_amt_won),
    INDEX idx_aihub_advance_region (sgg_cd),
    CONSTRAINT fk_aihub_advance_travel FOREIGN KEY (travel_id)
        REFERENCES aihub_travel (travel_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
