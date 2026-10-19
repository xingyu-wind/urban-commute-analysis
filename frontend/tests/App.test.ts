import { mount, flushPromises } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { VueWrapper } from '@vue/test-utils'
import App from '../src/App.vue'
import health from '../../contracts/examples/health-success.json'
import cities from '../../contracts/examples/cities-success.json'

const wrappers: VueWrapper[] = []
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
const start = () => { const wrapper = mount(App); wrappers.push(wrapper); return wrapper }
function responses(body: unknown = cities) {
  return vi.fn().mockImplementation((path: string) => Promise.resolve(json(path === '/health' ? health : body)))
}
afterEach(() => { wrappers.splice(0).forEach(wrapper => wrapper.unmount()); vi.unstubAllGlobals(); vi.useRealTimers() })

describe('city dashboard', () => {
  it.each([
    ['dev_seed','开发样例'], ['historical_snapshot','历史快照登记'],
    ['authorized_live','授权来源登记'], ['simulation','模拟数据'],
    ['mock','模拟接口'], ['forecast','预测数据'], ['mixed_catalog','混合来源目录'],
  ])('labels %s without treating it as synthetic or actual traffic', async (sourceType, label) => {
    vi.stubGlobal('fetch', responses({ ...cities, meta: { ...cities.meta, sourceType, datasetId: sourceType === 'mixed_catalog' ? null : 'source-v1' } }))
    const wrapper = start(); await flushPromises()
    expect(wrapper.get('.source-badge').text()).toContain(label)
    expect(wrapper.get('.source-badge').text()).toContain(sourceType)
    expect(wrapper.get('.data-notice').text()).toContain(sourceType === 'mixed_catalog' ? '多个数据集' : sourceType)
    expect(wrapper.get('.data-notice').text()).not.toContain('北京')
    expect(wrapper.get('.data-notice').text()).not.toContain('上海')
  })
  it.each(['historical_snapshot', 'authorized_live'])('qualifies %s as a database registration, not verified external authorization', async sourceType => {
    vi.stubGlobal('fetch', responses({ ...cities, meta: { ...cities.meta, sourceType } }))
    const wrapper = start(); await flushPromises()
    expect(wrapper.get('.data-notice').text()).toContain('仅为数据库登记')
    expect(wrapper.get('.data-notice').text()).toContain('不表示外部授权真实性已经核实')
    expect(wrapper.get('.source-badge').text()).not.toContain('已授权')
    expect(wrapper.get('.subtitle').text()).toContain('外部授权真实性仍需另行核实')
  })
  it('shows loading without prematurely claiming the backend is healthy', () => {
    vi.stubGlobal('fetch', vi.fn(() => new Promise(() => {})))
    const wrapper = start()
    expect(wrapper.text()).toContain('正在检查服务')
    expect(wrapper.text()).toContain('正在加载城市列表')
    expect(wrapper.text()).not.toContain('服务正常')
    expect(wrapper.get('button').attributes('disabled')).toBeDefined()
    expect(wrapper.get('.data-notice').text()).toContain('数据来源尚未确认')
  })
  it('renders real-contract synthetic MySQL catalog choices and changes the selected city', async () => {
    vi.stubGlobal('fetch', responses())
    const wrapper = start(); await flushPromises()
    expect(wrapper.text()).toContain('服务正常')
    expect(wrapper.text()).toContain('synthetic_test')
    expect(wrapper.get('.data-notice').text()).toContain('synthetic_test 合成测试数据')
    expect(wrapper.get('.data-notice').text()).not.toContain('北京、上海')
    expect(wrapper.text()).toContain('不适用（城市目录非交通观测）')
    expect(wrapper.findAll('option').map(option => option.text())).toEqual(['请选择城市', '北京', '上海'])
    await wrapper.get('select').setValue('sample-beijing')
    expect(wrapper.get('[data-testid="selected-city"]').text()).toBe('北京')
    await wrapper.get('select').setValue('sample-shanghai')
    expect(wrapper.get('[data-testid="selected-city"]').text()).toBe('上海')
  })
  it.each(['database_catalog', 'synthetic_test', 'authorized_live'])('describes an empty %s response without inferring any city provenance', async sourceType => {
    vi.stubGlobal('fetch', responses({ ...cities, data: [], meta: { ...cities.meta, sourceType, datasetId: sourceType === 'database_catalog' ? null : 'source-v1' } }))
    const wrapper = start(); await flushPromises()
    expect(wrapper.text()).toContain('暂无可选城市')
    expect(wrapper.text()).toContain('服务正常')
    expect(wrapper.get('.source-badge').text()).toContain(sourceType)
    expect(wrapper.get('.data-notice').text()).toContain('本次 API 未返回城市条目')
    expect(wrapper.get('.data-notice').text()).not.toContain('synthetic_test')
    expect(wrapper.find('select').exists()).toBe(false)
  })
  it('updates the notice when actual responses change from synthetic to mixed, registered and empty', async () => {
    const fetch = responses()
    vi.stubGlobal('fetch', fetch)
    const wrapper = start(); await flushPromises()
    expect(wrapper.get('.data-notice').text()).toContain('synthetic_test 合成测试数据')
    for (const [sourceType, datasetId, data, expected] of [
      ['mixed_catalog', null, cities.data, '多个数据集'],
      ['authorized_live', 'registered-v1', cities.data, '不表示外部授权真实性已经核实'],
      ['database_catalog', null, [], '本次 API 未返回城市条目'],
    ] as const) {
      fetch.mockImplementation(responses({ ...cities, data, meta: { ...cities.meta, sourceType, datasetId } }))
      await wrapper.get('button').trigger('click'); await flushPromises()
      expect(wrapper.get('.data-notice').text()).toContain(expected)
      expect(wrapper.get('.data-notice').text()).not.toContain('synthetic_test')
    }
  })
  it('shows HTTP failure and restores success after retry', async () => {
    const fetch = vi.fn().mockImplementation(() => Promise.resolve(json({}, 503)))
    vi.stubGlobal('fetch', fetch)
    const wrapper = start(); await flushPromises()
    expect(wrapper.text()).toContain('服务暂不可用')
    expect(wrapper.text()).toContain('HTTP 503')
    fetch.mockImplementation(responses())
    await wrapper.get('button').trigger('click'); await flushPromises()
    expect(wrapper.text()).toContain('服务正常')
    expect(wrapper.find('select').exists()).toBe(true)
  })
  it('removes stale health and cities when a later request fails over the network', async () => {
    const fetch = responses(); vi.stubGlobal('fetch', fetch)
    const wrapper = start(); await flushPromises()
    await wrapper.get('select').setValue('sample-beijing')
    fetch.mockRejectedValue(new TypeError('offline'))
    await wrapper.get('button').trigger('click'); await flushPromises()
    expect(wrapper.text()).not.toContain('服务正常')
    expect(wrapper.text()).toContain('无法连接服务')
    expect(wrapper.text()).toContain('城市列表获取失败')
    expect(wrapper.find('select').exists()).toBe(false)
    expect(wrapper.get('.data-notice').text()).toContain('暂无法确认数据来源')
    expect(wrapper.get('.data-notice').text()).not.toContain('synthetic_test')
  })
  it('detects a stopped backend on the 15-second automatic check', async () => {
    vi.useFakeTimers()
    const fetch = responses(); vi.stubGlobal('fetch', fetch)
    const wrapper = start(); await flushPromises()
    expect(wrapper.text()).toContain('服务正常')
    fetch.mockRejectedValue(new TypeError('connection refused'))
    await vi.advanceTimersByTimeAsync(15_000); await flushPromises()
    expect(wrapper.text()).toContain('服务暂不可用')
    expect(wrapper.text()).not.toContain('服务正常')
  })
})
