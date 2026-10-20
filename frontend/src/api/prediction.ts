import { ApiClientError, getJson } from './client'
import type { PredictionResponse } from '../types/prediction'

type Obj = Record<string, unknown>
const shape = (v: unknown, keys: string[]): v is Obj => typeof v === 'object' && v !== null && !Array.isArray(v)
  && Object.keys(v).length === keys.length && keys.every(k => Object.hasOwn(v, k))
const text = (v: unknown): v is string => typeof v === 'string' && v.length > 0 && v.length <= 500
const hash = (v: unknown) => typeof v === 'string' && /^[a-f0-9]{64}$/.test(v)
const num = (v: unknown, max = 10): v is number => typeof v === 'number' && Number.isFinite(v) && v >= 0 && v <= max
const day = (v: unknown): v is string => typeof v === 'string' && /^20\d\d-\d\d-\d\d$/.test(v)
  && Number.isFinite(Date.parse(v)) && new Date(v).toISOString().slice(0, 10) === v
const time = (v: unknown): v is string => typeof v === 'string' && /^20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,3})?Z$/.test(v)
  && Number.isFinite(Date.parse(v)) && day(v.slice(0, 10))
const models = ['naive', 'seasonal7', 'random_forest', 'xgboost']
const metric = (v: unknown): v is { mae: number; rmse: number } => shape(v, ['mae', 'rmse']) && num(v.mae) && num(v.rmse)
const strings = (v: unknown, check: (v: unknown) => boolean) => Array.isArray(v) && v.length > 0 && v.every(check) && new Set(v).size === v.length

export function validatePrediction(value: unknown, datasetId = ''): PredictionResponse {
  const fail = (): never => { throw new ApiClientError('contract', '预测响应不符合接口约定。') }
  if (!shape(value, ['code', 'message', 'meta', 'data']) || value.code !== 'OK' || !text(value.message)
    || !shape(value.meta, ['requestId', 'dataAsOf', 'sourceType', 'datasetId'])
    || typeof value.meta.requestId !== 'string' || !/^[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}$/i.test(value.meta.requestId)
    || !['dev_seed', 'synthetic_test', 'historical_snapshot', 'authorized_live'].includes(value.meta.sourceType as string)
    || !text(value.meta.datasetId) || !/^[a-z][a-z0-9]*(-[a-z0-9]+)*$/.test(value.meta.datasetId)
    || (datasetId && value.meta.datasetId !== datasetId)
    || !shape(value.data, ['release', 'history', 'predictions', 'evaluations'])
    || !Array.isArray(value.data.history) || !Array.isArray(value.data.predictions) || !Array.isArray(value.data.evaluations)) return fail()
  const { release: r, history, predictions, evaluations } = value.data
  if (r === null) {
    if (history.length || predictions.length || evaluations.length || value.meta.dataAsOf !== null) return fail()
  } else {
    if (!shape(r, ['jobId', 'modelVersion', 'modelName', 'trainedAt', 'generatedAt', 'dataCutoff', 'datasetVersion', 'inputSha256', 'batchIds', 'sourceHashes', 'limitation', 'metrics'])
      || typeof r.jobId !== 'string' || !/^[a-f0-9]{32}$/.test(r.jobId) || !hash(r.modelVersion) || !hash(r.inputSha256)
      || !models.includes(r.modelName as string) || !time(r.trainedAt) || !time(r.generatedAt) || !time(r.dataCutoff)
      || !/^20\d\d-\d\d-\d\dT00:00:00(?:\.000)?Z$/.test(r.dataCutoff)
      || !text(r.datasetVersion) || !text(r.limitation) || !metric(r.metrics)
      || !strings(r.batchIds, text) || !strings(r.sourceHashes, hash) || !time(value.meta.dataAsOf)
      || Date.parse(value.meta.dataAsOf) >= Date.parse(r.dataCutoff)
      || (value.meta.sourceType === 'synthetic_test' && !r.limitation.includes('合成'))
      || history.length !== 28 || predictions.length !== 7 || evaluations.length !== 8) return fail()
    const cutoff = Date.parse(r.dataCutoff as string)
    if (!history.every((p, i) => shape(p, ['date', 'value', 'sampleCount']) && day(p.date) && num(p.value)
      && Number.isSafeInteger(p.sampleCount) && (p.sampleCount as number) >= 4 && Date.parse(p.date) === cutoff + (i - 28) * 86400000)
      || !predictions.every((p, i) => shape(p, ['date', 'value']) && day(p.date) && num(p.value) && Date.parse(p.date) === cutoff + i * 86400000)) return fail()
    const identities = new Set<string>()
    for (const e of evaluations) {
      if (!shape(e, ['split', 'modelName', 'mae', 'rmse', 'byHorizon']) || !['validation', 'test'].includes(e.split as string)
        || !models.includes(e.modelName as string) || !num(e.mae) || !num(e.rmse) || !Array.isArray(e.byHorizon) || e.byHorizon.length !== 7
        || !e.byHorizon.every((h, i) => shape(h, ['step', 'mae', 'rmse']) && h.step === i + 1 && num(h.mae) && num(h.rmse))) return fail()
      identities.add(`${e.split}/${e.modelName}`)
    }
    if (identities.size !== 8) return fail()
    const test = evaluations.find(e => e.split === 'test' && e.modelName === r.modelName)
    if (!test || !metric(r.metrics) || test.mae !== r.metrics.mae || test.rmse !== r.metrics.rmse) return fail()
  }
  return value as unknown as PredictionResponse
}

export async function getPredictions(cityId: string, datasetId: string): Promise<PredictionResponse> {
  const query = new URLSearchParams({ cityId })
  if (datasetId) query.set('datasetId', datasetId)
  return validatePrediction(await getJson('/api/v1/predictions?' + query), datasetId)
}
