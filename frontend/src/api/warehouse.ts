import { ApiClientError, getJson } from './client'
import type { WarehouseResponse } from '../types/warehouse'

export async function getWarehouse(cityId: string, datasetId: string): Promise<WarehouseResponse> {
  const query = new URLSearchParams({ cityId })
  if (datasetId) query.set('datasetId', datasetId)
  const value = await getJson('/api/v1/warehouse/metrics?' + query) as WarehouseResponse
  const data = value?.data
  const time = (v: unknown) => typeof v === 'string' && /Z$/.test(v) && Number.isFinite(Date.parse(v))
  const finite = (v: unknown) => typeof v === 'number' && Number.isFinite(v)
  if (value?.code !== 'OK' || !value.meta || typeof value.meta.datasetId !== 'string'
    || data?.engine !== 'Hive' || !Array.isArray(data.items)
    || (data.release === null ? data.items.length !== 0 : !data.release || typeof data.release.id !== 'string'
      || typeof data.release.datasetVersion !== 'string' || !time(data.release.from) || !time(data.release.to)
      || !time(data.release.publishedAt) || !time(data.release.capturedAt)
      || !Array.isArray(data.release.batchIds) || !Array.isArray(data.release.sourceHashes)
      || !/^[a-f0-9]{64}$/.test(data.release.adsSha256))
    || !data.items.every(r => ['CITY', 'REGION', 'ROAD'].includes(r.targetType) && typeof r.targetId === 'string'
      && (r.roadRegionId === null || typeof r.roadRegionId === 'string') && r.grain === 'WINDOW'
      && Number.isSafeInteger(r.sampleCount) && r.sampleCount > 0 && time(r.bucketStart) && time(r.observedFrom) && time(r.observedTo)
      && finite(r.speedSum) && finite(r.congestionSum) && finite(r.avgSpeedKmh) && r.avgSpeedKmh >= 0 && r.avgSpeedKmh <= 250
      && finite(r.congestionIndex) && r.congestionIndex >= 0 && r.congestionIndex <= 10)) {
    throw new ApiClientError('contract', '离线结果不符合接口约定。')
  }
  return value
}
