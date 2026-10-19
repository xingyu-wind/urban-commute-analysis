import type { CitySource } from './api'

export interface Metrics { sampleCount: number; avgSpeedKmh: number | null; congestionIndex: number | null; dataAsOf: string | null }
export interface TrafficWindow { cityId: string; from: string; to: string; level: 'CITY' | 'REGION' | 'ROAD' }
export interface TrafficRegion { id: string; name: string; latitude: number | null; longitude: number | null; coordinateSystem: 'WGS84' | null; metrics: Metrics }
export interface TrafficRoad { id: string; name: string; regionId: string | null; metrics: Metrics }
export interface TrafficData {
  summary: { window: TrafficWindow; metrics: Metrics }
  series: { window: TrafficWindow; granularity: 'hour' | 'day'; items: { bucket: string; metrics: Metrics }[] }
  regions: { window: TrafficWindow; items: TrafficRegion[] }
  roads: { window: TrafficWindow; page: number; pageSize: number; total: number; items: TrafficRoad[] }
}
export interface TrafficResponse<K extends keyof TrafficData> {
  code: 'OK'; message: string; data: TrafficData[K]
  meta: { requestId: string; dataAsOf: string | null; sourceType: Extract<CitySource, 'dev_seed' | 'synthetic_test' | 'historical_snapshot' | 'authorized_live'>; datasetId: string }
}
export interface TrafficFilter { cityId: string; from: string; to: string; datasetId?: string }
