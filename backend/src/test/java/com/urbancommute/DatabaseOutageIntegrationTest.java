package com.urbancommute;

import static org.assertj.core.api.Assertions.assertThat;
import com.fasterxml.jackson.databind.JsonNode;
import java.net.InetAddress;
import java.net.ServerSocket;
import java.nio.file.Files;
import java.nio.file.Path;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

/** Actual JDBC handshake timeout, with no service/repository mocks and no live DB changes. */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT, properties = {
    "spring.flyway.enabled=false", "spring.datasource.hikari.initialization-fail-timeout=-1",
    "spring.datasource.hikari.connection-timeout=1000"})
class DatabaseOutageIntegrationTest {
    private static final ServerSocket unavailable;
    static {
        try { unavailable = new ServerSocket(0, 1, InetAddress.getByName("127.0.0.1")); }
        catch (java.io.IOException error) { throw new ExceptionInInitializerError(error); }
    }
    @DynamicPropertySource static void unavailableDatabase(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", () -> "jdbc:mysql://127.0.0.1:" + unavailable.getLocalPort()
                + "/unavailable?connectTimeout=200&socketTimeout=200");
        registry.add("spring.datasource.username", () -> "outage-test");
        registry.add("spring.datasource.password", () -> "not-a-real-password");
    }
    @Autowired TestRestTemplate http;
    @AfterAll static void closeSocket() throws Exception { unavailable.close(); }

    @Test void jdbcUnavailableReturnsSafe503WhileLivenessStaysUp() throws Exception {
        assertThat(http.getForObject("/health", JsonNode.class).path("status").asText()).isEqualTo("UP");
        for (String route : new String[]{"/api/v1/cities", "/api/v1/traffic/summary", "/api/v1/traffic/series", "/api/v1/traffic/regions", "/api/v1/traffic/roads"}) {
        String query = route.contains("/traffic/") ? "?cityId=s4-demo-city&from=2026-10-15T00:00:00Z&to=2026-10-17T00:00:00Z" : "";
        var response = http.getForEntity(route + query, JsonNode.class);
        assertThat(response.getStatusCode().value()).isEqualTo(503);
        var body = response.getBody();
        assertThat(body.path("code").asText()).isEqualTo("SERVICE_UNAVAILABLE");
        assertThat(body.path("data").isNull()).isTrue();
        assertThat(body.at("/meta/requestId").asText()).isEqualTo(response.getHeaders().getFirst("X-Request-Id"));
        assertThat(body.toString()).doesNotContain("jdbc:", "outage-test", "not-a-real-password", "SQLException");
        assertThat(http.getForObject("/health", JsonNode.class).path("status").asText()).isEqualTo("UP");
        Path directory = Path.of("target", "http-test-evidence");
        Files.createDirectories(directory);
        Files.writeString(directory.resolve("actual-jdbc-unavailable-" + route.substring(route.lastIndexOf('/') + 1) + ".json"), body.toPrettyString());
        }
    }
}
