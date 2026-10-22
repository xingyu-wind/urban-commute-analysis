import { ApiClientError, getJson } from './client'

export interface ObservationRange { sampleCount: number; firstObservedAt: string | null; lastObservedAt: string | null }
export interface DatasetAvailability {
  datasetId: string; sourceType: string
  levels: Record<'CITY' | 'REGION' | 'ROAD', ObservationRange>
  predictionAvailable: boolean; predictionCutoff: string | null
}
export interface Availability { cityId: string; defaultDatasetId: string; datasets: DatasetAvailability[] }
const obj = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null && !Array.isArray(v)
const shape = (v: unknown, fields: string[]): v is Record<string, unknown> => obj(v) && Object.keys(v).length === fields.length && fields.every(k => Object.hasOwn(v, k))
const identifier = (v: unknown): v is string => typeof v === 'string' && v.length <= 64 && /^[a-z][a-z0-9]*(-[a-z0-9]+)*$/.test(v)
const time = (v: unknown): v is string => typeof v === 'string' && /^20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,3})?Z$/.test(v) && Number.isFinite(Date.parse(v)) && new Date(v).toISOString().replace(/\.0+Z$/, 'Z').replace(/(\.\d*?[1-9])0+Z$/, '$1Z') === v.replace(/\.0+Z$/, 'Z').replace(/(\.\d*?[1-9])0+Z$/, '$1Z')
export function validateAvailability(value: unknown, cityId: string): Availability {
  const fail = (): never => { throw new ApiClientError('contract', '数据范围响应无效，请重试。') }
  if (!shape(value, ['code', 'message', 'meta', 'data']) || value.code !== 'OK' || typeof value.message !== 'string' || !value.message.trim()
    || !shape(value.meta, ['requestId', 'dataAsOf', 'sourceType', 'datasetId']) || typeof value.meta.requestId !== 'string' || !value.meta.requestId.trim()
    || value.meta.dataAsOf !== null || value.meta.sourceType !== null || value.meta.datasetId !== null
    || !shape(value.data, ['cityId', 'defaultDatasetId', 'datasets'])) return fail()
  const d = value.data
  if (d.cityId !== cityId || !identifier(d.defaultDatasetId) || !Array.isArray(d.datasets) || !d.datasets.length) return fail()
  const ids = new Set<string>()
  for (const row of d.datasets) {
    if (!shape(row, ['datasetId', 'sourceType', 'levels', 'predictionAvailable', 'predictionCutoff']) || !identifier(row.datasetId) || ids.has(row.datasetId)
      || !['dev_seed', 'synthetic_test', 'historical_snapshot', 'authorized_live', 'simulation', 'mock', 'forecast'].includes(String(row.sourceType))
      || !shape(row.levels, ['CITY', 'REGION', 'ROAD']) || typeof row.predictionAvailable !== 'boolean'
      || (row.predictionAvailable ? !time(row.predictionCutoff) : row.predictionCutoff !== null)) return fail()
    ids.add(row.datasetId)
    for (const level of ['CITY', 'REGION', 'ROAD']) {
      const range = row.levels[level]
      if (!shape(range, ['sampleCount', 'firstObservedAt', 'lastObservedAt']) || !Number.isSafeInteger(range.sampleCount) || Number(range.sampleCount) < 0) return fail()
      if (range.sampleCount === 0 ? range.firstObservedAt !== null || range.lastObservedAt !== null
        : !time(range.firstObservedAt) || !time(range.lastObservedAt) || Date.parse(range.firstObservedAt) > Date.parse(range.lastObservedAt)) return fail()
    }
  }
  if (!ids.has(d.defaultDatasetId)) return fail()
  return d as unknown as Availability
}
export async function getAvailability(cityId: string): Promise<Availability> {
  return validateAvailability(await getJson('/api/v1/traffic/availability?' + new URLSearchParams({ cityId })), cityId)
}
export function supportsAnalysis(dataset: DatasetAvailability): boolean {
  return ['dev_seed', 'synthetic_test', 'historical_snapshot', 'authorized_live'].includes(dataset.sourceType)
}
export function statusLabel(datasets: DatasetAvailability[]): string {
  const stats = datasets.some(d => supportsAnalysis(d) && Object.values(d.levels).some(r => r.sampleCount > 0))
  const predictions = datasets.some(d => supportsAnalysis(d) && d.predictionAvailable)
  return stats && predictions ? '统计 · 预测' : stats ? '有统计数据' : predictions ? '有预测数据' : '仅目录登记 · 暂无数据'
}
/** Date inputs describe a UTC half-open window; include the last observed day. */
export function recentWindow(dataset: DatasetAvailability): { from: string; to: string } | null {
  if (!supportsAnalysis(dataset)) return null
  const ranges = Object.values(dataset.levels).filter(r => r.sampleCount > 0)
  if (!ranges.length) return null
  const last = Math.max(...ranges.map(r => Date.parse(r.lastObservedAt!)))
  const first = Math.min(...ranges.map(r => Date.parse(r.firstObservedAt!)))
  const end = Date.parse(new Date(last).toISOString().slice(0, 10)) + 86400000
  return { from: new Date(Math.max(Date.parse(new Date(first).toISOString().slice(0, 10)), end - 7 * 86400000)).toISOString().slice(0, 10), to: new Date(end).toISOString().slice(0, 10) }
}
