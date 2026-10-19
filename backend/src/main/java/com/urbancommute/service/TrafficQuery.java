package com.urbancommute.service;

import com.urbancommute.api.Traffic.Window;
import com.urbancommute.web.InvalidRequestException;
import jakarta.servlet.http.HttpServletRequest;
import java.time.Duration;
import java.time.Instant;
import java.time.OffsetDateTime;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;

public record TrafficQuery(String cityId, String datasetId, Instant from, Instant to,
        String granularity, String regionId, String search, int page, int pageSize) {
    public static TrafficQuery parse(HttpServletRequest request, String endpoint) {
        Set<String> allowed = new HashSet<>(Set.of("cityId", "datasetId", "from", "to"));
        if (endpoint.equals("series")) allowed.add("granularity");
        if (endpoint.equals("roads")) allowed.addAll(Set.of("regionId", "search", "page", "pageSize"));
        Map<String, String[]> params = request.getParameterMap();
        if (!allowed.containsAll(params.keySet()) || params.values().stream().anyMatch(v -> v.length != 1)
                || request.getContentLengthLong() > 0 || request.getHeader("Transfer-Encoding") != null) fail();
        String city = identifier(request.getParameter("cityId"));
        String dataset = request.getParameter("datasetId");
        if (dataset != null) identifier(dataset);
        Instant from = time(request.getParameter("from"));
        Instant to = time(request.getParameter("to"));
        String granularity = params.containsKey("granularity") ? request.getParameter("granularity") : "day";
        if (!Set.of("hour", "day").contains(granularity)) fail();
        long maximumDays = endpoint.equals("series") && granularity.equals("hour") ? 31 : 366;
        if (!from.isBefore(to) || Duration.between(from, to).compareTo(Duration.ofDays(maximumDays)) > 0) fail();
        String region = request.getParameter("regionId");
        if (region != null) identifier(region);
        String search = params.containsKey("search") ? request.getParameter("search") : "";
        if (search.length() > 100 || search.chars().anyMatch(Character::isISOControl)) fail();
        return new TrafficQuery(city, dataset, from, to, granularity, region, search,
                integer(request.getParameter("page"), 1, 10000), integer(request.getParameter("pageSize"), 10, 100));
    }
    public Window window(String level) { return new Window(cityId, from.toString(), to.toString(), level); }
    private static String identifier(String value) {
        if (value == null || value.length() > 64 || !value.matches("[a-z][a-z0-9]*(-[a-z0-9]+)*")) fail();
        return value;
    }
    private static Instant time(String value) {
        try {
            if (value == null || !value.matches("\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(\\.\\d{1,3})?(Z|[+-]\\d{2}:\\d{2})")) fail();
            Instant result = OffsetDateTime.parse(value).toInstant();
            if (result.isBefore(Instant.parse("2000-01-01T00:00:00Z")) || !result.isBefore(Instant.parse("2100-01-01T00:00:00Z"))) fail();
            return result;
        } catch (java.time.DateTimeException e) { throw new InvalidRequestException(); }
    }
    private static int integer(String value, int fallback, int max) {
        if (value == null) return fallback;
        if (!value.matches("[1-9][0-9]{0,4}")) fail();
        int result = Integer.parseInt(value);
        if (result > max) fail();
        return result;
    }
    private static void fail() { throw new InvalidRequestException(); }
}
