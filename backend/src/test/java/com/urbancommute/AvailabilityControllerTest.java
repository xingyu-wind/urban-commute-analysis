package com.urbancommute;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;
import com.urbancommute.api.*;
import com.urbancommute.repository.AvailabilityRepository;
import com.urbancommute.web.*;
import java.util.List;
import org.junit.jupiter.api.*;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

class AvailabilityControllerTest {
    static class StubRepository extends AvailabilityRepository {
        int calls;
        StubRepository() { super(null, ""); }
        @Override public ApiResponse<TrafficAvailability> read(String cityId, String requestId) {
            calls++;
            if (cityId.equals("missing")) throw new InvalidRequestException();
            if (cityId.equals("offline")) throw new org.springframework.jdbc.CannotGetJdbcConnectionException("offline");
            return new ApiResponse<>("OK", "Success", new TrafficAvailability(cityId, "dataset", List.of()),
                new ResponseMeta("test", null, null, null));
        }
    }
    StubRepository repository;
    MockMvc mvc;
    @BeforeEach void setup() {
        repository = new StubRepository();
        mvc = MockMvcBuilders.standaloneSetup(new AvailabilityController(repository))
            .setControllerAdvice(new ApiExceptionHandler()).build();
    }
    @ParameterizedTest
    @ValueSource(strings = {"", "?cityId=", "?cityId=Bad", "?cityId=city&cityId=other",
        "?cityId=city&datasetId=other", "?cityId=city&from=2026-01-01"})
    void malformedQueriesNeverReachDatabase(String query) throws Exception {
        mvc.perform(get("/api/v1/traffic/availability" + query)).andExpect(status().isBadRequest());
        assertThat(repository.calls).isZero();
    }
    @Test void bodyAndTransferEncodingRejected() throws Exception {
        mvc.perform(get("/api/v1/traffic/availability?cityId=city").content("{}"))
            .andExpect(status().isBadRequest());
        mvc.perform(get("/api/v1/traffic/availability?cityId=city").header("Transfer-Encoding", "chunked"))
            .andExpect(status().isBadRequest());
        assertThat(repository.calls).isZero();
    }
    @Test void validCityIsPassedWithoutChangesAndUnknownCityIsBadRequest() throws Exception {
        mvc.perform(get("/api/v1/traffic/availability?cityId=city")).andExpect(status().isOk())
            .andExpect(jsonPath("$.data.cityId").value("city"));
        mvc.perform(get("/api/v1/traffic/availability?cityId=missing")).andExpect(status().isBadRequest());
    }
    @Test void databaseFailureUsesExistingUnavailableEnvelopeAndCanRecover() throws Exception {
        mvc.perform(get("/api/v1/traffic/availability?cityId=offline"))
            .andExpect(status().isServiceUnavailable()).andExpect(jsonPath("$.code").value("SERVICE_UNAVAILABLE"));
        mvc.perform(get("/api/v1/traffic/availability?cityId=city")).andExpect(status().isOk());
    }
}
