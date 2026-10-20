package com.urbancommute.web;

import com.urbancommute.api.ApiResponse;
import com.urbancommute.api.Warehouse.Data;
import com.urbancommute.repository.WarehouseRepository;
import jakarta.servlet.http.HttpServletRequest;
import java.util.Set;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.*;

@RestController
public class WarehouseController {
    private final WarehouseRepository repository;
    public WarehouseController(WarehouseRepository repository) { this.repository=repository; }
    @GetMapping(value="/api/v1/warehouse/metrics",produces=MediaType.APPLICATION_JSON_VALUE)
    public ApiResponse<Data> metrics(HttpServletRequest request) {
        if (!Set.of("cityId","datasetId","grain").containsAll(request.getParameterMap().keySet())
                || request.getParameterMap().values().stream().anyMatch(v->v.length!=1)
                || request.getContentLengthLong()>0 || request.getHeader("Transfer-Encoding")!=null)
            throw new InvalidRequestException();
        String city=id(request.getParameter("cityId"));
        String dataset=request.getParameter("datasetId");
        if (dataset!=null) id(dataset);
        String grain=request.getParameter("grain");
        if (grain==null) grain="WINDOW";
        if (!Set.of("WINDOW","DAY","HOUR").contains(grain)) throw new InvalidRequestException();
        return repository.read(city,dataset,grain,RequestIdFilter.requestId(request));
    }
    private static String id(String value) {
        if (value==null || value.length()>64 || !value.matches("[a-z][a-z0-9]*(-[a-z0-9]+)*")) throw new InvalidRequestException();
        return value;
    }
}
