package com.urbancommute.web;

import com.urbancommute.api.ApiResponse;
import com.urbancommute.api.City;
import com.urbancommute.api.HealthResponse;
import com.urbancommute.api.ResponseMeta;
import com.urbancommute.service.CityService;
import jakarta.servlet.http.HttpServletRequest;
import java.time.Instant;
import java.time.format.DateTimeFormatter;
import java.util.List;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class ApiController {
    private final CityService cityService;

    public ApiController(CityService cityService) {
        this.cityService = cityService;
    }

    @GetMapping(value = "/health", produces = MediaType.APPLICATION_JSON_VALUE)
    public HealthResponse health(HttpServletRequest request) {
        validateRequest(request);
        return new HealthResponse("UP", DateTimeFormatter.ISO_INSTANT.format(Instant.now()));
    }

    @GetMapping(value = "/api/v1/cities", produces = MediaType.APPLICATION_JSON_VALUE)
    public ApiResponse<List<City>> cities(HttpServletRequest request) {
        validateRequest(request);
        return new ApiResponse<>("OK", "Success", cityService.listCities(),
                ResponseMeta.seed(RequestIdFilter.requestId(request)));
    }

    private void validateRequest(HttpServletRequest request) {
        if (!request.getParameterMap().isEmpty() || request.getContentLengthLong() > 0
                || request.getHeader("Transfer-Encoding") != null) {
            throw new InvalidRequestException();
        }
    }
}
