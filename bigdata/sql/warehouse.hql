-- All four layers are calculated by Hive, never populated with Python aggregates.
SET hive.local.time.zone=UTC;
SET hive.execution.engine=tez;
SET tez.local.mode=true;
SET tez.ignore.lib.uris=true;
SET tez.runtime.optimize.local.fetch=true;
SET hive.exec.dynamic.partition=true;
SET hive.exec.dynamic.partition.mode=nonstrict;
SET hive.exec.max.dynamic.partitions=1000;
SET hive.exec.max.dynamic.partitions.pernode=1000;
CREATE DATABASE IF NOT EXISTS commute_s6 LOCATION '/s6/warehouse';
USE commute_s6;

CREATE EXTERNAL TABLE IF NOT EXISTS ods_observation (
  observation_id BIGINT, dataset_id STRING, city_id STRING, region_id STRING,
  road_segment_id STRING, target_type STRING, target_id STRING,
  observed_at STRING, collected_at STRING, avg_speed_kmh DECIMAL(6,2),
  congestion_index DECIMAL(4,2), dataset_version STRING, source_type STRING,
  source_sha256 STRING, batch_id STRING, road_region_id STRING
) PARTITIONED BY (snapshot_id STRING)
ROW FORMAT DELIMITED FIELDS TERMINATED BY '\t'
STORED AS TEXTFILE LOCATION '/s6/ods';
ALTER TABLE ods_observation ADD IF NOT EXISTS PARTITION (snapshot_id='${hivevar:snapshot}')
LOCATION '/s6/ods/snapshot_id=${hivevar:snapshot}';

-- The admission gate checked catalogs and full row content against committed MySQL.
-- DWD additionally rejects bad types/times/metric ranges via an assert query below.
CREATE EXTERNAL TABLE IF NOT EXISTS dwd_observation (
  observation_id BIGINT, dataset_id STRING, city_id STRING, target_type STRING,
  target_id STRING, road_region_id STRING, observed_at TIMESTAMP, collected_at TIMESTAMP,
  avg_speed_kmh DECIMAL(6,2), congestion_index DECIMAL(4,2), dataset_version STRING,
  source_type STRING, batch_ids ARRAY<STRING>, source_hashes ARRAY<STRING>
) PARTITIONED BY (snapshot_id STRING, observed_date STRING) STORED AS ORC LOCATION '/s6/dwd';

SELECT assert_true(COUNT(*)=0) FROM ods_observation WHERE snapshot_id='${hivevar:snapshot}' AND (
  observed_at IS NULL OR collected_at IS NULL OR
  CAST(regexp_replace(regexp_replace(observed_at,'T',' '),'Z','') AS TIMESTAMP) IS NULL OR
  CAST(regexp_replace(regexp_replace(collected_at,'T',' '),'Z','') AS TIMESTAMP) IS NULL OR
  collected_at<observed_at OR observed_at<'${hivevar:from}' OR observed_at>='${hivevar:to}' OR
  avg_speed_kmh IS NULL OR avg_speed_kmh<0 OR avg_speed_kmh>250 OR
  congestion_index IS NULL OR congestion_index<0 OR congestion_index>10 OR
  target_type NOT IN ('CITY','REGION','ROAD') OR
  NOT ((target_type='CITY' AND target_id=city_id AND region_id IS NULL AND road_segment_id IS NULL)
    OR (target_type='REGION' AND target_id=region_id AND road_segment_id IS NULL)
    OR (target_type='ROAD' AND target_id=road_segment_id AND region_id IS NULL))
);

INSERT OVERWRITE TABLE dwd_observation PARTITION(snapshot_id='${hivevar:snapshot}',observed_date)
SELECT observation_id,dataset_id,city_id,target_type,target_id,road_region_id,
  CAST(regexp_replace(regexp_replace(observed_at,'T',' '),'Z','') AS TIMESTAMP),
  CAST(regexp_replace(regexp_replace(collected_at,'T',' '),'Z','') AS TIMESTAMP),
  avg_speed_kmh,congestion_index,dataset_version,source_type,
  sort_array(collect_set(batch_id)),sort_array(collect_set(source_sha256)),substr(observed_at,1,10)
FROM ods_observation WHERE snapshot_id='${hivevar:snapshot}'
GROUP BY observation_id,dataset_id,city_id,target_type,target_id,road_region_id,observed_at,collected_at,
  avg_speed_kmh,congestion_index,dataset_version,source_type;
SELECT assert_true(COUNT(*)=COUNT(DISTINCT observation_id))
FROM dwd_observation WHERE snapshot_id='${hivevar:snapshot}';

CREATE EXTERNAL TABLE IF NOT EXISTS dws_hourly (
  dataset_id STRING,dataset_version STRING,source_type STRING,city_id STRING,
  target_type STRING,target_id STRING,road_region_id STRING,bucket_start STRING,
  sample_count BIGINT,speed_sum DECIMAL(24,2),congestion_sum DECIMAL(24,2),
  observed_from STRING,observed_to STRING
) PARTITIONED BY(snapshot_id STRING,observed_date STRING) STORED AS ORC LOCATION '/s6/dws';
INSERT OVERWRITE TABLE dws_hourly PARTITION(snapshot_id='${hivevar:snapshot}',observed_date)
SELECT dataset_id,dataset_version,source_type,city_id,target_type,target_id,road_region_id,
  date_format(observed_at,"yyyy-MM-dd'T'HH':00:00.000Z'"),COUNT(*),
  CAST(SUM(avg_speed_kmh) AS DECIMAL(24,2)),CAST(SUM(congestion_index) AS DECIMAL(24,2)),
  date_format(MIN(observed_at),"yyyy-MM-dd'T'HH:mm:ss.SSS'Z'"),
  date_format(MAX(observed_at),"yyyy-MM-dd'T'HH:mm:ss.SSS'Z'"),observed_date
