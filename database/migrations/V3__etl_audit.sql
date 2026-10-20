-- S5: immutable source snapshots and atomic, recoverable observation imports.
CREATE TABLE etl_source (
  source_sha256 CHAR(64) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
  dataset_id VARCHAR(64) NOT NULL,
  manifest JSON NOT NULL,
  registered_at DATETIME(3) NOT NULL DEFAULT (UTC_TIMESTAMP(3)),
  CONSTRAINT fk_etl_source_dataset FOREIGN KEY (dataset_id) REFERENCES dataset_registry(dataset_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE etl_batch (
  batch_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
  source_sha256 CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  file_sha256 CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  file_name VARCHAR(255) NOT NULL,
  status VARCHAR(16) NOT NULL,
  attempts INT NOT NULL DEFAULT 1,
  input_count INT NOT NULL,
  accepted_count INT NOT NULL,
  rejected_count INT NOT NULL,
  duplicate_count INT NOT NULL,
  written_count INT NOT NULL DEFAULT 0,
  existing_count INT NOT NULL DEFAULT 0,
  conflict_count INT NOT NULL DEFAULT 0,
  conflict_details JSON NULL,
  started_at DATETIME(3) NOT NULL DEFAULT (UTC_TIMESTAMP(3)),
  finished_at DATETIME(3) NULL,
  error_code VARCHAR(64) NULL,
  CONSTRAINT fk_etl_batch_source FOREIGN KEY (source_sha256) REFERENCES etl_source(source_sha256),
  CONSTRAINT ck_etl_batch_status CHECK (status IN ('RUNNING','FAILED','SUCCEEDED')),
  CONSTRAINT ck_etl_batch_counts CHECK (input_count = accepted_count + rejected_count + duplicate_count
    AND accepted_count >= 0 AND rejected_count >= 0 AND duplicate_count >= 0
    AND written_count >= 0 AND existing_count >= 0 AND conflict_count >= 0
    AND (status <> 'SUCCEEDED' OR accepted_count = written_count + existing_count)),
  INDEX idx_etl_batch_file (file_sha256)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE etl_rejection (
  batch_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  record_number INT NOT NULL,
  reason VARCHAR(64) NOT NULL,
  raw_record JSON NOT NULL,
  PRIMARY KEY (batch_id,record_number),
  FOREIGN KEY (batch_id) REFERENCES etl_batch(batch_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE etl_batch_observation (
  batch_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  observation_id BIGINT NOT NULL,
  disposition VARCHAR(8) NOT NULL,
  PRIMARY KEY (batch_id,observation_id),
  FOREIGN KEY (batch_id) REFERENCES etl_batch(batch_id),
  FOREIGN KEY (observation_id) REFERENCES traffic_observation(id),
  CONSTRAINT ck_etl_disposition CHECK (disposition IN ('WRITTEN','EXISTING'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
