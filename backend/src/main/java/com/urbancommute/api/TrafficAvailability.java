package com.urbancommute.api;

import java.util.List;
import java.util.Map;

/** Observed bounds are inclusive UTC instants; no observations are represented by zero/null. */
public record TrafficAvailability(String cityId, String defaultDatasetId, List<Dataset> datasets) {
    public record Range(long sampleCount, String firstObservedAt, String lastObservedAt) {}
    public record Dataset(String datasetId, String sourceType, Map<String, Range> levels,
            boolean predictionAvailable, String predictionCutoff) {}
}
