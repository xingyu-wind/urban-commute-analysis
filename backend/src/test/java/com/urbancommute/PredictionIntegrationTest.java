package com.urbancommute;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;
import com.fasterxml.jackson.databind.*;
import java.util.*;
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
class PredictionIntegrationTest {
    @DynamicPropertySource static void database(DynamicPropertyRegistry registry) { IsolatedMySql.properties(registry); }
    @Autowired MockMvc mvc;
    @Autowired JdbcTemplate jdbc;
    @Autowired ObjectMapper mapper;
    @BeforeEach void catalog() {
        jdbc.update("INSERT INTO dataset_registry VALUES ('s7-unit','owned','synthetic_test','not_applicable',NULL,'1','synthetic unit',UTC_TIMESTAMP(3))");
        jdbc.update("INSERT INTO city(id,name,dataset_id) VALUES ('s7-unit-city','test','s7-unit')");
    }
    JsonNode read() throws Exception {
        return mapper.readTree(mvc.perform(get("/api/v1/predictions").param("cityId","s7-unit-city"))
            .andExpect(status().isOk()).andReturn().getResponse().getContentAsString());
    }
    void release(String state) throws Exception {
        var doc=mapper.createObjectNode();
        doc.put("modelVersion","a".repeat(64)).put("inputSha256","b".repeat(64)).put("modelName","seasonal7")
            .put("trainedAt","2026-10-20T01:00:00.000Z").put("generatedAt","2026-10-20T01:00:00.000Z")
            .put("dataCutoff","2026-10-19T00:00:00.000Z").put("dataAsOf","2026-10-18T18:17:00.000Z")
            .put("datasetVersion","1").put("sourceType","synthetic_test").put("limitation","合成演示");
        doc.putArray("batchIds").add("unit-batch"); doc.putArray("sourceHashes").add("c".repeat(64));
        doc.putObject("metrics").put("mae",.2).put("rmse",.3);
        doc.putArray("history").addObject().put("date","2026-10-18").put("value",4.5).put("sampleCount",4);
        jdbc.update("INSERT INTO prediction_model VALUES (REPEAT('a',64),REPEAT('b',64),'{}','{}')");
        jdbc.update("""
            INSERT INTO prediction_job(job_id,model_version,city_id,dataset_id,data_cutoff,generated_at,content_sha256,status,document,published_at)
            VALUES (REPEAT('d',32),REPEAT('a',64),'s7-unit-city','s7-unit','2026-10-19','2026-10-20',REPEAT('e',64),?,?,UTC_TIMESTAMP(3))
            """,state,mapper.writeValueAsString(doc));
        for (int i=1;i<=7;i++) jdbc.update("INSERT INTO prediction_result VALUES (REPEAT('d',32),?,?,?)",i,"2026-10-"+(18+i),4+i*.1);
        jdbc.update("INSERT INTO prediction_current VALUES ('s7-unit-city','s7-unit',REPEAT('d',32))");
    }
    @Test void emptyHasSourceAndRequestId() throws Exception {
        var response=read();
        assertThat(response.path("data").path("release").isNull()).isTrue();
        assertThat(response.path("data").path("predictions").size()).isZero();
        assertThat(response.path("meta").path("dataAsOf").isNull()).isTrue();
        assertThat(response.path("meta").path("sourceType").asText()).isEqualTo("synthetic_test");
        UUID.fromString(response.path("meta").path("requestId").asText());
    }
    @ParameterizedTest @ValueSource(strings={"FAILED","STAGING"})
    void hidesUnpublished(String state) throws Exception {
        release(state); assertThat(read().path("data").path("release").isNull()).isTrue();
    }
    @Test void availabilityReportsOnlyCurrentCompatiblePublishedPrediction() throws Exception {
        release("PUBLISHED");
        var response = mapper.readTree(mvc.perform(get("/api/v1/traffic/availability").param("cityId", "s7-unit-city"))
            .andExpect(status().isOk()).andReturn().getResponse().getContentAsString());
        var dataset = response.at("/data/datasets/0");
        assertThat(dataset.path("predictionAvailable").asBoolean()).isTrue();
        assertThat(dataset.path("predictionCutoff").asText()).isEqualTo(read().at("/data/release/dataCutoff").asText());
        assertThat(dataset.at("/levels/CITY/sampleCount").asInt()).isZero();
        jdbc.update("UPDATE dataset_registry SET dataset_version='2' WHERE dataset_id='s7-unit'");
        var incompatible = mapper.readTree(mvc.perform(get("/api/v1/traffic/availability").param("cityId", "s7-unit-city"))
            .andExpect(status().isOk()).andReturn().getResponse().getContentAsString());
        assertThat(incompatible.at("/data/datasets/0/predictionAvailable").asBoolean()).isFalse();
        assertThat(incompatible.at("/data/datasets/0/predictionCutoff").isNull()).isTrue();
    }
    @Test void readsPublishedVersionAndOrderedSevenPoints() throws Exception {
        release("PUBLISHED"); var response=read();
        assertThat(response.path("data").path("release").path("modelVersion").asText()).isEqualTo("a".repeat(64));
        assertThat(response.path("data").path("predictions").size()).isEqualTo(7);
        assertThat(response.at("/data/predictions/0/date").asText()).isEqualTo("2026-10-19");
        assertThat(response.at("/data/predictions/6/value").asDouble()).isEqualTo(4.7);
        assertThat(response.at("/meta/dataAsOf").asText()).isEqualTo("2026-10-18T18:17:00.000Z");
    }
    @Test void registryChangeCannotRelabelPublishedModel() throws Exception {
        release("PUBLISHED"); jdbc.update("UPDATE dataset_registry SET dataset_version='2' WHERE dataset_id='s7-unit'");
        mvc.perform(get("/api/v1/predictions?cityId=s7-unit-city")).andExpect(status().isBadRequest());
    }
    @ParameterizedTest @ValueSource(strings={"", "?cityId=unknown", "?cityId=UPPER", "?cityId=s7-unit-city&cityId=s7-unit-city", "?cityId=s7-unit-city&extra=1", "?cityId=s7-unit-city&datasetId=missing"})
    void rejectsMalformedQueries(String query) throws Exception {
        var r=mvc.perform(get("/api/v1/predictions"+query)).andExpect(status().isBadRequest()).andReturn();
        assertThat(mapper.readTree(r.getResponse().getContentAsString()).path("code").asText()).isEqualTo("BAD_REQUEST");
    }
    @Test void rejectsBodiesAndWrites() throws Exception {
        mvc.perform(get("/api/v1/predictions?cityId=s7-unit-city").content("{}")).andExpect(status().isBadRequest());
        mvc.perform(post("/api/v1/predictions?cityId=s7-unit-city")).andExpect(status().isMethodNotAllowed());
    }
}
