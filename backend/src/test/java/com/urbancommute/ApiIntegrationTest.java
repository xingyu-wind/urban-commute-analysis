package com.urbancommute;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.doReturn;
import static org.mockito.Mockito.doThrow;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.urbancommute.api.ApiResponse;
import com.urbancommute.api.City;
import com.urbancommute.api.ResponseMeta;
import com.urbancommute.service.CityCatalog;
import com.urbancommute.service.CityService;
import com.urbancommute.web.ServiceUnavailableException;
import jakarta.validation.Validator;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.sql.SQLException;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.junit.jupiter.params.provider.CsvSource;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.transaction.PlatformTransactionManager;
import org.flywaydb.core.Flyway;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestInstance;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.bean.override.mockito.MockitoSpyBean;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.context.annotation.Import;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@AutoConfigureMockMvc
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
@Import(IsolatedMySql.class)
class ApiIntegrationTest {
    @DynamicPropertySource static void isolatedDatabase(DynamicPropertyRegistry registry) {
        IsolatedMySql.properties(registry);
    }
    @Autowired MockMvc mvc;
    @Autowired ObjectMapper mapper;
    @Autowired TestRestTemplate http;
    @Autowired Validator validator;
    @Autowired JdbcTemplate jdbc;
    @Autowired Flyway flyway;
    @Autowired PlatformTransactionManager transactionManager;
    @Value("${spring.datasource.url}") String datasourceUrl;
    @LocalServerPort int port;
    @MockitoSpyBean CityService cityService;

    @BeforeAll void loadSyntheticFixtureOnlyIntoDisposableCiDatabase() {
        // Fail closed: CI and local testing must use a dedicated throwaway schema.
        assertThat(datasourceUrl).contains("/" + IsolatedMySql.required("TEST_DB_SCHEMA") + "?");
        assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM city", Integer.class)).isZero();
        assertThat(jdbc.queryForList("SELECT version FROM flyway_schema_history WHERE success=1 ORDER BY installed_rank", String.class))
                .containsExactly("1", "2", "3");
        jdbc.update("""
                INSERT INTO dataset_registry(dataset_id,source_name,source_type,license_status,dataset_version,description)
                VALUES ('s3-synthetic-cities-v1','S3 generated catalog fixture','synthetic_test',
                        'not_applicable','v1','Invented test labels; no actual traffic data')""");
        jdbc.update("INSERT INTO city(id,name,dataset_id) VALUES ('sample-beijing','北京','s3-synthetic-cities-v1')");
        jdbc.update("INSERT INTO city(id,name,dataset_id) VALUES ('sample-shanghai','上海','s3-synthetic-cities-v1')");
        jdbc.update("""
                INSERT INTO region(id,city_id,name,center_lat,center_lon,coordinate_system)
                VALUES ('sample-region','sample-beijing','合成一区',39.900000,116.400000,'WGS84')""");
        jdbc.update("""
                INSERT INTO road_segment(id,city_id,region_id,name)
                VALUES ('sample-road','sample-beijing','sample-region','合成测试道路')""");
        jdbc.update("""
                INSERT INTO traffic_observation(dataset_id,city_id,road_segment_id,target_type,target_id,
                                                observed_at,collected_at,avg_speed_kmh,congestion_index)
                VALUES ('s3-synthetic-cities-v1','sample-beijing','sample-road','ROAD','sample-road',
                        '2026-01-02 00:00:00.000','2026-01-03 00:00:00.000',32.50,3.25)""");
    }

    private JsonNode json(MvcResult result) throws Exception {
        return mapper.readTree(result.getResponse().getContentAsString(StandardCharsets.UTF_8));
    }

