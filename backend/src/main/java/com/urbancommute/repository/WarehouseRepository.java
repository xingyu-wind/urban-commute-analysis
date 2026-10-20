package com.urbancommute.repository;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.urbancommute.api.*;
import com.urbancommute.api.Warehouse.*;
import com.urbancommute.web.InvalidRequestException;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.time.LocalDateTime;
import java.time.ZoneOffset;
import java.util.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.annotation.Isolation;
import org.springframework.transaction.annotation.Transactional;

@Repository
public class WarehouseRepository {
    private final JdbcTemplate jdbc;
    private final ObjectMapper mapper;
    private final String catalogFilter;
    public WarehouseRepository(JdbcTemplate jdbc, ObjectMapper mapper,
            @Value("${commute.cities.dataset-filter:}") String catalogFilter) {
        this.jdbc = jdbc; this.mapper = mapper; this.catalogFilter = catalogFilter;
    }
    private static String time(ResultSet rs, String field) throws SQLException {
        return rs.getObject(field, LocalDateTime.class).toInstant(ZoneOffset.UTC).toString();
    }
    @Transactional(readOnly=true, isolation=Isolation.REPEATABLE_READ)
    public ApiResponse<Data> read(String city, String dataset, String grain, String requestId) {
        var registration = jdbc.query("""
            SELECT d.dataset_id,d.source_type FROM city c JOIN dataset_registry d
              ON d.dataset_id=COALESCE(?,c.dataset_id)
            WHERE c.id=? AND (?='' OR c.dataset_id=?)
              AND d.source_type IN ('dev_seed','synthetic_test','historical_snapshot','authorized_live')
            """, (rs, i) -> new String[]{rs.getString(1),rs.getString(2)}, dataset,city,catalogFilter,catalogFilter);
        if (registration.size()!=1) throw new InvalidRequestException();
        String datasetId = registration.getFirst()[0];
        var releases = jdbc.query("""
            SELECT r.*,m.dataset_version FROM warehouse_current c JOIN warehouse_release r USING(release_id)
            JOIN warehouse_metric m USING(release_id)
            WHERE c.singleton=1 AND r.status='PUBLISHED' AND m.city_id=? AND m.dataset_id=?
            LIMIT 1
            """, (rs, i) -> {
                var batches = new TreeSet<String>();
                var hashes = new TreeSet<String>();
                try {
                    for (var batch : mapper.readTree(rs.getString("manifest")).get("batches")) {
                        if (batch.get("dataset_id").asText().equals(datasetId)) {
                            batches.add(batch.get("batch_id").asText()); hashes.add(batch.get("source_sha256").asText());
                        }
                    }
                } catch (com.fasterxml.jackson.core.JsonProcessingException e) { throw new SQLException("Invalid release manifest",e); }
                return new Release(rs.getString("release_id"),rs.getString("dataset_version"),time(rs,"window_from"),
                    time(rs,"window_to"),time(rs,"captured_at"),time(rs,"published_at"),rs.getString("ads_sha256"),
                    List.copyOf(batches),List.copyOf(hashes));
            },city,datasetId);
        Release release = releases.isEmpty() ? null : releases.getFirst();
        List<Metric> items = release == null ? List.of() : jdbc.query("""
            SELECT * FROM warehouse_metric WHERE release_id=? AND city_id=? AND dataset_id=? AND grain=?
            ORDER BY target_type,target_id,bucket_start LIMIT 10001
            """, (rs,i) -> new Metric(rs.getString("target_type"),rs.getString("target_id"),rs.getString("road_region_id"),
                rs.getString("grain"),time(rs,"bucket_start"),rs.getLong("sample_count"),rs.getBigDecimal("speed_sum"),
                rs.getBigDecimal("congestion_sum"),rs.getBigDecimal("avg_speed_kmh"),rs.getBigDecimal("congestion_index"),
                time(rs,"observed_from"),time(rs,"observed_to")),release.id(),city,datasetId,grain);
        if (items.size()>10000) throw new InvalidRequestException();
        String latest = items.stream().map(Metric::observedTo).max(Comparator.comparing(java.time.Instant::parse)).orElse(null);
        return new ApiResponse<>("OK","Success",new Data("Hive",release,items),
            new ResponseMeta(requestId,latest,registration.getFirst()[1],datasetId));
    }
}
