-- Preserve V1 and its checksum. Existing invalid rows intentionally fail this migration.
ALTER TABLE city
  DROP CHECK ck_city_id,
  ADD CONSTRAINT ck_city_id CHECK (REGEXP_LIKE(id, '^[a-z][a-z0-9]*(-[a-z0-9]+)*$', 'c')),
  ADD CONSTRAINT ck_city_name CHECK (REGEXP_LIKE(name, '[^[:space:]]'));

ALTER TABLE region
  DROP CHECK ck_region_coordinates,
  ADD CONSTRAINT ck_region_coordinates CHECK (
    (center_lat IS NULL AND center_lon IS NULL AND coordinate_system IS NULL) OR
    (center_lat IS NOT NULL AND center_lon IS NOT NULL AND coordinate_system IS NOT NULL
      AND center_lat BETWEEN -90 AND 90 AND center_lon BETWEEN -180 AND 180
      AND BINARY coordinate_system = BINARY 'WGS84')
  );

-- Several segments of the same named road can exist within a city.
-- Stable segment ID remains the identity and the observation deduplication target.
ALTER TABLE road_segment
  ADD INDEX idx_road_city_name (city_id,name),
  DROP INDEX uq_road_city_name;

ALTER TABLE traffic_observation
  ADD CONSTRAINT ck_obs_time_order CHECK (collected_at >= observed_at),
  ADD CONSTRAINT ck_obs_target_case CHECK (BINARY target_type IN ('CITY','REGION','ROAD'));

-- Genuine observed sources require authorization; generated sources cannot claim it.
ALTER TABLE dataset_registry
  ADD CONSTRAINT ck_dataset_id CHECK (REGEXP_LIKE(dataset_id, '[^[:space:]]')),
  ADD CONSTRAINT ck_dataset_source_case CHECK (BINARY source_type IN
    ('dev_seed','synthetic_test','historical_snapshot','authorized_live','simulation','mock','forecast')),
  ADD CONSTRAINT ck_dataset_license_case CHECK (BINARY license_status IN ('not_applicable','unverified','authorized')),
  ADD CONSTRAINT ck_dataset_provenance CHECK (
    (source_type IN ('historical_snapshot','authorized_live') AND license_status = 'authorized') OR
    (source_type IN ('dev_seed','synthetic_test','simulation','mock','forecast')
      AND license_status = 'not_applicable')
  );
