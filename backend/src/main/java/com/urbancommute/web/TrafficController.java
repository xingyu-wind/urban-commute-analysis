package com.urbancommute.web;

import com.urbancommute.api.ApiResponse;
import com.urbancommute.repository.TrafficRepository;
import com.urbancommute.service.TrafficQuery;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.*;

@RestController
public class TrafficController {
    private final TrafficRepository repository;
    public TrafficController(TrafficRepository repository) { this.repository = repository; }
    @GetMapping(value = {"/api/v1/traffic/summary", "/api/v1/traffic/series", "/api/v1/traffic/regions", "/api/v1/traffic/roads"}, produces = MediaType.APPLICATION_JSON_VALUE)
    public ApiResponse<?> traffic(HttpServletRequest request) {
        String endpoint = request.getRequestURI().substring(request.getRequestURI().lastIndexOf('/') + 1);
        return repository.read(TrafficQuery.parse(request, endpoint), endpoint, RequestIdFilter.requestId(request));
    }
}
