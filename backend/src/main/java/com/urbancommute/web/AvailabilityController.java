package com.urbancommute.web;

import com.urbancommute.api.*;
import com.urbancommute.repository.AvailabilityRepository;
import jakarta.servlet.http.HttpServletRequest;
import java.util.Set;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.*;

@RestController
public class AvailabilityController {
    private final AvailabilityRepository repository;
    public AvailabilityController(AvailabilityRepository repository) { this.repository = repository; }
    @GetMapping(value = "/api/v1/traffic/availability", produces = MediaType.APPLICATION_JSON_VALUE)
    public ApiResponse<TrafficAvailability> availability(HttpServletRequest request) {
        var params = request.getParameterMap();
        String cityId = request.getParameter("cityId");
        if (!params.keySet().equals(Set.of("cityId")) || params.values().stream().anyMatch(v -> v.length != 1)
                || cityId == null || cityId.length() > 64 || !cityId.matches("[a-z][a-z0-9]*(-[a-z0-9]+)*")
                || request.getContentLengthLong() > 0 || request.getHeader("Transfer-Encoding") != null)
            throw new InvalidRequestException();
        return repository.read(cityId, RequestIdFilter.requestId(request));
    }
}
