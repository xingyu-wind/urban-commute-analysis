import { afterEach, describe, expect, it, vi } from 'vitest'
import { getWarehouse } from '../src/api/warehouse'

const fixture = () => ({ code: 'OK', message: 'Success',
  meta: { requestId: '00112233-4455-6677-8899-aabbccddeeff', datasetId: 'synthetic', sourceType: 'synthetic_test', dataAsOf: '2026-10-16T00:00:00Z' },
  data: { engine: 'Hive', release: { id: 'release-1', datasetVersion: '1', from: '2026-10-15T00:00:00Z', to: '2026-10-17T00:00:00Z',
    capturedAt: '2026-10-20T00:00:00Z', publishedAt: '2026-10-20T00:01:00Z', adsSha256: 'a'.repeat(64), batchIds: ['batch-1'], sourceHashes: ['b'.repeat(64)] },
    items: [{ targetType: 'CITY', targetId: 'city', roadRegionId: null, grain: 'WINDOW', bucketStart: '2026-10-15T00:00:00Z',
      sampleCount: 2, speedSum: 60, congestionSum: 4, avgSpeedKmh: 30, congestionIndex: 2,
      observedFrom: '2026-10-15T00:00:00Z', observedTo: '2026-10-16T00:00:00Z' }] } })
function serve(value: unknown) {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify(value), { headers: { 'content-type': 'application/json' } })))
}
afterEach(() => vi.unstubAllGlobals())
describe('Hive wire response guard', () => {
  it('accepts published provenance and metrics', async () => {
    serve(fixture())
    expect((await getWarehouse('city', 'synthetic')).data.items[0]?.sampleCount).toBe(2)
  })
  it('accepts an explicit unpublished empty result', async () => {
    const f = fixture()
    serve({ ...f, meta: { ...f.meta, dataAsOf: null }, data: { engine: 'Hive', release: null, items: [] } })
    expect((await getWarehouse('city', '')).data.release).toBeNull()
  })
  it.each(['zero-count', 'null-mean', 'string-number', 'unpublished-metrics', 'wrong-dataset', 'extra-field', 'bad-provenance'])('rejects %s', async kind => {
    const value = fixture()
    const changed = JSON.parse(JSON.stringify(value))
    if (kind === 'zero-count') changed.data.items[0].sampleCount = 0
    if (kind === 'null-mean') changed.data.items[0].avgSpeedKmh = null
    if (kind === 'string-number') changed.data.items[0].avgSpeedKmh = '30'
    if (kind === 'unpublished-metrics') changed.data.release = null
    if (kind === 'wrong-dataset') changed.meta.datasetId = 'other'
    if (kind === 'extra-field') changed.data.items[0].forecast = 40
    if (kind === 'bad-provenance') changed.data.release.sourceHashes = ['bad']
    serve(changed)
    await expect(getWarehouse('city', 'synthetic')).rejects.toMatchObject({ kind: 'contract' })
  })
})
