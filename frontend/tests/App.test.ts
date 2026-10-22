import { mount, flushPromises } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from '../src/App.vue'
import health from '../../contracts/examples/health-success.json'
import cities from '../../contracts/examples/cities-success.json'
import availability from '../../contracts/examples/traffic-availability.json'
vi.mock('../src/components/TrafficDashboard.vue', () => ({ default: { props: ['cityId', 'availability', 'view'], template: '<div data-testid="traffic-view">{{ cityId }} / {{ availability.datasetId }}</div>' } }))
vi.mock('../src/components/PredictionPanel.vue', () => ({ default: { props: ['cityId', 'datasetId'], template: '<div data-testid="prediction-view">{{ cityId }} / {{ datasetId }}</div>' } }))
vi.mock('../src/components/OperationsPanel.vue', () => ({ default: { template: '<div data-testid="management-view">管理登录</div>' } }))
const wrappers: ReturnType<typeof mount>[] = []
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
const metadata = (id: string, populated = true) => {
  const v = structuredClone(availability); v.data.cityId = id
  if (!populated) Object.values(v.data.datasets[0]!.levels).forEach(r => Object.assign(r, { sampleCount: 0, firstObservedAt: null, lastObservedAt: null }))
  return v
}
function responses() { return vi.fn(async (path: string) => json(path === '/health' ? health : path === '/api/v1/cities' ? cities : metadata(new URL(path, 'http://localhost').searchParams.get('cityId')!, path.includes('shanghai')))) }
const start = () => { const w = mount(App); wrappers.push(w); return w }
vi.stubGlobal('scrollTo', vi.fn())
afterEach(() => { wrappers.splice(0).forEach(w => w.unmount()); vi.unstubAllGlobals(); vi.useRealTimers(); location.hash = '' })
describe('workbench navigation and real metadata association', () => {
  it('has five visible entries and defaults to populated city without requiring login', async () => {
    const fetch = responses(); vi.stubGlobal('fetch', fetch)
    const w = start(); await flushPromises()
    expect(w.findAll('nav button')).toHaveLength(5)
    expect(w.get('h1').text()).toBe('总览首页')
    expect(w.get('[aria-label="城市选择"]').element).toHaveProperty('value', 'sample-shanghai')
    expect(w.get('[data-testid="traffic-view"]').text()).toContain('sample-shanghai / s4-synthetic-v1')
    expect(w.find('[data-testid="management-view"]').exists()).toBe(false)
    expect(fetch.mock.calls.some(([path]) => path.includes('/auth/'))).toBe(false)
    expect(w.text()).not.toContain('本地开发环境')
  })
  it('labels directory-only cities and dataset states, with full provenance in details', async () => {
    vi.stubGlobal('fetch', responses()); const w = start(); await flushPromises()
    const labels = w.findAll('[aria-label="城市选择"] option').map(o => o.text())
    expect(labels[0]).toContain('仅目录登记 · 暂无数据')
    expect(labels[1]).toContain('有统计数据')
    expect(w.get('.source-badge').text()).toBe('合成演示数据')
    expect(w.get('.data-details').text()).toContain('不表示外部授权真实性已经核实')
    expect(w.get('.data-details').attributes('open')).toBeUndefined()
  })
  it('switches city and clears previous dataset association', async () => {
    vi.stubGlobal('fetch', responses()); const w = start(); await flushPromises()
    await w.get('[aria-label="城市选择"]').setValue('sample-beijing')
    expect(w.get('[data-testid="selected-city"]').text()).toBe('北京')
    expect(w.get('[data-testid="traffic-view"]').text()).toContain('sample-beijing')
    expect(w.get('[data-testid="traffic-view"]').text()).not.toContain('sample-shanghai')
  })
  it('changes datasets centrally for both statistics and predictions', async () => {
    const fetch = responses(); fetch.mockImplementation(async path => {
      if (path.includes('availability')) {
        const v = metadata(new URL(path, 'http://localhost').searchParams.get('cityId')!)
        v.data.datasets.push({ ...structuredClone(v.data.datasets[0]!), datasetId: 'second-dataset' }); return json(v)
      }
      return json(path === '/health' ? health : cities)
    }); vi.stubGlobal('fetch', fetch); const w = start(); await flushPromises()
    await w.get('[aria-label="数据集选择"]').setValue('second-dataset')
    expect(w.get('[data-testid="traffic-view"]').text()).toContain('second-dataset')
    expect(w.get('[data-testid="prediction-view"]').text()).toContain('second-dataset')
  })
  it('uses hash navigation, provides management only on entry, supports deep links', async () => {
    location.hash = '#prediction'; vi.stubGlobal('fetch', responses()); const w = start(); await flushPromises()
    expect(w.get('h1').text()).toBe('智能预测')
    await w.findAll('nav button')[3]!.trigger('click')
    expect(w.find('[data-testid="management-view"]').exists()).toBe(true)
    expect(location.hash).toBe('#management')
  })
  it('shows loading without claiming a healthy backend', () => {
    vi.stubGlobal('fetch', vi.fn(() => new Promise(() => {}))); const w = start()
    expect(w.text()).toContain('正在检查服务'); expect(w.text()).toContain('正在读取城市')
    expect(w.find('[data-testid="traffic-view"]').exists()).toBe(false)
  })
  it('retains a failed metadata city as retryable rather than claiming no data', async () => {
    const fetch = responses(); fetch.mockImplementation(async path => path.includes('availability') ? json({}, 503) : json(path === '/health' ? health : cities))
    vi.stubGlobal('fetch', fetch); const w = start(); await flushPromises()
    expect(w.get('[role="alert"]').text()).toContain('HTTP 503')
    expect(w.findAll('[aria-label="城市选择"] option')[0]!.text()).toContain('范围读取失败')
    fetch.mockImplementation(responses()); await w.get('[role="alert"] button').trigger('click'); await flushPromises()
    expect(w.find('[role="alert"]').exists()).toBe(false)
    expect(w.find('[data-testid="traffic-view"]').exists()).toBe(true)
  })
  it('removes stale analysis on failed catalog refresh and recovers', async () => {
    const fetch = responses(); vi.stubGlobal('fetch', fetch); const w = start(); await flushPromises()
    fetch.mockRejectedValue(new TypeError('offline')); await w.get('.topbar button').trigger('click'); await flushPromises()
    expect(w.get('[role="alert"]').text()).toContain('无法连接服务')
    expect(w.find('[data-testid="traffic-view"]').exists()).toBe(false)
    fetch.mockImplementation(responses()); await w.get('[role="alert"] button').trigger('click'); await flushPromises()
    expect(w.find('[data-testid="traffic-view"]').exists()).toBe(true)
  })
  it('does not equate an empty catalog with available observations', async () => {
    vi.stubGlobal('fetch', vi.fn(async path => json(path === '/health' ? health : { ...cities, data: [] })))
    const w = start(); await flushPromises(); expect(w.text()).toContain('暂无可选城市')
    expect(w.find('[data-testid="traffic-view"]').exists()).toBe(false)
  })
  it('checks service every fifteen seconds without resetting a manual selection', async () => {
    vi.useFakeTimers(); const fetch = responses(); vi.stubGlobal('fetch', fetch); const w = start(); await flushPromises()
    await w.get('[aria-label="城市选择"]').setValue('sample-beijing')
    fetch.mockRejectedValue(new TypeError('offline')); await vi.advanceTimersByTimeAsync(15000); await flushPromises()
    expect(w.text()).toContain('服务暂不可用')
    expect(w.get('[aria-label="城市选择"]').element).toHaveProperty('value', 'sample-beijing')
  })
})
