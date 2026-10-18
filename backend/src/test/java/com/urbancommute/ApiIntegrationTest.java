package com.urbancommute;

import static org.assertj.core.api.Assertions.assertThat;
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
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.test.context.bean.override.mockito.MockitoSpyBean;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@AutoConfigureMockMvc
class ApiIntegrationTest {
    @Autowired MockMvc mvc;
    @Autowired ObjectMapper mapper;
    @Autowired TestRestTemplate http;
    @Autowired Validator validator;
    @LocalServerPort int port;
    @MockitoSpyBean CityService cityService;

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

    @Test void citiesHaveStringIdsSeedMetadataAndExplicitNull() throws Exception {
        JsonNode body = json(mvc.perform(get("/api/v1/cities")).andExpect(status().isOk()).andReturn());
        assertThat(body.size()).isEqualTo(4);
        assertThat(body.path("code").asText()).isEqualTo("OK");
        assertThat(body.path("data").size()).isEqualTo(2);
        assertThat(body.at("/data/0/id").isTextual()).isTrue();
        assertThat(body.at("/data/0/id").asText()).isEqualTo("dev-city-001");
        assertThat(body.at("/meta/sourceType").asText()).isEqualTo("dev_seed");
        assertThat(body.at("/meta/datasetId").asText()).isEqualTo("dev-seed-cities-v1");
        assertThat(body.path("meta").has("dataAsOf")).isTrue();
        assertThat(body.at("/meta/dataAsOf").isNull()).isTrue();
    }

    @Test void emptyServiceResultRemainsHttp200Array() throws Exception {
        doReturn(List.of()).when(cityService).listCities();
        JsonNode body = live("cities-empty", "/api/v1/cities", 200);
        assertThat(body.path("data").isArray()).isTrue();
        assertThat(body.path("data").isEmpty()).isTrue();
        assertThat(body.at("/meta/sourceType").asText()).isEqualTo("dev_seed");
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
        doThrow(new IllegalStateException("private-path-and-secret-example" )).when(cityService).listCities();
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
        assertThat(validator.validate(new City("dev-city-001", "北京"))).isEmpty();
        assertThat(validator.validate(new City("INVALID ID", " "))).hasSize(2);
    }
}
