-- CI-only / disposable MySQL instance fixture. Fully synthetic labels; no observed traffic is inserted.
-- Safe on replay; NEVER execute against an existing production database.
INSERT INTO dataset_registry
  (dataset_id,source_name,source_type,license_status,dataset_version,description)
VALUES
  ('s3-synthetic-cities-v1','S3 generated catalog fixture','synthetic_test','not_applicable','v1','Invented test city labels; no measured commute data')
ON DUPLICATE KEY UPDATE dataset_id = dataset_id;
INSERT INTO city (id,name,dataset_id) VALUES
  ('sample-beijing','北京','s3-synthetic-cities-v1'),
  ('sample-shanghai','上海','s3-synthetic-cities-v1')
ON DUPLICATE KEY UPDATE id = id;
