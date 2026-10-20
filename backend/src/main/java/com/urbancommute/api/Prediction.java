package com.urbancommute.api;

import java.math.BigDecimal;
import java.util.List;

public final class Prediction {
    private Prediction() {}
    public record Metrics(double mae, double rmse) {}
    public record Horizon(int step, double mae, double rmse) {}
    public record Evaluation(String split, String modelName, double mae, double rmse, List<Horizon> byHorizon) {}
    public record Actual(String date, double value, int sampleCount) {}
    public record Forecast(String date, BigDecimal value) {}
    public record Release(String jobId, String modelVersion, String modelName, String trainedAt,
        String generatedAt, String dataCutoff, String datasetVersion, String inputSha256,
        List<String> batchIds, List<String> sourceHashes, String limitation, Metrics metrics) {}
    public record Data(Release release, List<Actual> history, List<Forecast> predictions, List<Evaluation> evaluations) {}
}
