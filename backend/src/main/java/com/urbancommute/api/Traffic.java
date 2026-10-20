package com.urbancommute.api;

import java.math.BigDecimal;
import java.util.List;

/** Sample arithmetic means, never vehicle counts or cross-level estimates. Times are UTC. */
public final class Traffic {
    private Traffic() {}
    public record Window(String cityId, String from, String to, String level) {}
    public record Metrics(long sampleCount, BigDecimal avgSpeedKmh, BigDecimal congestionIndex, String dataAsOf) {}
    public record Summary(Window window, Metrics metrics) {}
    public record Bucket(String bucket, Metrics metrics) {}
    public record Series(Window window, String granularity, List<Bucket> items) {}
    public record Region(String id, String name, Double latitude, Double longitude, String coordinateSystem, Metrics metrics) {}
    public record Regions(Window window, List<Region> items) {}
    public record Road(String id, String name, String regionId, Metrics metrics) {}
    public record Roads(Window window, int page, int pageSize, long total, List<Road> items) {}
}