    private void assertError(JsonNode body, String code) {
        assertThat(body.size()).isEqualTo(4);
        assertThat(body.path("code").asText()).isEqualTo(code);
        assertThat(body.path("message").asText()).isNotBlank();
        assertThat(body.has("data")).isTrue();
        assertThat(body.get("data").isNull()).isTrue();
        JsonNode meta = body.get("meta");
        assertThat(meta.size()).isEqualTo(4);
        UUID.fromString(meta.path("requestId").asText());
        for (String key : List.of("dataAsOf", "sourceType", "datasetId")) {
            assertThat(meta.has(key)).isTrue();
            assertThat(meta.get(key).isNull()).isTrue();
        }
    }

    private JsonNode live(String name, String path, int expectedStatus) throws Exception {
        HttpHeaders headers = new HttpHeaders();
        headers.setAccept(List.of(MediaType.APPLICATION_JSON));
        var response = http.exchange("http://127.0.0.1:" + port + path,
                HttpMethod.GET, new HttpEntity<>(headers), String.class);
        assertThat(response.getStatusCode().value()).isEqualTo(expectedStatus);
        assertThat(response.getHeaders().getContentType().isCompatibleWith(MediaType.APPLICATION_JSON)).isTrue();
        JsonNode body = mapper.readTree(response.getBody());
        String requestId = response.getHeaders().getFirst("X-Request-Id");
        UUID.fromString(requestId);
        if (body.has("meta")) assertThat(body.path("meta").path("requestId").asText()).isEqualTo(requestId);
        Path directory = Path.of("target", "http-test-evidence");
        Files.createDirectories(directory);
        Files.writeString(directory.resolve(name + ".json"), response.getBody(), StandardCharsets.UTF_8);
        Map<String, Object> evidence = new LinkedHashMap<>();
        evidence.put("method", "GET"); evidence.put("url", "http://127.0.0.1:" + port + path);
        evidence.put("contractPath", path); evidence.put("status", expectedStatus);
        evidence.put("contentType", response.getHeaders().getContentType().toString());
        evidence.put("requestId", requestId);
        evidence.put("capturedAt", Instant.now().toString());
        evidence.put("testServiceSubstitution", List.of("cities-empty", "error-500", "error-503").contains(name));
        mapper.writerWithDefaultPrettyPrinter().writeValue(directory.resolve(name + ".http.json").toFile(), evidence);
        return body;
    }

    @Test void healthHasDynamicZonedTimestampAndFreshRequestId() throws Exception {
        Instant before = Instant.now().minusSeconds(1);
        MvcResult first = mvc.perform(get("/health").header("X-Request-Id", "untrusted-client-value"))
                .andExpect(status().isOk()).andReturn();
        JsonNode body = json(first);
        assertThat(body.size()).isEqualTo(2);
        assertThat(body.path("status").asText()).isEqualTo("UP");
        assertThat(Instant.parse(body.path("timestamp").asText())).isBetween(before, Instant.now().plusSeconds(1));
        String id = first.getResponse().getHeader("X-Request-Id");
        UUID.fromString(id);
        String next = mvc.perform(get("/health")).andReturn().getResponse().getHeader("X-Request-Id");
        assertThat(next).isNotEqualTo(id);
    }

    @Test void citiesAreReadFromActualMySqlWithProvenance() throws Exception {
        JsonNode body = json(mvc.perform(get("/api/v1/cities")).andExpect(status().isOk()).andReturn());
        assertThat(body.size()).isEqualTo(4);
        assertThat(body.path("code").asText()).isEqualTo("OK");
        assertThat(body.path("data").size()).isEqualTo(2);
        assertThat(body.at("/data/0/id").asText()).isEqualTo("sample-beijing");
        assertThat(body.at("/meta/sourceType").asText()).isEqualTo("synthetic_test");
        assertThat(body.at("/meta/datasetId").asText()).isEqualTo("s3-synthetic-cities-v1");
        assertThat(body.at("/meta/dataAsOf").isNull()).isTrue();
    }

