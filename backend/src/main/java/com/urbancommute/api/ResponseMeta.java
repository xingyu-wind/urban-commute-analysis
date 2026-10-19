package com.urbancommute.api;

import com.fasterxml.jackson.annotation.JsonInclude;

@JsonInclude(JsonInclude.Include.ALWAYS)
public record ResponseMeta(String requestId, String dataAsOf, String sourceType, String datasetId) {
    public static ResponseMeta catalog(String requestId, String sourceType, String datasetId) {
        // Catalog membership is NOT a traffic observation and has no observed-at timestamp.
        return new ResponseMeta(requestId, null, sourceType, datasetId);
    }

    public static ResponseMeta error(String requestId) {
        return new ResponseMeta(requestId, null, null, null);
    }
}
