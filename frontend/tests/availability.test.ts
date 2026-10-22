import { describe, expect, it } from 'vitest'
import fixture from '../../contracts/examples/traffic-availability.json'
import { recentWindow, statusLabel, validateAvailability } from '../src/api/availability'
const read = () => validateAvailability(structuredClone(fixture), 's4-demo-city')
describe('availability metadata and UTC windows', () => {
  it('defaults to actual latest dates, includes last day and never uses today', () => {
    expect(recentWindow(read().datasets[0]!)).toEqual({ from: '2026-10-15', to: '2026-10-17' })
  })
  it('limits recent observations to seven days across month/year boundaries', () => {
    const d = read().datasets[0]!
    Object.values(d.levels).forEach(r => Object.assign(r, { firstObservedAt: '2024-01-01T10:00:00Z', lastObservedAt: '2025-01-02T23:59:59Z' }))
    expect(recentWindow(d)).toEqual({ from: '2024-12-27', to: '2025-01-03' })
  })
  it('does not conflate predictions and observed statistics', () => {
    const d = read().datasets[0]!
    Object.values(d.levels).forEach(r => Object.assign(r, { sampleCount: 0, firstObservedAt: null, lastObservedAt: null }))
    expect(recentWindow(d)).toBeNull(); expect(statusLabel([d])).toContain('仅目录登记')
    d.predictionAvailable = true; expect(statusLabel([d])).toBe('有预测数据')
  })
  it.each(['city', 'bounds', 'count', 'duplicate', 'prediction'])('rejects malformed %s metadata', bad => {
    const f = structuredClone(fixture)
    if (bad === 'city') f.data.cityId = 'other-city'
    if (bad === 'bounds') f.data.datasets[0]!.levels.CITY.firstObservedAt = '2026-10-20T00:00:00Z'
    if (bad === 'count') f.data.datasets[0]!.levels.ROAD.sampleCount = -1
    if (bad === 'duplicate') f.data.datasets.push(f.data.datasets[0]!)
    if (bad === 'prediction') f.data.datasets[0]!.predictionAvailable = true
    expect(() => validateAvailability(f, 's4-demo-city')).toThrow()
  })
})
