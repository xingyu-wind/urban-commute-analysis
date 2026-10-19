package com.urbancommute.service;

import com.urbancommute.api.City;
import java.util.List;

/** Source describes catalog contents, never the existence of live traffic observations. */
public record CityCatalog(List<City> cities, String sourceType, String datasetId) {}
