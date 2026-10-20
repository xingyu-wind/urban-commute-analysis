import type { TrafficResponse } from './traffic'
export interface WarehouseRelease {
  id: string; datasetVersion: string; from: string; to: string; capturedAt: string
  publishedAt: string; adsSha256: string; batchIds: string[]; sourceHashes: string[]
}
export interface WarehouseMetric {
  targetType: 'CITY' | 'REGION' | 'ROAD'; targetId: string; roadRegionId: string | null
  grain: 'WINDOW' | 'DAY' | 'HOUR'; bucketStart: string; sampleCount: number
  speedSum: number; congestionSum: number; avgSpeedKmh: number; congestionIndex: number
  observedFrom: string; observedTo: string
}
export interface WarehouseResponse {
  code: 'OK'; message: string; meta: TrafficResponse<'summary'>['meta']
  data: { engine: 'Hive'; release: WarehouseRelease | null; items: WarehouseMetric[] }
}
