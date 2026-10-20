package com.urbancommute;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;
import com.fasterxml.jackson.databind.*;
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
class WarehouseIntegrationTest {
    @DynamicPropertySource static void database(DynamicPropertyRegistry registry) { IsolatedMySql.properties(registry); }
    @Autowired MockMvc mvc;
    @Autowired JdbcTemplate jdbc;
    @Autowired ObjectMapper mapper;
    @BeforeEach void catalog() {
        jdbc.update("INSERT INTO dataset_registry VALUES ('s6-unit','owned','synthetic_test','not_applicable',NULL,'1','synthetic unit',UTC_TIMESTAMP(3))");
        jdbc.update("INSERT INTO city(id,name,dataset_id) VALUES ('s6-unit-city','synthetic city','s6-unit')");
    }
    JsonNode read() throws Exception {
        return mapper.readTree(mvc.perform(get("/api/v1/warehouse/metrics").param("cityId","s6-unit-city"))
            .andExpect(status().isOk()).andReturn().getResponse().getContentAsString());
    }
    void release(String state) {
        jdbc.update("""
            INSERT INTO warehouse_release(release_id,status,content_sha256,ads_sha256,window_from,window_to,captured_at,published_at,manifest,row_count)
            VALUES ('s6-unit-release',?,REPEAT('a',64),REPEAT('b',64),'2026-10-15','2026-10-17','2026-10-20','2026-10-20',
              '{"batches":[{"dataset_id":"s6-unit","batch_id":"s6-unit-batch","source_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}]}',1)
            """,state);
        jdbc.update("""
            INSERT INTO warehouse_metric VALUES ('s6-unit-release','s6-unit','1','synthetic_test','s6-unit-city','CITY','s6-unit-city',NULL,
              'WINDOW','2026-10-15',3,120,15,40,5,'2026-10-15','2026-10-16')
            """);
        jdbc.update("INSERT INTO warehouse_current VALUES (1,'s6-unit-release')");
    }
    @Test void noPublicationHasExplicitEmptyState() throws Exception {
        var result=read();
        assertThat(result.at("/data/release").isNull()).isTrue();
        assertThat(result.at("/data/items").size()).isZero();
        assertThat(result.at("/meta/dataAsOf").isNull()).isTrue();
    }
    @ParameterizedTest @ValueSource(strings={"STAGING","FAILED"})
    void unpublishedReleaseIsNeverVisibleEvenWithPointer(String state) throws Exception {
        release(state);
        assertThat(read().at("/data/release").isNull()).isTrue();
        assertThat(read().at("/data/items").size()).isZero();
    }
    @Test void publishedAdsReturnsPersistedMetricsAndTraceability() throws Exception {
        release("PUBLISHED");
        var result=read();
        assertThat(result.at("/data/items/0/avgSpeedKmh").decimalValue()).isEqualByComparingTo("40.00");
        assertThat(result.at("/data/items/0/sampleCount").asLong()).isEqualTo(3);
        assertThat(result.at("/data/release/batchIds/0").asText()).isEqualTo("s6-unit-batch");
        assertThat(result.at("/meta/sourceType").asText()).isEqualTo("synthetic_test");
    }
    @ParameterizedTest @ValueSource(strings={"cityId=missing-city","cityId=s6-unit-city&grain=minute",
        "cityId=s6-unit-city&from=x","cityId=s6-unit-city&cityId=s6-unit-city","cityId=s6-unit-city&datasetId=","cityId="})
    void invalidFiltersFailClosed(String query) throws Exception {
        mvc.perform(get(java.net.URI.create("/api/v1/warehouse/metrics?"+query))).andExpect(status().isBadRequest());
    }
}
