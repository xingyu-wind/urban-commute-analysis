package com.urbancommute.repository;

import com.fasterxml.jackson.databind.*;
import com.urbancommute.api.*;
import com.urbancommute.api.Prediction.*;
import com.urbancommute.web.InvalidRequestException;
import java.sql.SQLException;
import java.util.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.annotation.Isolation;
import org.springframework.transaction.annotation.Transactional;

@Repository
public class PredictionRepository {
    private final JdbcTemplate jdbc;
    private final ObjectMapper mapper;
    private final String catalogFilter;
    public PredictionRepository(JdbcTemplate jdbc, ObjectMapper mapper,
            @Value("${commute.cities.dataset-filter:}") String catalogFilter) {
        this.jdbc=jdbc; this.mapper=mapper; this.catalogFilter=catalogFilter;
    }
    private JsonNode parse(String value) throws SQLException {
        try { return mapper.readTree(value); }
        catch (com.fasterxml.jackson.core.JsonProcessingException e) { throw new SQLException("Invalid prediction document",e); }
    }
    private List<String> strings(JsonNode array) {
        var values = new ArrayList<String>(); array.forEach(v -> values.add(v.asText())); return List.copyOf(values);
    }
    @Transactional(readOnly=true, isolation=Isolation.REPEATABLE_READ)
    public ApiResponse<Data> read(String city, String dataset, String requestId) {
        var registration = jdbc.query("""
            SELECT d.dataset_id,d.source_type,d.dataset_version FROM city c JOIN dataset_registry d
              ON d.dataset_id=COALESCE(?,c.dataset_id)
            WHERE c.id=? AND (?='' OR c.dataset_id=?)
              AND d.source_type IN ('synthetic_test','historical_snapshot','authorized_live','dev_seed')
            """, (rs,i) -> new String[]{rs.getString(1),rs.getString(2),rs.getString(3)},dataset,city,catalogFilter,catalogFilter);
        if (registration.size()!=1) throw new InvalidRequestException();
        String datasetId=registration.getFirst()[0];
        var jobs = jdbc.query("""
            SELECT j.job_id,j.document FROM prediction_current c JOIN prediction_job j USING(job_id)
            WHERE c.city_id=? AND c.dataset_id=? AND j.city_id=c.city_id AND j.dataset_id=c.dataset_id AND j.status='PUBLISHED'
            """,(rs,i) -> Map.entry(rs.getString(1),parse(rs.getString(2))),city,datasetId);
        if (jobs.isEmpty()) return new ApiResponse<>("OK","Success",new Data(null,List.of(),List.of(),List.of()),
            new ResponseMeta(requestId,null,registration.getFirst()[1],datasetId));
        var job=jobs.getFirst(); var d=job.getValue();
        // A changed registry must not mislabel a previously published model.
        if (!d.path("datasetVersion").asText().equals(registration.getFirst()[2])
                || !d.path("sourceType").asText().equals(registration.getFirst()[1])) throw new InvalidRequestException();
        var release = new Release(job.getKey(),d.path("modelVersion").asText(),d.path("modelName").asText(),
            d.path("trainedAt").asText(),d.path("generatedAt").asText(),d.path("dataCutoff").asText(),
            d.path("datasetVersion").asText(),d.path("inputSha256").asText(),strings(d.path("batchIds")),strings(d.path("sourceHashes")),
            d.path("limitation").asText(),new Metrics(d.path("metrics").path("mae").asDouble(),d.path("metrics").path("rmse").asDouble()));
        var history = new ArrayList<Actual>();
        d.path("history").forEach(p -> history.add(new Actual(p.path("date").asText(),p.path("value").asDouble(),p.path("sampleCount").asInt())));
        var predictions = jdbc.query("SELECT forecast_date,value FROM prediction_result WHERE job_id=? ORDER BY step",
            (rs,i) -> new Forecast(rs.getString(1),rs.getBigDecimal(2)),job.getKey());
        var evaluations = jdbc.query("SELECT split,model_name,evaluation FROM prediction_evaluation WHERE job_id=? ORDER BY split,model_name",(rs,i) -> {
            var e=parse(rs.getString(3)); var horizons=new ArrayList<Horizon>();
            e.path("byHorizon").forEach(h -> horizons.add(new Horizon(h.path("step").asInt(),h.path("mae").asDouble(),h.path("rmse").asDouble())));
            return new Evaluation(rs.getString(1),rs.getString(2),e.path("mae").asDouble(),e.path("rmse").asDouble(),List.copyOf(horizons));
        },job.getKey());
        return new ApiResponse<>("OK","Success",new Data(release,List.copyOf(history),predictions,evaluations),
            new ResponseMeta(requestId,d.path("dataAsOf").asText(),registration.getFirst()[1],datasetId));
    }
}
