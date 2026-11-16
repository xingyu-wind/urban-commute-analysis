-- Execute only in the dedicated ephemeral teacher-reproduction container.
-- Inputs are observations, never Python-computed aggregates.
CREATE DATABASE IF NOT EXISTS teacher_reproduction;
USE teacher_reproduction;
CREATE EXTERNAL TABLE IF NOT EXISTS ods (
 id string,dataset_id string,city_id string,target_type string,target_id string,
 local_date string,observed_at string,speed_kmh string,congestion_index string,
 volume string,length_km string,sample_count string)
ROW FORMAT DELIMITED FIELDS TERMINATED BY '\t' STORED AS TEXTFILE
LOCATION '/teacher-reproduction/ods';

CREATE TABLE IF NOT EXISTS dwd STORED AS ORC AS
SELECT id,dataset_id,city_id,target_type,target_id,local_date,observed_at,
 CAST(NULLIF(speed_kmh,'NULL') AS DOUBLE) speed_kmh,
 CAST(NULLIF(congestion_index,'NULL') AS DOUBLE) congestion_index,
 CAST(NULLIF(volume,'NULL') AS DOUBLE) volume,
 CAST(NULLIF(length_km,'NULL') AS DOUBLE) length_km,
 CAST(sample_count AS BIGINT) sample_count
FROM (SELECT *,ROW_NUMBER() OVER(PARTITION BY id ORDER BY dataset_id) rn FROM ods) t WHERE rn=1;

SELECT assert_true(COUNT(*)=0) FROM dwd
WHERE sample_count<=0 OR speed_kmh<0 OR congestion_index<0 OR volume<0;

CREATE TABLE IF NOT EXISTS dws STORED AS ORC AS
SELECT dataset_id,city_id,target_type,target_id,local_date,
 SUM(sample_count) sample_count,COUNT(*) observation_count,
 SUM(speed_kmh*sample_count) speed_sum,
 SUM(CASE WHEN speed_kmh IS NOT NULL THEN sample_count ELSE 0 END) speed_count,
 SUM(congestion_index*sample_count) congestion_sum,
 SUM(CASE WHEN congestion_index IS NOT NULL THEN sample_count ELSE 0 END) congestion_count,
 SUM(volume) volume_sum,COUNT(volume) volume_count
FROM dwd GROUP BY dataset_id,city_id,target_type,target_id,local_date;

CREATE TABLE IF NOT EXISTS ads_daily STORED AS ORC AS
SELECT dataset_id,city_id,local_date,SUM(sample_count) sample_count,SUM(observation_count) observation_count,
 SUM(speed_sum)/SUM(speed_count) speed_kmh,
 SUM(congestion_sum)/SUM(congestion_count) congestion_index,
 SUM(volume_sum)/SUM(volume_count) volume
FROM dws GROUP BY dataset_id,city_id,local_date;

CREATE TABLE IF NOT EXISTS ads_weekday STORED AS ORC AS
SELECT dataset_id,city_id,CASE WHEN dayofweek(local_date) IN (1,7) THEN 'WEEKEND' ELSE 'WEEKDAY' END day_type,
 SUM(sample_count) sample_count,SUM(speed_sum)/SUM(speed_count) speed_kmh,
 SUM(congestion_sum)/SUM(congestion_count) congestion_index,SUM(volume_sum)/SUM(volume_count) volume
FROM dws GROUP BY dataset_id,city_id,CASE WHEN dayofweek(local_date) IN (1,7) THEN 'WEEKEND' ELSE 'WEEKDAY' END;

CREATE TABLE IF NOT EXISTS ads_hour STORED AS ORC AS
SELECT dataset_id,city_id,SUBSTR(observed_at,12,2) local_hour,
 SUM(sample_count) sample_count,SUM(speed_kmh*sample_count)/SUM(CASE WHEN speed_kmh IS NOT NULL THEN sample_count ELSE 0 END) speed_kmh,
 AVG(volume) volume
FROM dwd WHERE observed_at IS NOT NULL AND observed_at<>'NULL'
GROUP BY dataset_id,city_id,SUBSTR(observed_at,12,2);

-- Each timestamp has its own denominator; missing estimates never add road length.
CREATE TABLE IF NOT EXISTS ads_road_length STORED AS ORC AS
SELECT dataset_id,city_id,observed_at,COUNT(*) observed_roads,SUM(length_km) observed_length_km,
 SUM(CASE WHEN speed_kmh<32.18688 THEN length_km ELSE 0 END)/SUM(length_km) congested_length_share,
 SUM(CASE WHEN speed_kmh<16.09344 THEN 1 ELSE 0 END) severe_roads,
 SUM(CASE WHEN speed_kmh>0 THEN length_km/speed_kmh*3600 ELSE NULL END) derived_travel_seconds,
 SUM(CASE WHEN speed_kmh=0 THEN 1 ELSE 0 END) stopped_roads
FROM dwd WHERE dataset_id IN ('CHICAGO_ROADS','CHICAGO_ROADS_7D','CHICAGO_ROADS_V2','CHICAGO_ROADS_7D_V2')
GROUP BY dataset_id,city_id,observed_at;

INSERT OVERWRITE DIRECTORY '/teacher-reproduction/export/daily'
ROW FORMAT DELIMITED FIELDS TERMINATED BY '\t'
SELECT * FROM ads_daily;
INSERT OVERWRITE DIRECTORY '/teacher-reproduction/export/weekday'
ROW FORMAT DELIMITED FIELDS TERMINATED BY '\t'
SELECT * FROM ads_weekday;
INSERT OVERWRITE DIRECTORY '/teacher-reproduction/export/hour'
ROW FORMAT DELIMITED FIELDS TERMINATED BY '\t'
SELECT * FROM ads_hour;
INSERT OVERWRITE DIRECTORY '/teacher-reproduction/export/road_length'
ROW FORMAT DELIMITED FIELDS TERMINATED BY '\t'
SELECT * FROM ads_road_length;

SELECT 'ODS',COUNT(*) FROM ods UNION ALL SELECT 'DWD',COUNT(*) FROM dwd
UNION ALL SELECT 'DWS',COUNT(*) FROM dws UNION ALL SELECT 'ADS_DAILY',COUNT(*) FROM ads_daily;
