import { ApiClientError, getJson } from './client'
import type { WarehouseResponse } from '../types/warehouse'

type ObjectValue = Record<string, unknown>
const object = (v: unknown): v is ObjectValue => typeof v === 'object' && v !== null && !Array.isArray(v)
const shape = (v: unknown, fields: string[]): v is ObjectValue => object(v) && Object.keys(v).length === fields.length && fields.every(f => Object.hasOwn(v, f))
const text = (v: unknown, max = 64): v is string => typeof v === 'string' && v.length > 0 && v.length <= max
const id = (v: unknown): v is string => text(v) && /^[a-z][a-z0-9]*(-[a-z0-9]+)*$/.test(v)
const time = (v: unknown): v is string => typeof v === 'string' && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,3})?Z$/.test(v) && Number.isFinite(Date.parse(v))
const numeric = (v: unknown, max = Number.MAX_SAFE_INTEGER): v is number => typeof v === 'number' && Number.isFinite(v) && v >= 0 && v <= max
const hash = (v: unknown): v is string => typeof v === 'string' && /^[a-f0-9]{64}$/.test(v)
const uniqueStrings = (v: unknown, check: (item: unknown) => boolean) => Array.isArray(v) && v.length > 0 && v.every(item => check(item)) && new Set(v).size === v.length

export async function getWarehouse(cityId: string, datasetId: string): Promise<WarehouseResponse> {
  const query = new URLSearchParams({ cityId })
  if (datasetId) query.set('datasetId', datasetId)
  const value = await getJson('/api/v1/warehouse/metrics?' + query)
  const fail = (): never => { throw new ApiClientError('contract', '离线结果不符合接口约定。') }
  if (!shape(value, ['code', 'message', 'data', 'meta']) || value.code !== 'OK' || !text(value.message, 500)
    || !shape(value.meta, ['requestId', 'dataAsOf', 'sourceType', 'datasetId'])
    || typeof value.meta.requestId !== 'string' || !/^[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}$/i.test(value.meta.requestId)
    || (value.meta.dataAsOf !== null && !time(value.meta.dataAsOf))
    || !['dev_seed', 'synthetic_test', 'historical_snapshot', 'authorized_live'].includes(value.meta.sourceType as string)
    || !id(value.meta.datasetId) || (datasetId && value.meta.datasetId !== datasetId)
    || !shape(value.data, ['engine', 'release', 'items']) || value.data.engine !== 'Hive'
    || !Array.isArray(value.data.items) || value.data.items.length > 10000) return fail()
  const data = value.data
  const release = data.release
  if (release === null) {
    if ((data.items as unknown[]).length !== 0 || value.meta.dataAsOf !== null) return fail()
  } else if (!shape(release, ['id', 'datasetVersion', 'from', 'to', 'capturedAt', 'publishedAt', 'adsSha256', 'batchIds', 'sourceHashes'])
    || !text(release.id) || !text(release.datasetVersion) || !time(release.from) || !time(release.to)
    || Date.parse(release.from) >= Date.parse(release.to) || !time(release.publishedAt) || !time(release.capturedAt)
    || !hash(release.adsSha256) || !uniqueStrings(release.batchIds, text) || !uniqueStrings(release.sourceHashes, hash)) return fail()
  if (!(data.items as unknown[]).every(r => shape(r, ['targetType', 'targetId', 'roadRegionId', 'grain', 'bucketStart', 'sampleCount', 'speedSum', 'congestionSum', 'avgSpeedKmh', 'congestionIndex', 'observedFrom', 'observedTo'])
    && ['CITY', 'REGION', 'ROAD'].includes(r.targetType as string) && id(r.targetId)
    && (r.roadRegionId === null || (r.targetType === 'ROAD' && id(r.roadRegionId))) && r.grain === 'WINDOW'
    && Number.isSafeInteger(r.sampleCount) && (r.sampleCount as number) > 0 && time(r.bucketStart) && time(r.observedFrom) && time(r.observedTo)
    && Date.parse(r.observedFrom) <= Date.parse(r.observedTo) && numeric(r.speedSum) && numeric(r.congestionSum)
    && numeric(r.avgSpeedKmh, 250) && numeric(r.congestionIndex, 10))) return fail()
  return value as unknown as WarehouseResponse
}
