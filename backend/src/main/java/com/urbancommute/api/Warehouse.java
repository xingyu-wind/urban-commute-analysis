package com.urbancommute.api;

import java.math.BigDecimal;
import java.util.List;

public final class Warehouse {
    private Warehouse() {}
    public record Release(String id, String datasetVersion, String from, String to, String capturedAt,
            String publishedAt, String adsSha256, List<String> batchIds, List<String> sourceHashes) {}
    public record Metric(String targetType, String targetId, String roadRegionId, String grain,
            String bucketStart, long sampleCount, BigDecimal speedSum, BigDecimal congestionSum,
            BigDecimal avgSpeedKmh, BigDecimal congestionIndex, String observedFrom, String observedTo) {}
    public record Data(String engine, Release release, List<Metric> items) {}
}
