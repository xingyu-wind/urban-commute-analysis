-- S4 only: run exclusively on a disposable, owned MySQL 8.4 test schema.
-- All identifiers and observations are invented. No real traffic or road positions are claimed.
-- Times are UTC DATETIME(3). Preserve Flyway V1/V2; this is NOT a migration.
-- Window for independent checks: [2026-10-15T00:00:00Z, 2026-10-17T00:00:00Z).
INSERT INTO dataset_registry
(dataset_id, source_name, source_type, license_status, dataset_version, description)
VALUES ('s4-synthetic-v1','S4 calculation-only fixture','synthetic_test','not_applicable','v1',
'Invented traffic values and non-geographic demonstration entities; NOT measured traffic');

INSERT INTO city (id,name,dataset_id) VALUES
('s4-demo-city','S4合成演示城市','s4-synthetic-v1');

-- WGS84 point is an invented renderer fixture and NOT the documented position of a real region.
-- West has no coordinate to verify it is not plotted as if geolocated.
INSERT INTO region (id,city_id,name,center_lat,center_lon,coordinate_system) VALUES
('s4-demo-east','s4-demo-city','演示东区',39.900000,116.400000,'WGS84'),
('s4-demo-west','s4-demo-city','演示西区',NULL,NULL,NULL);

INSERT INTO road_segment (id,city_id,region_id,name) VALUES
('s4-demo-road-a','s4-demo-city','s4-demo-east','演示路段A'),
('s4-demo-road-b','s4-demo-city','s4-demo-west','演示路段B');

-- city level: (30,6), (42,4), (36,5) => speed 36 km/h; index 5.00; N=3
INSERT INTO traffic_observation
(dataset_id,city_id,region_id,road_segment_id,target_type,target_id,observed_at,collected_at,avg_speed_kmh,congestion_index)
VALUES
('s4-synthetic-v1','s4-demo-city',NULL,NULL,'CITY','s4-demo-city','2026-10-15 08:00:00.000','2026-10-15 09:00:00.000',30.00,6.00),
('s4-synthetic-v1','s4-demo-city',NULL,NULL,'CITY','s4-demo-city','2026-10-15 09:00:00.000','2026-10-15 10:00:00.000',42.00,4.00),
('s4-synthetic-v1','s4-demo-city',NULL,NULL,'CITY','s4-demo-city','2026-10-16 08:00:00.000','2026-10-16 09:00:00.000',36.00,5.00),
-- region east: speed 25; index 6; N=2; region west: speed 50; index 2; N=1
('s4-synthetic-v1','s4-demo-city','s4-demo-east',NULL,'REGION','s4-demo-east','2026-10-15 08:00:00.000','2026-10-15 09:00:00.000',20.00,7.00),
('s4-synthetic-v1','s4-demo-city','s4-demo-east',NULL,'REGION','s4-demo-east','2026-10-16 08:00:00.000','2026-10-16 09:00:00.000',30.00,5.00),
('s4-synthetic-v1','s4-demo-city','s4-demo-west',NULL,'REGION','s4-demo-west','2026-10-15 08:00:00.000','2026-10-15 09:00:00.000',50.00,2.00),
-- road A: speed 15; index 8; N=2; road B: speed 40; index 3; N=1
('s4-synthetic-v1','s4-demo-city',NULL,'s4-demo-road-a','ROAD','s4-demo-road-a','2026-10-15 08:00:00.000','2026-10-15 09:00:00.000',10.00,9.00),
('s4-synthetic-v1','s4-demo-city',NULL,'s4-demo-road-a','ROAD','s4-demo-road-a','2026-10-16 08:00:00.000','2026-10-16 09:00:00.000',20.00,7.00),
('s4-synthetic-v1','s4-demo-city',NULL,'s4-demo-road-b','ROAD','s4-demo-road-b','2026-10-15 08:00:00.000','2026-10-15 09:00:00.000',40.00,3.00);
