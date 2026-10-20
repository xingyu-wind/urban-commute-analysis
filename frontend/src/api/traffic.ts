import { ApiClientError, getJson } from './client'
import type { TrafficData, TrafficFilter, TrafficResponse } from '../types/traffic'

type Obj = Record<string, unknown>
const object = (v: unknown): v is Obj => typeof v === 'object' && v !== null && !Array.isArray(v)
const shape = (v: unknown, fields: string[]): v is Obj => object(v) && Object.keys(v).length === fields.length && fields.every(k => Object.hasOwn(v, k))
const string = (v: unknown, max: number) => typeof v === 'string' && !!v.trim() && v.length <= max
const id = (v: unknown) => string(v, 64) && /^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$/.test(v as string)
const time = (v: unknown) => typeof v === 'string' && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,3})?Z$/.test(v)
  && Number.isFinite(Date.parse(v)) && new Date(v).toISOString().replace(/\.0+Z$/, 'Z').replace(/(\.\d*?[1-9])0+Z$/, '$1Z') === v.replace(/\.0+Z$/, 'Z').replace(/(\.\d*?[1-9])0+Z$/, '$1Z')
const nullableTime = (v: unknown) => v === null || time(v)
const integer = (v: unknown, min: number, max = Number.MAX_SAFE_INTEGER) => typeof v === 'number' && Number.isSafeInteger(v) && v >= min && v <= max
const numeric = (v: unknown, min: number, max: number) => typeof v === 'number' && Number.isFinite(v) && v >= min && v <= max
function metrics(v: unknown): boolean {
  if (!shape(v, ['sampleCount', 'avgSpeedKmh', 'congestionIndex', 'dataAsOf']) || !integer(v.sampleCount, 0)) return false
  return v.sampleCount === 0 ? v.avgSpeedKmh === null && v.congestionIndex === null && v.dataAsOf === null
    : numeric(v.avgSpeedKmh, 0, 250) && numeric(v.congestionIndex, 0, 10) && time(v.dataAsOf)
}
export function validateTraffic<K extends keyof TrafficData>(endpoint: K, v: unknown): TrafficResponse<K> {
  const fail = () => { throw new ApiClientError('contract', '交通响应不符合接口约定，未展示无效统计。') }
  if (!shape(v, ['code', 'message', 'data', 'meta']) || v.code !== 'OK' || !string(v.message, 1000)
    || !shape(v.meta, ['requestId', 'dataAsOf', 'sourceType', 'datasetId'])
    || typeof v.meta.requestId !== 'string' || !/^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$/i.test(v.meta.requestId)
    || !nullableTime(v.meta.dataAsOf) || !id(v.meta.datasetId)
    || !['dev_seed', 'synthetic_test', 'historical_snapshot', 'authorized_live'].includes(v.meta.sourceType as string)) return fail()
  const fields = { summary: ['window', 'metrics'], series: ['window', 'granularity', 'items'], regions: ['window', 'items'], roads: ['window', 'page', 'pageSize', 'total', 'items'] }
  if (!shape(v.data, fields[endpoint])) return fail()
  const d = v.data
  if (!shape(d.window, ['cityId', 'from', 'to', 'level']) || !id(d.window.cityId) || !time(d.window.from) || !time(d.window.to)
    || Date.parse(d.window.from as string) >= Date.parse(d.window.to as string)
    || d.window.level !== ({ summary: 'CITY', series: 'CITY', regions: 'REGION', roads: 'ROAD' }[endpoint])) return fail()
  if (endpoint === 'summary') { if (!metrics(d.metrics)) return fail() }
  else {
    if (!Array.isArray(d.items)) return fail()
    if (endpoint === 'series' && (!['hour', 'day'].includes(d.granularity as string) || d.items.length > 745
      || !d.items.every(row => shape(row, ['bucket', 'metrics']) && time(row.bucket) && metrics(row.metrics)))) return fail()
    if (endpoint === 'regions' && !d.items.every(row => shape(row, ['id', 'name', 'latitude', 'longitude', 'coordinateSystem', 'metrics'])
      && id(row.id) && string(row.name, 100) && metrics(row.metrics)
      && ((row.latitude === null && row.longitude === null && row.coordinateSystem === null)
        || (numeric(row.latitude, -90, 90) && numeric(row.longitude, -180, 180) && row.coordinateSystem === 'WGS84')))) return fail()
    if (endpoint === 'roads' && (!integer(d.page, 1, 10000) || !integer(d.pageSize, 1, 100) || !integer(d.total, 0) || d.items.length > (d.pageSize as number)
      || !d.items.every(row => shape(row, ['id', 'name', 'regionId', 'metrics']) && id(row.id) && string(row.name, 160)
        && (row.regionId === null || id(row.regionId)) && metrics(row.metrics)))) return fail()
  }
  return v as unknown as TrafficResponse<K>
}
export async function getTraffic<K extends keyof TrafficData>(endpoint: K, filter: TrafficFilter, extra: Record<string, string> = {}): Promise<TrafficResponse<K>> {
  const params = new URLSearchParams({ ...filter, ...extra })
  const result = validateTraffic(endpoint, await getJson(`/api/v1/traffic/${endpoint}?${params}`))
  const w = result.data.window
  if (w.cityId !== filter.cityId || Date.parse(w.from) !== Date.parse(filter.from) || Date.parse(w.to) !== Date.parse(filter.to)
    || (filter.datasetId && result.meta.datasetId !== filter.datasetId)) throw new ApiClientError('contract', '交通响应与当前筛选不匹配。')
  return result
}
