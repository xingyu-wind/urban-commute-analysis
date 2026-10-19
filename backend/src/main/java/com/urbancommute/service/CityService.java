package com.urbancommute.service;

import com.urbancommute.api.City;
import com.urbancommute.repository.CityRepository;
import java.util.List;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class CityService {
    private final CityRepository repository;
    public CityService(CityRepository repository) { this.repository = repository; }

    @Transactional(readOnly = true)
    public CityCatalog listCities() {
        var rows = repository.findAll();
        List<City> cities = rows.stream().map(row -> new City(row.id(), row.name())).toList();
        if (rows.isEmpty()) return new CityCatalog(cities, "database_catalog", null);
        var first = rows.getFirst();
        boolean sameDataset = rows.stream().allMatch(row -> row.datasetId().equals(first.datasetId()));
        if (sameDataset) return new CityCatalog(cities, first.sourceType(), first.datasetId());
        // Never label a mixed catalog as homogeneous synthetic or authorized data.
        return new CityCatalog(cities, "mixed_catalog", null);
    }
}
