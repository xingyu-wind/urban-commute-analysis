-- Independent oracle: fixed literals and SUM / COUNT, no production query fragments.
-- Run after s4-synthetic.sql, before the mutation test, in the same isolated schema.
SELECT target_type,target_id,COUNT(*) AS sample_count,
       SUM(avg_speed_kmh)/COUNT(*) AS speed_kmh,
       SUM(congestion_index)/COUNT(*) AS congestion_index,
       MAX(observed_at) AS data_as_of
FROM traffic_observation
WHERE dataset_id='s4-synthetic-v1'
  AND observed_at >= '2026-10-15 00:00:00' AND observed_at < '2026-10-17 00:00:00'
GROUP BY target_type,target_id ORDER BY target_type,target_id;

SELECT DATE(observed_at) AS utc_day,COUNT(*) AS sample_count,
       SUM(avg_speed_kmh)/COUNT(*) AS speed_kmh,
       SUM(congestion_index)/COUNT(*) AS congestion_index
FROM traffic_observation
WHERE dataset_id='s4-synthetic-v1' AND target_type='CITY' AND target_id='s4-demo-city'
  AND observed_at >= '2026-10-15' AND observed_at < '2026-10-17'
GROUP BY DATE(observed_at) ORDER BY utc_day;
