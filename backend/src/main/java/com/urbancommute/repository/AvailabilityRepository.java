package com.urbancommute.repository;

import com.urbancommute.api.*;
import com.urbancommute.api.TrafficAvailability.*;
import com.urbancommute.web.InvalidRequestException;
import java.time.LocalDateTime;
import java.time.ZoneOffset;
import java.util.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.annotation.Isolation;
import org.springframework.transaction.annotation.Transactional;

@Repository
public class AvailabilityRepository {
    private final NamedParameterJdbcTemplate jdbc;
    private final String catalogFilter;
    public AvailabilityRepository(NamedParameterJdbcTemplate jdbc,
            @Value("${commute.cities.dataset-filter:}") String catalogFilter) {
        this.jdbc = jdbc; this.catalogFilter = catalogFilter;
    }
    private static String utc(LocalDateTime time) {
        return time == null ? null : time.toInstant(ZoneOffset.UTC).toString();
    }
    @Transactional(readOnly = true, isolation = Isolation.REPEATABLE_READ)
    public ApiResponse<TrafficAvailability> read(String cityId, String requestId) {
        var p = new HashMap<String, Object>();
        p.put("city", cityId); p.put("filter", catalogFilter);
        var cities = jdbc.query("SELECT dataset_id FROM city WHERE id=:city AND (:filter='' OR dataset_id=:filter)",
            p, (rs, i) -> rs.getString(1));
        if (cities.size() != 1) throw new InvalidRequestException();
        String defaultDataset = cities.getFirst();
        p.put("defaultDataset", defaultDataset);
        // A registry entry alone is not an association with this city. Only its default,
        // actual observations, or a published current prediction may establish one.
        var registrations = jdbc.query("""
            SELECT d.dataset_id,d.source_type FROM dataset_registry d
            WHERE d.dataset_id=:defaultDataset OR
              (d.source_type IN ('dev_seed','synthetic_test','historical_snapshot','authorized_live') AND
               (EXISTS (SELECT 1 FROM traffic_observation o WHERE o.city_id=:city AND o.dataset_id=d.dataset_id)
                OR EXISTS (SELECT 1 FROM prediction_current c JOIN prediction_job j USING(job_id)
                  WHERE c.city_id=:city AND c.dataset_id=d.dataset_id AND j.city_id=c.city_id
                    AND j.dataset_id=c.dataset_id AND j.status='PUBLISHED')))
            ORDER BY (d.dataset_id=:defaultDataset) DESC,d.dataset_id
            """, p, (rs, i) -> new String[]{rs.getString(1), rs.getString(2)});
        var datasets = new ArrayList<Dataset>();
        for (var registration : registrations) {
            p.put("dataset", registration[0]);
            var levels = new LinkedHashMap<String, Range>();
            for (String level : List.of("CITY", "REGION", "ROAD")) levels.put(level, new Range(0, null, null));
            jdbc.query("""
                SELECT target_type,COUNT(*) n,MIN(observed_at) first_at,MAX(observed_at) last_at
                FROM traffic_observation WHERE city_id=:city AND dataset_id=:dataset GROUP BY target_type
                """, p, rs -> {
                    String level = rs.getString("target_type");
                    if (levels.containsKey(level)) levels.put(level, new Range(rs.getLong("n"),
                        utc(rs.getObject("first_at", LocalDateTime.class)), utc(rs.getObject("last_at", LocalDateTime.class))));
                });
            var predictions = jdbc.query("""
                SELECT JSON_UNQUOTE(JSON_EXTRACT(j.document,'$.dataCutoff')) cutoff
                FROM prediction_current c JOIN prediction_job j USING(job_id)
                JOIN dataset_registry d ON d.dataset_id=c.dataset_id
                WHERE c.city_id=:city AND c.dataset_id=:dataset AND j.city_id=c.city_id
                  AND j.dataset_id=c.dataset_id AND j.status='PUBLISHED'
                  AND JSON_UNQUOTE(JSON_EXTRACT(j.document,'$.datasetVersion'))=d.dataset_version
                  AND JSON_UNQUOTE(JSON_EXTRACT(j.document,'$.sourceType'))=d.source_type
                """, p, (rs, i) -> rs.getString("cutoff"));
            datasets.add(new Dataset(registration[0], registration[1], Collections.unmodifiableMap(levels),
                !predictions.isEmpty(), predictions.isEmpty() ? null : predictions.getFirst()));
        }
        return new ApiResponse<>("OK", "Success", new TrafficAvailability(cityId, defaultDataset, List.copyOf(datasets)),
            new ResponseMeta(requestId, null, null, null));
    }
}
