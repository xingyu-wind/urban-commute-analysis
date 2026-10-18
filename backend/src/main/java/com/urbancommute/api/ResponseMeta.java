package com.urbancommute.api;

import com.fasterxml.jackson.annotation.JsonInclude;

@JsonInclude(JsonInclude.Include.ALWAYS)
public record ResponseMeta(String requestId, String dataAsOf, String sourceType, String datasetId) {
    public static ResponseMeta seed(String requestId) {
        return new ResponseMeta(requestId, null, "dev_seed", "dev-seed-cities-v1");
    }

    public static ResponseMeta error(String requestId) {
        return new ResponseMeta(requestId, null, null, null);
    }
}
