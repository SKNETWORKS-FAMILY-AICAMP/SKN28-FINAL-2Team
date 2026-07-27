CREATE TABLE IF NOT EXISTS aihub_places (
    aihub_place_id BIGINT PRIMARY KEY,
    canonical_name VARCHAR(255) NOT NULL,
    normalized_name VARCHAR(255) NOT NULL,
    aliases JSON NOT NULL,
    poi_ids JSON NOT NULL,
    road_nm_addr VARCHAR(500),
    lotno_addr VARCHAR(500),
    longitude DECIMAL(16, 12),
    latitude DECIMAL(16, 12),
    visit_area_type_cd VARCHAR(20),
    visit_count INT NOT NULL,
    identity_method VARCHAR(30) NOT NULL,
    tourapi_content_id BIGINT,
    match_status ENUM('MATCHED', 'REVIEW', 'UNMATCHED') NOT NULL,
    match_method VARCHAR(40) NOT NULL,
    name_similarity DECIMAL(5, 4),
    distance_m DECIMAL(10, 2),
    confidence_score DECIMAL(5, 4) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_aihub_places_normalized_name (normalized_name),
    INDEX idx_aihub_places_tourapi (tourapi_content_id),
    INDEX idx_aihub_places_status (match_status),
    INDEX idx_aihub_places_coordinates (longitude, latitude),
    CONSTRAINT fk_aihub_places_tourapi FOREIGN KEY (tourapi_content_id)
        REFERENCES places (content_id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
