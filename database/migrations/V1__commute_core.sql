-- S3 core schema for MySQL 8.4; intentionally contains NO data and NO DROP statements.
-- All DATETIME values are UTC by data contract; never treat them as local wall-clock time.
CREATE TABLE dataset_registry (
  dataset_id VARCHAR(64) NOT NULL PRIMARY KEY,
  source_name VARCHAR(120) NOT NULL,
  source_type VARCHAR(32) NOT NULL,
  license_status VARCHAR(20) NOT NULL,
  license_url VARCHAR(500) NULL,
  dataset_version VARCHAR(64) NOT NULL,
  description VARCHAR(500) NOT NULL,
  registered_at DATETIME(3) NOT NULL DEFAULT (UTC_TIMESTAMP(3)),
  CONSTRAINT ck_dataset_source CHECK (source_type IN ('dev_seed','synthetic_test','historical_snapshot','authorized_live','simulation','mock','forecast')),
  CONSTRAINT ck_dataset_license CHECK (license_status IN ('not_applicable','unverified','authorized')),
  CONSTRAINT ck_live_authorized CHECK (source_type <> 'authorized_live' OR license_status = 'authorized')
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE city (
  id VARCHAR(64) NOT NULL PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  dataset_id VARCHAR(64) NOT NULL,
  created_at DATETIME(3) NOT NULL DEFAULT (UTC_TIMESTAMP(3)),
  CONSTRAINT fk_city_dataset FOREIGN KEY (dataset_id) REFERENCES dataset_registry(dataset_id),
  CONSTRAINT ck_city_id CHECK (id REGEXP '^[a-z][a-z0-9]*(-[a-z0-9]+)*$'),
  INDEX idx_city_dataset (dataset_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE region (
  id VARCHAR(64) NOT NULL PRIMARY KEY,
  city_id VARCHAR(64) NOT NULL,
  name VARCHAR(100) NOT NULL,
  center_lat DECIMAL(9,6) NULL,
  center_lon DECIMAL(9,6) NULL,
  coordinate_system VARCHAR(16) NULL,
  CONSTRAINT fk_region_city FOREIGN KEY (city_id) REFERENCES city(id),
  CONSTRAINT uq_region_city_name UNIQUE (city_id,name),
  CONSTRAINT uq_region_city_id UNIQUE (id,city_id),
  CONSTRAINT ck_region_coordinates CHECK (
    (center_lat IS NULL AND center_lon IS NULL AND coordinate_system IS NULL) OR
    (center_lat BETWEEN -90 AND 90 AND center_lon BETWEEN -180 AND 180 AND coordinate_system = 'WGS84')
  )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE road_segment (
  id VARCHAR(64) NOT NULL PRIMARY KEY,
  city_id VARCHAR(64) NOT NULL,
  region_id VARCHAR(64) NULL,
  name VARCHAR(160) NOT NULL,
  CONSTRAINT fk_road_city FOREIGN KEY (city_id) REFERENCES city(id),
  CONSTRAINT fk_road_region_same_city FOREIGN KEY (region_id,city_id) REFERENCES region(id,city_id),
  CONSTRAINT uq_road_city_id UNIQUE (id,city_id),
  CONSTRAINT uq_road_city_name UNIQUE (city_id,name),
  INDEX idx_road_region (region_id,city_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE traffic_observation (
  id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  dataset_id VARCHAR(64) NOT NULL,
  city_id VARCHAR(64) NOT NULL,
  region_id VARCHAR(64) NULL,
  road_segment_id VARCHAR(64) NULL,
  target_type VARCHAR(8) NOT NULL,
  target_id VARCHAR(64) NOT NULL,
  observed_at DATETIME(3) NOT NULL,
  collected_at DATETIME(3) NOT NULL,
  avg_speed_kmh DECIMAL(6,2) NOT NULL,
  congestion_index DECIMAL(4,2) NOT NULL,
  CONSTRAINT fk_obs_dataset FOREIGN KEY (dataset_id) REFERENCES dataset_registry(dataset_id),
  CONSTRAINT fk_obs_city FOREIGN KEY (city_id) REFERENCES city(id),
  CONSTRAINT fk_obs_region_same_city FOREIGN KEY (region_id,city_id) REFERENCES region(id,city_id),
  CONSTRAINT fk_obs_road_same_city FOREIGN KEY (road_segment_id,city_id) REFERENCES road_segment(id,city_id),
  CONSTRAINT ck_obs_target CHECK (
    (target_type='CITY' AND target_id=city_id AND region_id IS NULL AND road_segment_id IS NULL) OR
    (target_type='REGION' AND target_id=region_id AND region_id IS NOT NULL AND road_segment_id IS NULL) OR
    (target_type='ROAD' AND target_id=road_segment_id AND road_segment_id IS NOT NULL AND region_id IS NULL)
  ),
  CONSTRAINT ck_obs_speed CHECK (avg_speed_kmh BETWEEN 0 AND 250),
  CONSTRAINT ck_obs_congestion CHECK (congestion_index BETWEEN 0 AND 10),
  CONSTRAINT uq_obs_dataset_target_time UNIQUE (dataset_id,target_type,target_id,observed_at),
  INDEX idx_obs_city_time (city_id,observed_at),
  INDEX idx_obs_region_time (region_id,observed_at),
  INDEX idx_obs_road_time (road_segment_id,observed_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