    @Test void repeatMigrationIsIdempotentAndDataRetained() {
        assertThat(flyway.validateWithResult().validationSuccessful).isTrue();
        assertThat(flyway.migrate().migrationsExecuted).isZero();
        assertThat(jdbc.queryForList("SELECT version FROM flyway_schema_history WHERE success=1 ORDER BY installed_rank", String.class))
                .containsExactly("1", "2", "3");
        assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM city", Integer.class)).isEqualTo(2);
    }

    @Test void isolationGuardChecksActualDatabaseAccountAndServerWithoutWrites() throws Exception {
        try (var connection = jdbc.getDataSource().getConnection()) {
            String schema = IsolatedMySql.required("TEST_DB_SCHEMA");
            String user = IsolatedMySql.required("TEST_DB_USER");
            String server = IsolatedMySql.required("TEST_DB_SERVER_UUID");
            IsolatedMySql.verify(connection, schema, user, server);
            assertThatThrownBy(() -> IsolatedMySql.verify(connection, "urban_commute", user, server))
                    .isInstanceOf(IllegalStateException.class).hasMessageContaining("non-isolated");
            assertThatThrownBy(() -> IsolatedMySql.verify(connection, schema, "s3t_00000000000000000000", server))
                    .isInstanceOf(IllegalStateException.class).hasMessageContaining("identity mismatch");
        }
    }

    @Test void mysqlEnforcesForeignKeysCheckRangesAndDeduplication() {
        assertThat(jdbc.queryForObject("SELECT AVG(avg_speed_kmh) FROM traffic_observation", java.math.BigDecimal.class))
                .isEqualByComparingTo("32.50");
        assertThatThrownBy(() -> jdbc.update("INSERT INTO region(id,city_id,name) VALUES ('bad-region','missing-city','x')"))
                .isInstanceOf(DataIntegrityViolationException.class);
        assertThatThrownBy(() -> jdbc.update("""
                INSERT INTO traffic_observation(dataset_id,city_id,road_segment_id,target_type,target_id,observed_at,
                    collected_at,avg_speed_kmh,congestion_index)
                VALUES ('s3-synthetic-cities-v1','sample-beijing','sample-road','ROAD','sample-road',
                    '2026-01-04','2026-01-04',-1,2)"""))
                // MySQL CHECK violation 3819/HY000 is not always translated by Spring's SQLExceptionTranslator.
                .isInstanceOf(org.springframework.jdbc.UncategorizedSQLException.class);
        assertThatThrownBy(() -> jdbc.update("""
                INSERT INTO traffic_observation(dataset_id,city_id,road_segment_id,target_type,target_id,observed_at,
                    collected_at,avg_speed_kmh,congestion_index)
                VALUES ('s3-synthetic-cities-v1','sample-beijing','sample-road','ROAD','sample-road',
                    '2026-01-02','2026-01-03',32.50,3.25)"""))
                .isInstanceOf(DataIntegrityViolationException.class);
        assertThatThrownBy(() -> jdbc.update("""
                INSERT INTO road_segment(id,city_id,region_id,name)
                VALUES ('cross-city','sample-shanghai','sample-region','invalid cross-city road')"""))
                .isInstanceOf(DataIntegrityViolationException.class);
    }

    @Test void emptyServiceResultRemainsHttp200Array() throws Exception {
        doReturn(new CityCatalog(List.of(), "database_catalog", null)).when(cityService).listCities();
        JsonNode body = live("cities-empty", "/api/v1/cities", 200);
        assertThat(body.path("data").isEmpty()).isTrue();
        assertThat(body.at("/meta/sourceType").asText()).isEqualTo("database_catalog");
    }

    @Test void unknownRouteUsesUniform404() throws Exception {
        assertError(json(mvc.perform(get("/not-a-route")).andExpect(status().isNotFound()).andReturn()), "NOT_FOUND");
    }

    @Test void wrongMethodPreservesAllowHeader() throws Exception {
        assertError(json(mvc.perform(post("/api/v1/cities"))
                .andExpect(status().isMethodNotAllowed()).andExpect(header().string("Allow", org.hamcrest.Matchers.containsString("GET")))
                .andReturn()), "METHOD_NOT_ALLOWED");
    }

