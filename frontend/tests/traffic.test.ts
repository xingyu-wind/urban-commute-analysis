import { describe, expect, it, vi, afterEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { validateTraffic } from '../src/api/traffic'
import TrafficDashboard from '../src/components/TrafficDashboard.vue'
import summary from '../../contracts/examples/traffic-summary.json'
import series from '../../contracts/examples/traffic-series.json'
import regions from '../../contracts/examples/traffic-regions.json'
import roads from '../../contracts/examples/traffic-roads.json'

vi.mock('../src/components/TrafficChart.vue', () => ({ default: { props: ['option', 'label'], template: '<div class="test-chart" :aria-label="label"></div>' } }))
const fixtures = { summary, series, regions, roads }
const json = (v: unknown) => new Response(JSON.stringify(v), { headers: { 'content-type': 'application/json' } })
const wrappers: ReturnType<typeof mount>[] = []
afterEach(() => { wrappers.splice(0).forEach(w => w.unmount()); vi.unstubAllGlobals() })
describe('S4 response guards', () => {
  it.each(['summary', 'series', 'regions', 'roads'] as const)('accepts independent %s contract', endpoint => {
    expect(validateTraffic(endpoint, fixtures[endpoint])).toEqual(fixtures[endpoint])
  })
  it.each([
    (v: typeof summary) => { v.data.metrics.sampleCount = 0 },
    (v: typeof summary) => { v.data.metrics.congestionIndex = 11 },
    (v: typeof summary) => { v.meta.sourceType = 'forecast' },
    (v: typeof summary) => { v.data.window.level = 'ROAD' },
    (v: typeof summary) => { v.meta.dataAsOf = '2026-02-30T08:00:00Z' },
    (v: typeof summary) => { Object.assign(v.data.metrics, { vehicles: 100 }) },
  ])('rejects false counts, wrong levels/sources, dates and extra fields', mutate => {
    const bad = structuredClone(summary); mutate(bad)
    expect(() => validateTraffic('summary', bad)).toThrow('交通响应不符合接口约定')
  })
  it('rejects partially missing or non-WGS84 coordinates', () => {
    const bad = structuredClone(regions); bad.data.items[0]!.longitude = null
    expect(() => validateTraffic('regions', bad)).toThrow()
    bad.data.items[0]!.coordinateSystem = 'GCJ02'
    expect(() => validateTraffic('regions', bad)).toThrow()
  })
})
function api() {
  return vi.fn(async (url: string) => {
    const uri = new URL(url, 'http://localhost'), endpoint = uri.pathname.split('/').at(-1)! as keyof typeof fixtures
    const value = structuredClone(fixtures[endpoint])
    Object.assign(value.data.window, { cityId: uri.searchParams.get('cityId'), from: uri.searchParams.get('from'), to: uri.searchParams.get('to') })
    if (endpoint === 'summary' && uri.searchParams.get('cityId') === 'new-city') (value as typeof summary).data.metrics.avgSpeedKmh = 77
    return json(value)
  })
}
function start() { const w = mount(TrafficDashboard, { props: { cityId: 's4-demo-city', cityName: '合成演示城市' } }); wrappers.push(w); return w }
describe('S4 dashboard lifecycle', () => {
  it('renders API metrics, explicit synthetic provenance and map coordinate omissions', async () => {
    vi.stubGlobal('fetch', api()); const w = start(); await flushPromises()
    expect(w.get('[data-testid=kpi-speed]').text()).toContain('36.00')
    expect(w.get('[data-testid=kpi-count]').text()).toContain('3')
    expect(w.text()).toContain('synthetic_test 合成测试')
    expect(w.findAll('[data-map-point]')).toHaveLength(1)
    expect(w.text()).toContain('1 个区域缺少坐标已省略')
    await w.get('[data-map-point]').trigger('click'); await flushPromises()
    expect(w.text()).toContain('当前联动：演示东区')
  })
  it('clears old metrics on failed refresh and supports retry', async () => {
    const fetch = api(); vi.stubGlobal('fetch', fetch); const w = start(); await flushPromises()
    fetch.mockRejectedValue(new Error('offline'))
    await w.get('form').trigger('submit'); await flushPromises()
    expect(w.find('[data-testid=kpi-speed]').exists()).toBe(false)
    expect(w.get('[role=alert]').text()).toContain('分析暂不可用')
    fetch.mockImplementation(api()); await w.get('[role=alert] button').trigger('click'); await flushPromises()
    expect(w.get('[data-testid=kpi-speed]').text()).toContain('36.00')
  })
  it('ignores a late response after city selection changes', async () => {
    const pending: (() => void)[] = []
    vi.stubGlobal('fetch', vi.fn((url: string) => {
      const actual = api()(url)
      return url.includes('s4-demo-city') ? new Promise<Response>(resolve => { pending.push(() => { void actual.then(resolve) }) }) : actual
    }))
    const w = start(); await w.setProps({ cityId: 'new-city', cityName: '新城市' }); await flushPromises()
    expect(w.get('[data-testid=kpi-speed]').text()).toContain('77.00')
    for (const resolve of pending) resolve()
    await flushPromises()
    expect(w.text()).toContain('窗口')
    expect(w.text()).toContain('新城市')
    expect(w.get('[data-testid=kpi-speed]').text()).toContain('77.00')
    expect(w.find('[role=alert]').exists()).toBe(false)
  })
})
