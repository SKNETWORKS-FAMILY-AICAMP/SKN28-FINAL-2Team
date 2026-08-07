CREATE TABLE IF NOT EXISTS travel_packages (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    package_id VARCHAR(50) NOT NULL UNIQUE,
    title VARCHAR(255) NOT NULL,
    summary TEXT,
    region VARCHAR(100) NOT NULL,
    duration_days TINYINT NOT NULL,
    estimated_price INT NOT NULL,
    match_profile JSON NOT NULL,
    schema_version VARCHAR(20) NOT NULL DEFAULT '1.0',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT chk_package_duration CHECK (duration_days BETWEEN 1 AND 5),
    CONSTRAINT chk_package_price CHECK (estimated_price >= 0),
    INDEX idx_package_region_duration (region, duration_days),
    INDEX idx_package_price (estimated_price),
    INDEX idx_package_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS package_items (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    package_db_id BIGINT NOT NULL,
    day_no TINYINT NULL,
    sequence TINYINT NULL,
    item_type VARCHAR(20) NOT NULL,
    content_id BIGINT NOT NULL,
    stay_minutes SMALLINT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_package_items_package
        FOREIGN KEY (package_db_id) REFERENCES travel_packages(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_package_items_place
        FOREIGN KEY (content_id) REFERENCES places(content_id),
    CONSTRAINT chk_package_item_type
        CHECK (item_type IN ('tourism', 'restaurant', 'hotel')),
    CONSTRAINT chk_package_item_day
        CHECK (day_no IS NULL OR day_no BETWEEN 1 AND 5),
    UNIQUE KEY uq_package_schedule (package_db_id, day_no, sequence),
    INDEX idx_package_item_schedule (package_db_id, day_no, sequence),
    INDEX idx_package_item_content (content_id),
    INDEX idx_package_item_type (item_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