    @Test void undeclaredQueryAndGetBodyAreBadRequests() throws Exception {
        assertError(json(mvc.perform(get("/api/v1/cities").param("limit", "invalid"))
                .andExpect(status().isBadRequest()).andReturn()), "BAD_REQUEST");
        assertError(json(mvc.perform(get("/health").contentType(MediaType.APPLICATION_JSON).content("{}"))
                .andExpect(status().isBadRequest()).andReturn()), "BAD_REQUEST");
    }

    @Test void unacceptableRepresentationStays406WithJsonExplanation() throws Exception {
        for (String path : List.of("/health", "/api/v1/cities")) {
            MvcResult result = mvc.perform(get(path).accept(MediaType.APPLICATION_XML))
                    .andExpect(status().isNotAcceptable()).andReturn();
            assertThat(result.getResponse().getContentType()).startsWith("application/json");
            assertError(json(result), "NOT_ACCEPTABLE");
        }
    }

    @Test void unexpectedServiceExceptionIsSafe500OverRealHttp() throws Exception {
        doThrow(new IllegalStateException("private-path-and-secret-example")).when(cityService).listCities();
        JsonNode body = live("error-500", "/api/v1/cities", 500);
        assertError(body, "INTERNAL_ERROR");
        assertThat(body.toString()).doesNotContain("private-path", "stackTrace", "exception");
    }

    @Test void unavailableServiceIs503OverRealHttp() throws Exception {
        doThrow(new ServiceUnavailableException()).when(cityService).listCities();
        assertError(live("error-503", "/api/v1/cities", 503), "SERVICE_UNAVAILABLE");
    }

    @Test void actualEmbeddedServerServesBothEndpoints() throws Exception {
        assertThat(live("health", "/health", 200).path("status").asText()).isEqualTo("UP");
        assertThat(live("cities", "/api/v1/cities", 200).path("data").size()).isEqualTo(2);
    }

    @Test void requiredNullsSurviveNonNullMapperConfiguration() {
        ObjectMapper strict = mapper.copy().setSerializationInclusion(JsonInclude.Include.NON_NULL);
        JsonNode body = strict.valueToTree(new ApiResponse<>("INTERNAL_ERROR", "Internal service error", null,
                ResponseMeta.error(UUID.randomUUID().toString())));
        assertError(body, "INTERNAL_ERROR");
    }

    @Test void cityValidationRejectsInvalidIdsAndBlankNames() {
        assertThat(validator.validate(new City("sample-beijing", "北京"))).isEmpty();
        assertThat(validator.validate(new City("INVALID ID", " "))).hasSize(2);
    }

    private void rejected(String sql, String constraint, int code, Object... args) {
        try {
            jdbc.update(sql, args);
            throw new AssertionError("MySQL accepted invalid data: " + constraint);
        } catch (org.springframework.dao.DataAccessException error) {
            Throwable cause = error.getMostSpecificCause();
            assertThat(cause).isInstanceOf(SQLException.class);
            assertThat(((SQLException) cause).getErrorCode()).isEqualTo(code);
            assertThat(cause.getMessage()).contains(constraint);
        }
    }

    @ParameterizedTest @ValueSource(strings = {"Upper-City", "bad_id", "1city", "bad--city", "bad city", ""})
    void databaseRejectsInvalidCityIds(String id) {
        rejected("INSERT INTO city(id,name,dataset_id) VALUES (?,'x','s3-synthetic-cities-v1')",
                "ck_city_id", 3819, id);
    }

    @ParameterizedTest @ValueSource(strings = {"", " ", "\t\n", "　"})
    void databaseRejectsBlankCityNames(String name) {
        rejected("INSERT INTO city(id,name,dataset_id) VALUES ('blank-city',?,'s3-synthetic-cities-v1')",
                "ck_city_name", 3819, name);
    }

