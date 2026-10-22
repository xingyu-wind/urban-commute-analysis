package com.urbancommute;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.fasterxml.jackson.databind.*;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import org.junit.jupiter.api.*;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.annotation.Import;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.*;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.annotation.Transactional;

@SpringBootTest
@AutoConfigureMockMvc
@Import(IsolatedMySql.class)
@Transactional
class TrafficIntegrationTest {
    @DynamicPropertySource static void database(DynamicPropertyRegistry registry) { IsolatedMySql.properties(registry); }
    @Autowired MockMvc mvc;
    @Autowired JdbcTemplate jdbc;
    @Autowired ObjectMapper mapper;
    static final String QUERY = "?cityId=s4-demo-city&from=2026-10-15T00:00:00Z&to=2026-10-17T00:00:00Z";
    @BeforeEach void fixture() throws Exception {
        // The migration gate has already checked actual schema/account/server. Each fixture rolls back.
        String sql = Files.readString(Path.of("../database/fixtures/s4-synthetic.sql"));
        org.springframework.jdbc.datasource.init.ScriptUtils.executeSqlScript(
            org.springframework.jdbc.datasource.DataSourceUtils.getConnection(jdbc.getDataSource()),
            new org.springframework.core.io.ByteArrayResource(sql.getBytes(StandardCharsets.UTF_8)));
    }
    static org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder request(String uri) {
        return org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get(java.net.URI.create(uri));
    }
    JsonNode read(String endpoint, String query) throws Exception {
        var result = mvc.perform(request("/api/v1/traffic/" + endpoint + query)).andExpect(status().isOk()).andReturn();
        String content = result.getResponse().getContentAsString(StandardCharsets.UTF_8);
        Path dir = Path.of("target/s4-http"); Files.createDirectories(dir);
        Files.writeString(dir.resolve(endpoint + ".json"), content);
        return mapper.readTree(content);
    }
    void metric(JsonNode node, long n, double speed, double congestion) {
        assertThat(node.path("sampleCount").asLong()).isEqualTo(n);
        assertThat(node.path("avgSpeedKmh").asDouble()).isEqualTo(speed);
        assertThat(node.path("congestionIndex").asDouble()).isEqualTo(congestion);
    }
    @Test void availabilityUsesRealIndependentBoundsAndCityDatasetAssociation() throws Exception {
        var original = read("availability", "?cityId=s4-demo-city");
        assertThat(original.at("/data/defaultDatasetId").asText()).isEqualTo("s4-synthetic-v1");
        for (String level : new String[]{"CITY", "REGION", "ROAD"}) {
            var oracle = jdbc.queryForMap("SELECT COUNT(*) n,DATE_FORMAT(MAX(observed_at),'%Y-%m-%dT%H:%i:%sZ') last_at "
                + "FROM traffic_observation WHERE city_id='s4-demo-city' AND dataset_id='s4-synthetic-v1' AND target_type=?", level);
            var range = original.at("/data/datasets/0/levels/" + level);
            assertThat(range.path("sampleCount").asLong()).isEqualTo(((Number) oracle.get("n")).longValue());
            assertThat(range.path("lastObservedAt").asText()).isEqualTo(oracle.get("last_at"));
        }
        jdbc.update("INSERT INTO dataset_registry(dataset_id,source_name,source_type,license_status,dataset_version,description) "
            + "VALUES ('availability-unused','other city only','synthetic_test','not_applicable','v1','unrelated')");
        jdbc.update("INSERT INTO city(id,name,dataset_id) VALUES ('availability-other-city','other','availability-unused')");
        jdbc.update("INSERT INTO traffic_observation(dataset_id,city_id,target_type,target_id,observed_at,collected_at,avg_speed_kmh,congestion_index) "
            + "VALUES ('availability-unused','availability-other-city','CITY','availability-other-city','2026-10-21','2026-10-21',40,5)");
        assertThat(read("availability", "?cityId=s4-demo-city").at("/data/datasets").size()).isEqualTo(1);
        jdbc.update("INSERT INTO traffic_observation(dataset_id,city_id,target_type,target_id,observed_at,collected_at,avg_speed_kmh,congestion_index) "
            + "VALUES ('availability-unused','s4-demo-city','CITY','s4-demo-city','2026-10-20','2026-10-20',40,5)");
        var associated = read("availability", "?cityId=s4-demo-city").at("/data/datasets/1");
        assertThat(associated.path("datasetId").asText()).isEqualTo("availability-unused");
        assertThat(associated.at("/levels/CITY/lastObservedAt").asText()).isEqualTo("2026-10-20T00:00:00Z");
        assertThat(associated.at("/levels/REGION/sampleCount").asInt()).isZero();
        assertThat(associated.at("/levels/ROAD/lastObservedAt").isNull()).isTrue();
        assertThat(associated.path("predictionAvailable").asBoolean()).isFalse();
        mvc.perform(head("/api/v1/traffic/availability?cityId=s4-demo-city")).andExpect(status().isOk());
        mvc.perform(post("/api/v1/traffic/availability?cityId=s4-demo-city")).andExpect(status().isMethodNotAllowed());
        mvc.perform(get("/api/v1/traffic/availability?cityId=missing")).andExpect(status().isBadRequest());
    }
    @Test void directoryOnlySourceKeepsTruthfulRangesWithoutGrantingStatisticalReads() throws Exception {
        jdbc.update("UPDATE dataset_registry SET source_type='simulation' WHERE dataset_id='s4-synthetic-v1'");
        var availability = read("availability", "?cityId=s4-demo-city").at("/data/datasets/0");
        assertThat(availability.path("sourceType").asText()).isEqualTo("simulation");
        assertThat(availability.at("/levels/CITY/sampleCount").asInt()).isEqualTo(3);
        assertThat(availability.path("predictionAvailable").asBoolean()).isFalse();
        mvc.perform(request("/api/v1/traffic/summary" + QUERY)).andExpect(status().isBadRequest());
    }
    @Test void independentHandCalculationAndSqlAgreeWithoutCrossLevelCounting() throws Exception {
        // Independent oracle: SUM/count on a fixed CITY target, not the production query builder.
        var sql = jdbc.queryForMap("SELECT COUNT(*) n,SUM(avg_speed_kmh)/COUNT(*) speed,SUM(congestion_index)/COUNT(*) congestion "
                + "FROM traffic_observation WHERE dataset_id='s4-synthetic-v1' AND target_type='CITY' AND target_id='s4-demo-city' "
                + "AND observed_at >= '2026-10-15' AND observed_at < '2026-10-17'");
        assertThat(((Number) sql.get("n")).longValue()).isEqualTo(3);
        assertThat(((Number) sql.get("speed")).doubleValue()).isEqualTo(36);
        assertThat(((Number) sql.get("congestion")).doubleValue()).isEqualTo(5);
        var summary = read("summary", QUERY);
        metric(summary.at("/data/metrics"), 3, 36, 5);
        assertThat(summary.at("/meta/dataAsOf").asText()).isEqualTo("2026-10-16T08:00:00Z");
        assertThat(summary.at("/meta/sourceType").asText()).isEqualTo("synthetic_test");
        assertThat(summary.at("/meta/datasetId").asText()).isEqualTo("s4-synthetic-v1");
        var regions = read("regions", QUERY);
        metric(regions.at("/data/items/0/metrics"), 2, 25, 6);
        metric(regions.at("/data/items/1/metrics"), 1, 50, 2);
        assertThat(regions.at("/data/items/0/coordinateSystem").asText()).isEqualTo("WGS84");
        assertThat(regions.at("/data/items/1/latitude").isNull()).isTrue();
        var roads = read("roads", QUERY);
        metric(roads.at("/data/items/0/metrics"), 2, 15, 8);
        metric(roads.at("/data/items/1/metrics"), 1, 40, 3);
        assertThat(roads.at("/data/total").asInt()).isEqualTo(2);
    }
    @Test void databaseMutationChangesApiAndRestoresExactly() throws Exception {
        metric(read("summary", QUERY).at("/data/metrics"), 3, 36, 5);
        assertThat(jdbc.update("UPDATE traffic_observation SET avg_speed_kmh=60 WHERE dataset_id='s4-synthetic-v1' "
                + "AND target_type='CITY' AND observed_at='2026-10-15 09:00:00'")).isEqualTo(1);
        metric(read("summary", QUERY).at("/data/metrics"), 3, 42, 5);
        jdbc.update("UPDATE traffic_observation SET avg_speed_kmh=42 WHERE dataset_id='s4-synthetic-v1' "
                + "AND target_type='CITY' AND observed_at='2026-10-15 09:00:00'");
        metric(read("summary", QUERY).at("/data/metrics"), 3, 36, 5);
    }
    @Test void bucketsAreUtcSparseAndHalfOpenWithOffsetsNormalized() throws Exception {
        var series = read("series", QUERY);
        assertThat(series.at("/data/items").size()).isEqualTo(2);
        metric(series.at("/data/items/0/metrics"), 2, 36, 5);
        metric(series.at("/data/items/1/metrics"), 1, 36, 5);
        var hourly = read("series", QUERY + "&granularity=hour");
        assertThat(hourly.at("/data/items").size()).isEqualTo(48);
        assertThat(hourly.at("/data/items/0/metrics/avgSpeedKmh").isNull()).isTrue();
        metric(read("summary", "?cityId=s4-demo-city&from=2026-10-15T16:00:00%2B08:00&to=2026-10-15T17:00:00%2B08:00")
                .at("/data/metrics"), 1, 30, 6);
    }
    @Test void noObservationsMeansNullNotZeroAndCatalogEntitiesRemain() throws Exception {
        String empty = "?cityId=s4-demo-city&from=2026-10-18T00:00:00Z&to=2026-10-19T00:00:00Z";
        for (String endpoint : new String[]{"summary", "series", "regions", "roads"}) {
            var body = read(endpoint, empty);
            assertThat(body.at("/meta/dataAsOf").isNull()).isTrue();
            JsonNode metrics = endpoint.equals("summary") ? body.at("/data/metrics") : body.at("/data/items/0/metrics");
            assertThat(metrics.path("sampleCount").asLong()).isZero();
            assertThat(metrics.path("avgSpeedKmh").isNull()).isTrue();
            assertThat(metrics.path("congestionIndex").isNull()).isTrue();
        }
    }
    @Test void pagingRegionFilteringLiteralSearchAndEmptyPage() throws Exception {
        assertThat(read("roads", QUERY + "&pageSize=1").at("/data/items").size()).isEqualTo(1);
        assertThat(read("roads", QUERY + "&pageSize=1&page=2").at("/data/items/0/id").asText()).isEqualTo("s4-demo-road-b");
        assertThat(read("roads", QUERY + "&page=3").at("/data/items").size()).isZero();
        assertThat(read("roads", QUERY + "&regionId=s4-demo-west").at("/data/total").asInt()).isEqualTo(1);
        assertThat(read("roads", QUERY + "&search=%25%27%20OR%201=1").at("/data/total").asInt()).isZero();
    }
    @Test void datasetIsolationAndNonHistoricalSourcesRejected() throws Exception {
        jdbc.update("INSERT INTO dataset_registry(dataset_id,source_name,source_type,license_status,dataset_version,description) "
                + "VALUES ('s4-other','other','synthetic_test','not_applicable','v1','other')");
        jdbc.update("INSERT INTO traffic_observation(dataset_id,city_id,target_type,target_id,observed_at,collected_at,avg_speed_kmh,congestion_index) "
                + "VALUES ('s4-other','s4-demo-city','CITY','s4-demo-city','2026-10-15','2026-10-15',99,9)");
        metric(read("summary", QUERY).at("/data/metrics"), 3, 36, 5);
        metric(read("summary", QUERY + "&datasetId=s4-other").at("/data/metrics"), 1, 99, 9);
        for (String source : new String[]{"forecast", "mock", "simulation"}) {
            jdbc.update("UPDATE dataset_registry SET source_type=? WHERE dataset_id='s4-other'", source);
            mvc.perform(request("/api/v1/traffic/summary" + QUERY + "&datasetId=s4-other")).andExpect(status().isBadRequest());
        }
    }
    @ParameterizedTest
    @ValueSource(strings = {"&unexpected=x", "&cityId=other", "&page=0", "&pageSize=101", "&page=10001", "&page=abc",
        "&regionId=missing", "&datasetId=missing", "&search=%00"})
    void invalidRoadParameters(String extra) throws Exception {
        mvc.perform(request("/api/v1/traffic/roads" + QUERY + extra)).andExpect(status().isBadRequest());
    }
    @ParameterizedTest
    @ValueSource(strings = {"", "?cityId=missing&from=2026-10-15T00:00:00Z&to=2026-10-16T00:00:00Z",
        "?cityId=s4-demo-city&from=2026-02-30T00:00:00Z&to=2026-10-16T00:00:00Z",
        "?cityId=s4-demo-city&from=2026-10-15T00:00:00&to=2026-10-16T00:00:00Z",
        "?cityId=s4-demo-city&from=2026-10-17T00:00:00Z&to=2026-10-15T00:00:00Z",
        "?cityId=s4-demo-city&from=2020-10-15T00:00:00Z&to=2026-10-16T00:00:00Z"})
    void invalidWindows(String query) throws Exception {
        mvc.perform(request("/api/v1/traffic/summary" + query)).andExpect(status().isBadRequest());
    }
    @Test void methodMediaBodyAndHourlyBoundaries() throws Exception {
        mvc.perform(post("/api/v1/traffic/summary" + QUERY)).andExpect(status().isMethodNotAllowed());
        mvc.perform(request("/api/v1/traffic/summary" + QUERY).accept("text/html")).andExpect(status().isNotAcceptable());
        mvc.perform(request("/api/v1/traffic/summary" + QUERY).content("{}")).andExpect(status().isBadRequest());
        mvc.perform(request("/api/v1/traffic/series" + QUERY + "&granularity=week")).andExpect(status().isBadRequest());
        mvc.perform(request("/api/v1/traffic/series?cityId=s4-demo-city&from=2026-01-01T00:00:00Z&to=2026-03-01T00:00:00Z&granularity=hour"))
                .andExpect(status().isBadRequest());
    }
}
