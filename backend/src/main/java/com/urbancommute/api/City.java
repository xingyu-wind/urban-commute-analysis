package com.urbancommute.api;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

public record City(
        @NotBlank @Size(max = 64) @Pattern(regexp = "^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$") String id,
        @NotBlank @Size(max = 100) String name) {}
