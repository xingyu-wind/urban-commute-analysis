import { describe, expect, it } from 'vitest'
import { validatePrediction } from '../src/api/prediction'
const fixture = () => {
  const cutoff = Date.parse('2026-10-19T00:00:00Z')
  const date = (i: number) => new Date(cutoff + i * 86400000).toISOString().slice(0, 10)
  return { code: 'OK', message: 'Success', meta: { requestId: '00112233-4455-6677-8899-aabbccddeeff',
    datasetId: 'synthetic', sourceType: 'synthetic_test', dataAsOf: '2026-10-18T18:17:00.000Z' },
  data: { release: { jobId: 'd'.repeat(32), modelVersion: 'a'.repeat(64), modelName: 'seasonal7',
    trainedAt: '2026-10-20T01:00:00.000Z', generatedAt: '2026-10-20T01:00:00.000Z', dataCutoff: '2026-10-19T00:00:00.000Z',
    datasetVersion: '1', inputSha256: 'b'.repeat(64), batchIds: ['batch'], sourceHashes: ['c'.repeat(64)],
    limitation: '合成演示', metrics: { mae: .2, rmse: .3 } },
  history: Array.from({ length: 28 }, (_, i) => ({ date: date(i - 28), value: 4, sampleCount: 4 })),
  predictions: Array.from({ length: 7 }, (_, i) => ({ date: date(i), value: 4 })),
  evaluations: ['validation', 'test'].flatMap(split => ['naive', 'seasonal7', 'random_forest', 'xgboost'].map(modelName => ({
    split, modelName, mae: .2, rmse: .3, byHorizon: Array.from({ length: 7 }, (_, i) => ({ step: i + 1, mae: .2, rmse: .3 })) }))) } }
}
describe('published prediction wire contract', () => {
  it('accepts seven UTC days and explicit demo provenance', () => {
    expect(validatePrediction(fixture(), 'synthetic').data.predictions).toHaveLength(7)
  })
  it('accepts no published model without manufacturing zeros', () => {
    const f = fixture()
    expect(validatePrediction({ ...f, meta: { ...f.meta, dataAsOf: null }, data: { release: null, history: [], predictions: [], evaluations: [] } }).data.release).toBeNull()
  })
  it.each(['gap', 'duplicate', 'outside-bound', 'string', 'sparse', 'no-source', 'bad-model', 'wrong-metric', 'future-asof', 'bad-date', 'extra', 'hidden-demo', 'duplicate-evaluation', 'wrong-horizon'])('rejects %s', kind => {
    const f = fixture()
    if (kind === 'gap') f.data.predictions.pop()
    if (kind === 'duplicate') f.data.predictions[1]!.date = f.data.predictions[0]!.date
    if (kind === 'outside-bound') f.data.predictions[0]!.value = 10.1
    if (kind === 'string') Object.assign(f.data.predictions[0]!, { value: '4' })
    if (kind === 'sparse') f.data.history[0]!.sampleCount = 1
    if (kind === 'no-source') f.data.release.sourceHashes = []
    if (kind === 'bad-model') f.data.release.modelVersion = 'model'
    if (kind === 'wrong-metric') f.data.release.metrics.mae = 8
    if (kind === 'future-asof') f.meta.dataAsOf = f.data.release.dataCutoff
    if (kind === 'bad-date') f.data.predictions[0]!.date = '2026-02-30'
    if (kind === 'extra') Object.assign(f.data.predictions[0]!, { vehicles: 500 })
    if (kind === 'hidden-demo') f.data.release.limitation = 'accuracy is real'
    if (kind === 'duplicate-evaluation') f.data.evaluations[0] = f.data.evaluations[1]!
    if (kind === 'wrong-horizon') f.data.evaluations[0]!.byHorizon[0]!.step = 7
    expect(() => validatePrediction(f)).toThrow('预测响应不符合接口约定')
  })
})
