-- S6: immutable releases and an atomic pointer. UTC DATETIME(3), no changes to V1-V3.
CREATE TABLE warehouse_release (
  release_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
  status VARCHAR(16) NOT NULL,
  content_sha256 CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  ads_sha256 CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  window_from DATETIME(3) NOT NULL,
  window_to DATETIME(3) NOT NULL,
  captured_at DATETIME(3) NOT NULL,
  published_at DATETIME(3) NULL,
  manifest JSON NOT NULL,
  row_count BIGINT NOT NULL,
  error_code VARCHAR(64) NULL,
  CONSTRAINT ck_warehouse_status CHECK (status IN ('STAGING','FAILED','PUBLISHED')),
  CONSTRAINT ck_warehouse_window CHECK (window_from < window_to AND row_count > 0),
  CONSTRAINT ck_warehouse_published CHECK (status <> 'PUBLISHED' OR published_at IS NOT NULL)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE warehouse_metric (
  release_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  dataset_id VARCHAR(64) NOT NULL,
  dataset_version VARCHAR(64) NOT NULL,
  source_type VARCHAR(32) NOT NULL,
  city_id VARCHAR(64) NOT NULL,
  target_type VARCHAR(8) NOT NULL,
  target_id VARCHAR(64) NOT NULL,
  road_region_id VARCHAR(64) NULL,
  grain VARCHAR(8) NOT NULL,
  bucket_start DATETIME(3) NOT NULL,
  sample_count BIGINT NOT NULL,
  speed_sum DECIMAL(24,2) NOT NULL,
  congestion_sum DECIMAL(24,2) NOT NULL,
  avg_speed_kmh DECIMAL(6,2) NOT NULL,
  congestion_index DECIMAL(4,2) NOT NULL,
  observed_from DATETIME(3) NOT NULL,
  observed_to DATETIME(3) NOT NULL,
  PRIMARY KEY (release_id,dataset_id,city_id,target_type,target_id,grain,bucket_start),
  FOREIGN KEY (release_id) REFERENCES warehouse_release(release_id),
  FOREIGN KEY (dataset_id) REFERENCES dataset_registry(dataset_id),
  FOREIGN KEY (city_id) REFERENCES city(id),
  CONSTRAINT ck_warehouse_metric CHECK (sample_count>0 AND avg_speed_kmh BETWEEN 0 AND 250
    AND congestion_index BETWEEN 0 AND 10 AND observed_from<=observed_to
    AND target_type IN ('CITY','REGION','ROAD') AND grain IN ('WINDOW','DAY','HOUR')
    AND (target_type='ROAD' OR road_region_id IS NULL))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE warehouse_current (
  singleton TINYINT NOT NULL PRIMARY KEY,
  release_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  FOREIGN KEY (release_id) REFERENCES warehouse_release(release_id),
  CONSTRAINT ck_warehouse_singleton CHECK (singleton=1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
