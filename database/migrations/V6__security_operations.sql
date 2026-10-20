-- S8: forward-only security and independent adapter jobs; no publication pointer changes.
CREATE TABLE app_user (
 username VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
 password_hash VARCHAR(100) NOT NULL,
 role VARCHAR(16) NOT NULL,
 enabled BOOLEAN NOT NULL DEFAULT TRUE,
 CHECK (role IN ('ADMIN','READER'))
) ENGINE=InnoDB;
CREATE TABLE security_audit (
 id BIGINT AUTO_INCREMENT PRIMARY KEY,
 occurred_at DATETIME(3) NOT NULL DEFAULT (UTC_TIMESTAMP(3)),
 actor VARCHAR(64) NOT NULL,
 action VARCHAR(48) NOT NULL,
 object_id VARCHAR(64) NULL,
 outcome VARCHAR(32) NOT NULL,
 request_id VARCHAR(64) NULL
) ENGINE=InnoDB;
CREATE TABLE managed_import (
 id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
 extension VARCHAR(4) NOT NULL,
 input_sha256 CHAR(64) NOT NULL,
 proposal JSON NOT NULL,
 configuration JSON NULL,
 configuration_sha256 CHAR(64) NULL,
 confirmed_by VARCHAR(64) NULL,
 confirmed_at DATETIME(3) NULL,
 created_by VARCHAR(64) NOT NULL,
 created_at DATETIME(3) NOT NULL DEFAULT (UTC_TIMESTAMP(3)),
 CHECK (extension IN ('csv','json')),
 CHECK ((configuration IS NULL AND confirmed_by IS NULL AND confirmed_at IS NULL) OR
        (configuration IS NOT NULL AND configuration_sha256 IS NOT NULL AND confirmed_by IS NOT NULL AND confirmed_at IS NOT NULL))
) ENGINE=InnoDB;
CREATE TABLE managed_job (
 id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
 import_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL UNIQUE,
 status VARCHAR(16) NOT NULL,
 attempts INT NOT NULL DEFAULT 1,
 operated_by VARCHAR(64) NOT NULL,
 input_sha256 CHAR(64) NOT NULL,
 mapping_sha256 CHAR(64) NOT NULL,
 output_sha256 CHAR(64) NULL,
 quality JSON NULL,
 error_code VARCHAR(48) NULL,
 updated_at DATETIME(3) NOT NULL DEFAULT (UTC_TIMESTAMP(3)),
 FOREIGN KEY (import_id) REFERENCES managed_import(id),
 CHECK (status IN ('RUNNING','FAILED','SUCCEEDED')),
 CHECK (attempts BETWEEN 1 AND 3)
) ENGINE=InnoDB;