FROM dwd_observation WHERE snapshot_id='${hivevar:snapshot}'
GROUP BY dataset_id,dataset_version,source_type,city_id,target_type,target_id,road_region_id,
  date_format(observed_at,"yyyy-MM-dd'T'HH':00:00.000Z'"),observed_date;

CREATE EXTERNAL TABLE IF NOT EXISTS ads_metric (
  dataset_id STRING,dataset_version STRING,source_type STRING,city_id STRING,
  target_type STRING,target_id STRING,road_region_id STRING,grain STRING,bucket_start STRING,
  sample_count BIGINT,speed_sum DECIMAL(24,2),congestion_sum DECIMAL(24,2),
  avg_speed_kmh DECIMAL(6,2),congestion_index DECIMAL(4,2),observed_from STRING,observed_to STRING
) PARTITIONED BY(snapshot_id STRING) STORED AS ORC LOCATION '/s6/ads';
-- Reaggregate sums/counts. Hive ROUND on DECIMAL uses HALF_UP; only final means round.
INSERT OVERWRITE TABLE ads_metric PARTITION(snapshot_id='${hivevar:snapshot}')
SELECT dataset_id,dataset_version,source_type,city_id,target_type,target_id,road_region_id,grain,bucket_start,
  SUM(sample_count),CAST(SUM(speed_sum) AS DECIMAL(24,2)),CAST(SUM(congestion_sum) AS DECIMAL(24,2)),
  CAST(ROUND(SUM(speed_sum)/SUM(sample_count),2) AS DECIMAL(6,2)),
  CAST(ROUND(SUM(congestion_sum)/SUM(sample_count),2) AS DECIMAL(4,2)),MIN(observed_from),MAX(observed_to)
FROM (
  SELECT dataset_id,dataset_version,source_type,city_id,target_type,target_id,road_region_id,
    'HOUR' grain,bucket_start,sample_count,speed_sum,congestion_sum,observed_from,observed_to
    FROM dws_hourly WHERE snapshot_id='${hivevar:snapshot}'
  UNION ALL
  SELECT dataset_id,dataset_version,source_type,city_id,target_type,target_id,road_region_id,
    'DAY',concat(observed_date,'T00:00:00.000Z'),sample_count,speed_sum,congestion_sum,observed_from,observed_to
    FROM dws_hourly WHERE snapshot_id='${hivevar:snapshot}'
  UNION ALL
  SELECT dataset_id,dataset_version,source_type,city_id,target_type,target_id,road_region_id,
    'WINDOW','${hivevar:from}',sample_count,speed_sum,congestion_sum,observed_from,observed_to
    FROM dws_hourly WHERE snapshot_id='${hivevar:snapshot}'
) g GROUP BY dataset_id,dataset_version,source_type,city_id,target_type,target_id,road_region_id,grain,bucket_start;

SHOW PARTITIONS ods_observation;
SHOW PARTITIONS dwd_observation;
SHOW PARTITIONS dws_hourly;
SHOW PARTITIONS ads_metric;
SELECT 'ODS',COUNT(*),SUM(avg_speed_kmh),SUM(congestion_index) FROM ods_observation WHERE snapshot_id='${hivevar:snapshot}';
SELECT 'DWD',COUNT(*),SUM(avg_speed_kmh),SUM(congestion_index) FROM dwd_observation WHERE snapshot_id='${hivevar:snapshot}';
SELECT 'DWS',COUNT(*),SUM(sample_count),SUM(speed_sum),SUM(congestion_sum) FROM dws_hourly WHERE snapshot_id='${hivevar:snapshot}';
SELECT 'ADS',grain,COUNT(*),SUM(sample_count),SUM(speed_sum),SUM(congestion_sum) FROM ads_metric WHERE snapshot_id='${hivevar:snapshot}' GROUP BY grain;
-- Layer reconciliation is executed by Hive as well as the independent host oracle.
SELECT assert_true(d.n=s.n AND d.speed=s.speed AND d.congestion=s.congestion)
FROM (SELECT COUNT(*) n,SUM(avg_speed_kmh) speed,SUM(congestion_index) congestion
      FROM dwd_observation WHERE snapshot_id='${hivevar:snapshot}') d
CROSS JOIN (SELECT SUM(sample_count) n,SUM(speed_sum) speed,SUM(congestion_sum) congestion
      FROM dws_hourly WHERE snapshot_id='${hivevar:snapshot}') s;
SELECT assert_true(d.n=a.n AND d.speed=a.speed AND d.congestion=a.congestion)
FROM (SELECT COUNT(*) n,SUM(avg_speed_kmh) speed,SUM(congestion_index) congestion
      FROM dwd_observation WHERE snapshot_id='${hivevar:snapshot}') d
CROSS JOIN (SELECT grain,SUM(sample_count) n,SUM(speed_sum) speed,SUM(congestion_sum) congestion
      FROM ads_metric WHERE snapshot_id='${hivevar:snapshot}' GROUP BY grain) a;
INSERT OVERWRITE DIRECTORY '/s6/export/${hivevar:snapshot}'
ROW FORMAT DELIMITED FIELDS TERMINATED BY '\t'
SELECT dataset_id,dataset_version,source_type,city_id,target_type,target_id,road_region_id,grain,bucket_start,
  sample_count,speed_sum,congestion_sum,avg_speed_kmh,congestion_index,observed_from,observed_to
FROM ads_metric WHERE snapshot_id='${hivevar:snapshot}';
