package com.urbancommute.repository;

import com.urbancommute.api.*;
import com.urbancommute.api.Traffic.*;
import com.urbancommute.service.TrafficQuery;
import com.urbancommute.web.InvalidRequestException;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.time.*;
import java.time.temporal.ChronoUnit;
import java.util.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.annotation.Isolation;
import org.springframework.transaction.annotation.Transactional;

@Repository
public class TrafficRepository {
    private final NamedParameterJdbcTemplate jdbc;
    private final String catalogFilter;
    public TrafficRepository(NamedParameterJdbcTemplate jdbc, @Value("${commute.cities.dataset-filter:}") String catalogFilter) {
        this.jdbc = jdbc; this.catalogFilter = catalogFilter;
    }
    private static final String FILTER = """
        o.city_id=:city AND o.dataset_id=:dataset AND o.target_type=:level
        AND o.observed_at>=:from AND o.observed_at<:to
        """;
    private static final String STATS = "COUNT(o.id) AS n, AVG(o.avg_speed_kmh) AS speed, AVG(o.congestion_index) AS congestion, MAX(o.observed_at) AS latest";
    private static String timestamp(ResultSet rs, String field) throws SQLException {
        LocalDateTime value = rs.getObject(field, LocalDateTime.class);
        return value == null ? null : value.toInstant(ZoneOffset.UTC).toString();
    }
    private static Metrics metrics(ResultSet rs) throws SQLException {
        return new Metrics(rs.getLong("n"), rs.getBigDecimal("speed"), rs.getBigDecimal("congestion"), timestamp(rs, "latest"));
    }
    private static final Metrics EMPTY = new Metrics(0, null, null, null);

    /** All statements in a response share a MySQL repeatable-read snapshot. No source mixing. */
    @Transactional(readOnly = true, isolation = Isolation.REPEATABLE_READ)
    public ApiResponse<?> read(TrafficQuery q, String endpoint, String requestId) {
        var p = new HashMap<String, Object>();
        p.put("city", q.cityId()); p.put("dataset", q.datasetId()); p.put("catalogFilter", catalogFilter);
        var registration = jdbc.query("""
            SELECT d.dataset_id,d.source_type FROM city c JOIN dataset_registry d
            ON d.dataset_id=COALESCE(:dataset,c.dataset_id)
            WHERE c.id=:city AND (:catalogFilter='' OR c.dataset_id=:catalogFilter)
              AND d.source_type IN ('dev_seed','synthetic_test','historical_snapshot','authorized_live')
            """, p, (rs, i) -> new String[]{rs.getString(1), rs.getString(2)});
        if (registration.size() != 1) throw new InvalidRequestException();
        p.put("dataset", registration.getFirst()[0]);
        String level = switch (endpoint) { case "regions" -> "REGION"; case "roads" -> "ROAD"; default -> "CITY"; };
        p.put("level", level);
        p.put("from", LocalDateTime.ofInstant(q.from(), ZoneOffset.UTC));
        p.put("to", LocalDateTime.ofInstant(q.to(), ZoneOffset.UTC));
        p.put("region", q.regionId());
        // LOCATE treats %, _ and quotes as ordinary characters. All values are bound.
        p.put("search", q.search());
        String roadFilter = " AND (:region IS NULL OR r.region_id=:region) AND LOCATE(:search,r.name)>0 ";
        if (q.regionId() != null && jdbc.queryForObject("SELECT COUNT(*) FROM region WHERE id=:region AND city_id=:city", p, Long.class) != 1)
            throw new InvalidRequestException();
        String statsSql = "SELECT " + STATS + " FROM traffic_observation o "
                + (endpoint.equals("roads") ? "JOIN road_segment r ON r.id=o.road_segment_id " : "")
                + "WHERE " + FILTER + (endpoint.equals("roads") ? roadFilter : "");
        Metrics aggregate = jdbc.queryForObject(statsSql, p, (rs, i) -> metrics(rs));
        Object data;
        if (endpoint.equals("summary")) data = new Summary(q.window(level), aggregate);
        else if (endpoint.equals("series")) {
            // Only the enum selects SQL syntax; no request text is interpolated.
            String format = q.granularity().equals("hour") ? "%Y-%m-%d %H:00:00" : "%Y-%m-%d 00:00:00";
            var rows = jdbc.query("SELECT CAST(DATE_FORMAT(o.observed_at,'" + format + "') AS DATETIME) AS bucket, "
                    + STATS + " FROM traffic_observation o WHERE " + FILTER + " GROUP BY bucket ORDER BY bucket", p,
                    (rs, i) -> new Bucket(timestamp(rs, "bucket"), metrics(rs)));
            Map<String, Metrics> values = new HashMap<>();
            rows.forEach(row -> values.put(row.bucket(), row.metrics()));
            List<Bucket> filled = new ArrayList<>();
            ChronoUnit unit = q.granularity().equals("hour") ? ChronoUnit.HOURS : ChronoUnit.DAYS;
            for (Instant bucket = q.from().truncatedTo(unit); bucket.isBefore(q.to()); bucket = bucket.plus(1, unit))
                filled.add(new Bucket(bucket.toString(), values.getOrDefault(bucket.toString(), EMPTY)));
            data = new Series(q.window(level), q.granularity(), filled);
        } else if (endpoint.equals("regions")) {
            var rows = jdbc.query("SELECT r.id,r.name,r.center_lat,r.center_lon,r.coordinate_system," + STATS
                    + " FROM region r LEFT JOIN traffic_observation o ON o.region_id=r.id AND " + FILTER
                    + " WHERE r.city_id=:city GROUP BY r.id,r.name,r.center_lat,r.center_lon,r.coordinate_system "
                    + " ORDER BY congestion DESC,r.id", p, (rs, i) -> new Region(rs.getString("id"), rs.getString("name"),
                        rs.getObject("center_lat", Double.class), rs.getObject("center_lon", Double.class),
                        rs.getString("coordinate_system"), metrics(rs)));
            data = new Regions(q.window(level), rows);
        } else {
            long total = jdbc.queryForObject("SELECT COUNT(*) FROM road_segment r WHERE r.city_id=:city" + roadFilter, p, Long.class);
            p.put("limit", q.pageSize()); p.put("offset", (q.page() - 1) * q.pageSize());
            var rows = jdbc.query("SELECT r.id,r.name,r.region_id," + STATS
                    + " FROM road_segment r LEFT JOIN traffic_observation o ON o.road_segment_id=r.id AND " + FILTER
                    + " WHERE r.city_id=:city" + roadFilter + " GROUP BY r.id,r.name,r.region_id "
                    + "ORDER BY congestion DESC,r.id LIMIT :limit OFFSET :offset", p,
                    (rs, i) -> new Road(rs.getString("id"), rs.getString("name"), rs.getString("region_id"), metrics(rs)));
            data = new Roads(q.window(level), q.page(), q.pageSize(), total, rows);
        }
        return new ApiResponse<>("OK", "Success", data,
                new ResponseMeta(requestId, aggregate.dataAsOf(), registration.getFirst()[1], registration.getFirst()[0]));
    }
}