    @ParameterizedTest @ValueSource(ints = {1,2,3,4,5,6})
    void allPartialCoordinateNullCombinationsAreRejected(int mask) {
        rejected("INSERT INTO region(id,city_id,name,center_lat,center_lon,coordinate_system) VALUES ('partial','sample-beijing','partial',?,?,?)",
                "ck_region_coordinates", 3819, (mask & 1) != 0 ? 39.9 : null,
                (mask & 2) != 0 ? 116.4 : null, (mask & 4) != 0 ? "WGS84" : null);
    }

    @ParameterizedTest @CsvSource({"91,0,WGS84", "0,181,WGS84", "-91,0,WGS84", "0,-181,WGS84", "0,0,wgs84", "0,0,GCJ02"})
    void coordinateRangeAndSystemAreEnforced(double lat, double lon, String system) {
        rejected("INSERT INTO region(id,city_id,name,center_lat,center_lon,coordinate_system) VALUES ('bad-coord','sample-beijing','bad',?,?,?)",
                "ck_region_coordinates", 3819, lat, lon, system);
    }

    @ParameterizedTest @CsvSource({"authorized_live,unverified", "historical_snapshot,unverified", "synthetic_test,authorized", "forecast,authorized"})
    void provenanceCannotClaimUnverifiedObservationsOrAuthorizedSynthetic(String source, String license) {
        rejected("INSERT INTO dataset_registry(dataset_id,source_name,source_type,license_status,dataset_version,description) VALUES ('bad-source','x',?,?,'v1','x')",
                "ck_dataset_provenance", 3819, source, license);
    }

    @ParameterizedTest @CsvSource({"SYNTHETIC_TEST,not_applicable,ck_dataset_source_case", "synthetic_test,NOT_APPLICABLE,ck_dataset_license_case"})
    void provenanceEnumsAreCaseSensitive(String source, String license, String constraint) {
        rejected("INSERT INTO dataset_registry(dataset_id,source_name,source_type,license_status,dataset_version,description) VALUES ('wrong-case','x',?,?,'v1','x')",
                constraint, 3819, source, license);
    }

    @ParameterizedTest @ValueSource(strings = {"dev_seed","synthetic_test","historical_snapshot","authorized_live","simulation","mock","forecast"})
    void allCanonicalSourceTypesHaveExplicitMetadata(String source) {
        var transaction = new TransactionTemplate(transactionManager);
        transaction.executeWithoutResult(status -> {
            jdbc.update("INSERT INTO dataset_registry(dataset_id,source_name,source_type,license_status,dataset_version,description) VALUES ('single-source','x',?,?,'v1','x')",
                    source, List.of("historical_snapshot", "authorized_live").contains(source) ? "authorized" : "not_applicable");
            jdbc.update("INSERT INTO city(id,name,dataset_id) VALUES ('source-city','source city','single-source')");
            var catalog = new CityService(new com.urbancommute.repository.CityRepository(jdbc, "single-source")).listCities();
            assertThat(catalog.sourceType()).isEqualTo(source);
            assertThat(catalog.datasetId()).isEqualTo("single-source");
            status.setRollbackOnly();
        });
    }

    @Test void sameRoadNameAcrossSegmentsAndCoordinateNullsAreValid() {
        new TransactionTemplate(transactionManager).executeWithoutResult(status -> {
            jdbc.update("INSERT INTO road_segment(id,city_id,name) VALUES ('another-segment','sample-beijing','合成测试道路')");
            jdbc.update("INSERT INTO region(id,city_id,name) VALUES ('no-coordinates','sample-beijing','no-coordinates')");
            status.setRollbackOnly();
        });
    }

