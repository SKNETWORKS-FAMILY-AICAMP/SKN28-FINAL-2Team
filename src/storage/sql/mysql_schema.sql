CREATE TABLE IF NOT EXISTS content_types (
    content_type_id INT PRIMARY KEY,
    name VARCHAR(100) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS lcls_categories (
    lcls3_code VARCHAR(30) PRIMARY KEY,
    lcls1_code VARCHAR(20) NOT NULL,
    lcls1_name VARCHAR(100),
    lcls2_code VARCHAR(20) NOT NULL,
    lcls2_name VARCHAR(100),
    lcls3_name VARCHAR(100)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS places (
    content_id BIGINT PRIMARY KEY,
    content_type_id INT NOT NULL,
    lcls3_code VARCHAR(30) NOT NULL,
    title VARCHAR(255) NOT NULL,
    addr1 VARCHAR(500),
    addr2 VARCHAR(255),
    area_code INT,
    sigungu_code INT,
    zipcode VARCHAR(20),
    longitude DECIMAL(16,12) NOT NULL,
    latitude DECIMAL(16,12) NOT NULL,
    location POINT NOT NULL SRID 4326,
    map_level INT,
    api_created_at DATETIME,
    api_modified_at DATETIME,
    CONSTRAINT fk_places_content_type FOREIGN KEY (content_type_id)
        REFERENCES content_types(content_type_id),
    CONSTRAINT fk_places_lcls_category FOREIGN KEY (lcls3_code)
        REFERENCES lcls_categories(lcls3_code),
    INDEX idx_places_content_type (content_type_id),
    INDEX idx_places_lcls3 (lcls3_code),
    INDEX idx_places_area (area_code, sigungu_code),
    SPATIAL INDEX idx_places_location (location)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS place_common_details (
    content_id BIGINT PRIMARY KEY,
    tel VARCHAR(255),
    tel_name VARCHAR(255),
    homepage TEXT,
    overview MEDIUMTEXT,
    copyright_code VARCHAR(30),
    CONSTRAINT fk_common_place FOREIGN KEY (content_id)
        REFERENCES places(content_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS place_intro (
    content_id BIGINT PRIMARY KEY,
    info_center TEXT,
    opening_hours TEXT,
    closed_days TEXT,
    parking TEXT,
    reservation TEXT,
    use_fee TEXT,
    check_in_time TEXT,
    check_out_time TEXT,
    type_details JSON NOT NULL,
    CONSTRAINT fk_intro_place FOREIGN KEY (content_id)
        REFERENCES places(content_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS place_images (
    image_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    content_id BIGINT NOT NULL,
    image_url TEXT NOT NULL,
    thumbnail_url TEXT,
    image_role VARCHAR(50) NOT NULL,
    display_order INT NOT NULL DEFAULT 0,
    CONSTRAINT fk_image_place FOREIGN KEY (content_id)
        REFERENCES places(content_id) ON DELETE CASCADE,
    UNIQUE KEY uq_place_image_role (content_id, image_role, display_order),
    INDEX idx_image_content (content_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS place_search_documents (
    search_document_id BIGINT PRIMARY KEY,
    content_id BIGINT NOT NULL,
    document_type VARCHAR(50) NOT NULL,
    rag_eligible BOOLEAN NOT NULL DEFAULT FALSE,
    route_eligible BOOLEAN NOT NULL DEFAULT FALSE,
    schedule_eligible BOOLEAN NOT NULL DEFAULT FALSE,
    requires_verification BOOLEAN NOT NULL DEFAULT FALSE,
    exclusion_reason TEXT,
    search_text MEDIUMTEXT,
    tags JSON NOT NULL,
    preprocessing_version VARCHAR(50),
    generated_at DATETIME(6),
    CONSTRAINT fk_search_document_place FOREIGN KEY (content_id)
        REFERENCES places(content_id) ON DELETE CASCADE,
    INDEX idx_search_document_content (content_id),
    INDEX idx_search_document_flags (rag_eligible, route_eligible, schedule_eligible),
    INDEX idx_search_document_type (document_type),
    FULLTEXT INDEX ft_search_text (search_text) WITH PARSER ngram
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS place_search_chunks (
    chunk_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    search_document_id BIGINT NOT NULL,
    chunk_index INT NOT NULL,
    chunk_text MEDIUMTEXT NOT NULL,
    CONSTRAINT fk_chunk_search_document FOREIGN KEY (search_document_id)
        REFERENCES place_search_documents(search_document_id) ON DELETE CASCADE,
    UNIQUE KEY uq_search_document_chunk (search_document_id, chunk_index),
    INDEX idx_chunk_search_document (search_document_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS ingestion_runs (
    ingestion_run_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    source_name VARCHAR(255) NOT NULL,
    dataset VARCHAR(50) NOT NULL,
    started_at DATETIME(6) NOT NULL,
    finished_at DATETIME(6),
    status VARCHAR(30) NOT NULL,
    INDEX idx_ingestion_status (status, started_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS api_fetch_records (
    fetch_record_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    ingestion_run_id BIGINT NOT NULL,
    content_id BIGINT NOT NULL,
    endpoint VARCHAR(100) NOT NULL,
    fetch_status VARCHAR(30) NOT NULL,
    fetch_error TEXT,
    fetched_at DATETIME(6),
    raw_payload JSON NOT NULL,
    CONSTRAINT fk_fetch_ingestion_run FOREIGN KEY (ingestion_run_id)
        REFERENCES ingestion_runs(ingestion_run_id) ON DELETE CASCADE,
    CONSTRAINT fk_fetch_place FOREIGN KEY (content_id)
        REFERENCES places(content_id) ON DELETE CASCADE,
    INDEX idx_fetch_run (ingestion_run_id),
    INDEX idx_fetch_place_endpoint (content_id, endpoint),
    INDEX idx_fetch_status (fetch_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
