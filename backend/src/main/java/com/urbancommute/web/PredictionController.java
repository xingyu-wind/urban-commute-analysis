package com.urbancommute.web;

import com.urbancommute.api.ApiResponse;
import com.urbancommute.api.Prediction.Data;
import com.urbancommute.repository.PredictionRepository;
import jakarta.servlet.http.HttpServletRequest;
import java.util.Set;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.*;

@RestController
public class PredictionController {
    private final PredictionRepository repository;
    public PredictionController(PredictionRepository repository) { this.repository=repository; }
    @GetMapping(value="/api/v1/predictions", produces=MediaType.APPLICATION_JSON_VALUE)
    public ApiResponse<Data> predictions(HttpServletRequest request) {
        if (!Set.of("cityId","datasetId").containsAll(request.getParameterMap().keySet())
            || request.getParameterMap().values().stream().anyMatch(v->v.length!=1)
            || request.getContentLengthLong()>0 || request.getHeader("Transfer-Encoding")!=null) throw new InvalidRequestException();
        String city=id(request.getParameter("cityId")), dataset=request.getParameter("datasetId");
        if (dataset!=null) id(dataset);
        return repository.read(city,dataset,RequestIdFilter.requestId(request));
    }
    private static String id(String v) {
        if (v==null || v.length()>64 || !v.matches("[a-z][a-z0-9]*(-[a-z0-9]+)*")) throw new InvalidRequestException();
        return v;
    }
}