    @Test void modifiedHistoricalMigrationIsRejectedWithoutRepair(@org.junit.jupiter.api.io.TempDir Path directory) throws Exception {
        for (String file : List.of("V1__commute_core.sql", "V2__strengthen_core_constraints.sql")) {
            String sql;
            try (var input = getClass().getResourceAsStream("/db/migration/" + file)) {
                sql = new String(input.readAllBytes(), StandardCharsets.UTF_8);
            }
            if (file.startsWith("V1")) sql = sql.replace("CREATE TABLE city (", "CREATE TABLE changed_city (");
            Files.writeString(directory.resolve(file), sql);
        }
        var changed = Flyway.configure().dataSource(jdbc.getDataSource())
                .locations("filesystem:" + directory).load().validateWithResult();
        assertThat(changed.validationSuccessful).isFalse();
        assertThat(changed.invalidMigrations).anySatisfy(migration ->
                assertThat(migration.errorDetails.errorCode.toString()).isEqualTo("CHECKSUM_MISMATCH"));
        assertThat(flyway.validateWithResult().validationSuccessful).isTrue();
    }

    @Test void actualDatabaseEmptyFilterAndMixedSourcesPreserveProvenance() {
        assertThat(new CityService(new com.urbancommute.repository.CityRepository(jdbc, "missing")).listCities())
                .isEqualTo(new CityCatalog(List.of(), "database_catalog", null));
        new TransactionTemplate(transactionManager).executeWithoutResult(status -> {
            jdbc.update("INSERT INTO dataset_registry(dataset_id,source_name,source_type,license_status,dataset_version,description) VALUES ('other-source','x','simulation','not_applicable','v1','x')");
            jdbc.update("INSERT INTO city(id,name,dataset_id) VALUES ('mixed-city','mixed','other-source')");
            var catalog = cityService.listCities();
            assertThat(catalog.cities()).hasSize(3);
            assertThat(catalog.sourceType()).isEqualTo("mixed_catalog");
            assertThat(catalog.datasetId()).isNull();
            status.setRollbackOnly();
        });
    }

    @Test @org.springframework.transaction.annotation.Transactional
    void mixedSourcesReachControllerWithNullDatasetAndNoObservationTimestamp() throws Exception {
        jdbc.update("INSERT INTO dataset_registry(dataset_id,source_name,source_type,license_status,dataset_version,description) VALUES ('mixed-api-source','x','mock','not_applicable','v1','x')");
        jdbc.update("INSERT INTO city(id,name,dataset_id) VALUES ('mixed-api-city','mixed','mixed-api-source')");
        var body = json(mvc.perform(get("/api/v1/cities")).andExpect(status().isOk()).andReturn());
        assertThat(body.path("data").size()).isEqualTo(3);
        assertThat(body.at("/meta/sourceType").asText()).isEqualTo("mixed_catalog");
        assertThat(body.at("/meta/datasetId").isNull()).isTrue();
        assertThat(body.at("/meta/dataAsOf").isNull()).isTrue();
    }

    @ParameterizedTest @CsvSource({"sample-shanghai,sample-road,sample-road,2026-01-05,2026-01-05,10,2,fk_obs_road_same_city,1452", "sample-beijing,sample-road,other-road,2026-01-05,2026-01-05,10,2,ck_obs_target,3819", "sample-beijing,sample-road,sample-road,2026-01-05,2026-01-04,10,2,ck_obs_time_order,3819", "sample-beijing,sample-road,sample-road,2026-01-05,2026-01-05,251,2,ck_obs_speed,3819", "sample-beijing,sample-road,sample-road,2026-01-05,2026-01-05,10,11,ck_obs_congestion,3819"})
    void observationConstraintsAreDatabaseEnforced(String city, String road, String target, String observed,
            String collected, double speed, double congestion, String constraint, int code) {
        rejected("INSERT INTO traffic_observation(dataset_id,city_id,road_segment_id,target_type,target_id,observed_at,collected_at,avg_speed_kmh,congestion_index) VALUES ('s3-synthetic-cities-v1',?,?,'ROAD',?,?,?,?,?)",
                constraint, code, city, road, target, observed, collected, speed, congestion);
    }
}
