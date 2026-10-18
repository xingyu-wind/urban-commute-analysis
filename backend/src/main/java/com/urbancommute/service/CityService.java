package com.urbancommute.service;

import com.urbancommute.api.City;
import java.util.List;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

@Service
public class CityService {
    private static final List<City> SEED = List.of(
            new City("dev-city-001", "北京"), new City("dev-city-002", "上海"));
    private final boolean seedEnabled;

    public CityService(@Value("${commute.cities.seed-enabled:true}") boolean seedEnabled) {
        this.seedEnabled = seedEnabled;
    }

    public List<City> listCities() {
        return seedEnabled ? SEED : List.of();
    }
}
