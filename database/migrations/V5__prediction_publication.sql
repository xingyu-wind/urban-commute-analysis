-- Independent of warehouse_current. Offline publication only; UTC exclusive cutoff.
CREATE TABLE prediction_model (
  model_version CHAR(64) PRIMARY KEY,
  input_sha256 CHAR(64) NOT NULL,
  configuration JSON NOT NULL,
  artifacts JSON NOT NULL
) ENGINE=InnoDB;
CREATE TABLE prediction_job (
  job_id CHAR(32) PRIMARY KEY,
  model_version CHAR(64) NOT NULL,
  city_id VARCHAR(64) NOT NULL,
  dataset_id VARCHAR(64) NOT NULL,
  data_cutoff DATETIME(3) NOT NULL,
  generated_at DATETIME(3) NOT NULL,
  content_sha256 CHAR(64) NOT NULL UNIQUE,
  status VARCHAR(16) NOT NULL,
  attempts INT NOT NULL DEFAULT 1,
  published_at DATETIME(3) NULL,
  document JSON NOT NULL,
  UNIQUE (job_id,city_id,dataset_id),
  FOREIGN KEY (model_version) REFERENCES prediction_model(model_version),
  FOREIGN KEY (city_id) REFERENCES city(id),
  FOREIGN KEY (dataset_id) REFERENCES dataset_registry(dataset_id),
  CHECK (status IN ('STAGING','FAILED','PUBLISHED')),
  CHECK (attempts > 0),
  CHECK (status <> 'PUBLISHED' OR published_at IS NOT NULL)
) ENGINE=InnoDB;
CREATE TABLE prediction_evaluation (
  job_id CHAR(32) NOT NULL,
  split VARCHAR(16) NOT NULL,
  model_name VARCHAR(32) NOT NULL,
  evaluation JSON NOT NULL,
  PRIMARY KEY (job_id,split,model_name),
  FOREIGN KEY (job_id) REFERENCES prediction_job(job_id),
  CHECK (split IN ('validation','test'))
) ENGINE=InnoDB;
CREATE TABLE prediction_result (
  job_id CHAR(32) NOT NULL,
  step INT NOT NULL,
  forecast_date DATE NOT NULL,
  value DECIMAL(9,6) NOT NULL,
  PRIMARY KEY (job_id,step),
  UNIQUE (job_id,forecast_date),
  FOREIGN KEY (job_id) REFERENCES prediction_job(job_id),
  CHECK (step BETWEEN 1 AND 7),
  CHECK (value BETWEEN 0 AND 10)
) ENGINE=InnoDB;
CREATE TABLE prediction_current (
  city_id VARCHAR(64) NOT NULL,
  dataset_id VARCHAR(64) NOT NULL,
  job_id CHAR(32) NOT NULL UNIQUE,
  PRIMARY KEY (city_id,dataset_id),
  FOREIGN KEY (job_id,city_id,dataset_id) REFERENCES prediction_job(job_id,city_id,dataset_id)
) ENGINE=InnoDB;
