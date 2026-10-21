package com.urbancommute;

import static org.assertj.core.api.Assertions.assertThat;
import java.net.URI;
import java.net.http.*;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.context.annotation.Import;
import org.springframework.test.context.*;
import org.springframework.web.bind.annotation.*;

/** Real embedded HTTP: registering a new Controller must not implicitly authorize it. */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@Import({IsolatedMySql.class, DefaultDenialIntegrationTest.FutureController.class})
class DefaultDenialIntegrationTest {
    @DynamicPropertySource static void database(DynamicPropertyRegistry registry) { IsolatedMySql.properties(registry); }
    @LocalServerPort int port;
    @RestController
    static class FutureController {
        static final AtomicInteger writes = new AtomicInteger();
        @RequestMapping({"/api/v1/traffic/future-write", "/api/v1/warehouse/future-write", "/future-write"})
        String write() { writes.incrementAndGet(); return "must never execute"; }
    }
    @Test void futureControllersAreDeniedBeforeInvocationOverRealHttp() throws Exception {
        var client = HttpClient.newHttpClient();
        for (String path : new String[]{"/api/v1/traffic/future-write", "/api/v1/warehouse/future-write", "/future-write"}) {
            for (String method : new String[]{"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"}) {
                var response = client.send(HttpRequest.newBuilder(URI.create("http://127.0.0.1:"+port+path))
                    .method(method, HttpRequest.BodyPublishers.noBody()).build(), HttpResponse.BodyHandlers.ofString());
                assertThat(response.statusCode()).isEqualTo(404);
                assertThat(response.body()).contains("\"code\":\"NOT_FOUND\"");
                assertThat(response.headers().firstValue("X-Request-Id")).isPresent();
            }
        }
        assertThat(FutureController.writes.get()).isZero();
    }
}
