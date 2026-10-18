package com.urbancommute.api;

import com.fasterxml.jackson.annotation.JsonInclude;

@JsonInclude(JsonInclude.Include.ALWAYS)
public record ApiResponse<T>(String code, String message, T data, ResponseMeta meta) {}
