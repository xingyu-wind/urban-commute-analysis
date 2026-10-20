
export type Metrics = { mae: number; rmse: number }
export type PredictionResponse = {
  code: 'OK'; message: string; meta: { requestId: string; dataAsOf: string | null; sourceType: string; datasetId: string }
  data: {
    release: null | {
      jobId: string; modelVersion: string; modelName: string; trainedAt: string; generatedAt: string
      dataCutoff: string; datasetVersion: string; inputSha256: string; batchIds: string[]
      sourceHashes: string[]; limitation: string; metrics: Metrics
    }
    history: { date: string; value: number; sampleCount: number }[]
    predictions: { date: string; value: number }[]
    evaluations: (Metrics & { split: 'validation' | 'test'; modelName: string; byHorizon: (Metrics & { step: number })[] })[]
  }
}
