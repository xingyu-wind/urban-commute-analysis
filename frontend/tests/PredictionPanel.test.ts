import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, expect, it, vi } from 'vitest'
import PredictionPanel from '../src/components/PredictionPanel.vue'
import { getPredictions } from '../src/api/prediction'
import fixture from '../../contracts/examples/predictions-success.json'
import type { PredictionResponse } from '../src/types/prediction'
vi.mock('../src/components/TrafficChart.vue', () => ({ default: { name: 'TrafficChart', props: ['option', 'label'], template: '<div class="test-chart" />' } }))
vi.mock('../src/api/prediction', () => ({ getPredictions: vi.fn() }))
const empty = (): PredictionResponse => ({ code: 'OK', message: 'Success',
  meta: { requestId: '00112233-4455-6677-8899-aabbccddeeff', dataAsOf: null, sourceType: 'synthetic_test', datasetId: 'synthetic' },
  data: { release: null, history: [], predictions: [], evaluations: [] } })
afterEach(() => vi.resetAllMocks())
it('shows no model with explicit source and no chart', async () => {
  vi.mocked(getPredictions).mockResolvedValue(empty())
  const wrapper = mount(PredictionPanel, { props: { cityId: 'city' } })
  await flushPromises()
  expect(wrapper.text()).toContain('暂无已发布模型')
  expect(wrapper.text()).toContain('synthetic_test')
  expect(wrapper.find('.traffic-chart').exists()).toBe(false)
  wrapper.unmount()
})
it('shows failure and allows retry to an explicit empty result', async () => {
  vi.mocked(getPredictions).mockRejectedValueOnce(new Error('样本覆盖不足')).mockResolvedValueOnce(empty())
  const wrapper = mount(PredictionPanel, { props: { cityId: 'city' } })
  await flushPromises()
  expect(wrapper.get('[role="alert"]').text()).toContain('样本覆盖不足')
  await wrapper.get('form').trigger('submit'); await flushPromises()
  expect(wrapper.find('[role="alert"]').exists()).toBe(false)
  expect(wrapper.text()).toContain('暂无已发布模型')
  wrapper.unmount()
})
it('discards an older city response arriving after the new city', async () => {
  let resolveOld: (value: PredictionResponse) => void = () => {}
  vi.mocked(getPredictions).mockReturnValueOnce(new Promise(resolve => { resolveOld = resolve })).mockResolvedValueOnce(empty())
  const wrapper = mount(PredictionPanel, { props: { cityId: 'old-city' } })
  await wrapper.setProps({ cityId: 'new-city' }); await flushPromises()
  const stale = empty(); stale.meta.datasetId = 'stale-dataset'; resolveOld(stale)
  await flushPromises()
  expect(wrapper.text()).not.toContain('stale-dataset')
  expect(getPredictions).toHaveBeenLastCalledWith('new-city', '')
  wrapper.unmount()
})

it('sends the exact published 28 historical and seven forecast values to ECharts with separate series', async () => {
  const response = structuredClone(fixture) as PredictionResponse
  vi.mocked(getPredictions).mockResolvedValue(response)
  const wrapper = mount(PredictionPanel, { props: { cityId: 'city', datasetId: response.meta.datasetId } })
  await flushPromises()
  const option = wrapper.findComponent({ name: 'TrafficChart' }).props('option')
  expect(option.xAxis.data).toEqual([...response.data.history, ...response.data.predictions].map(p => p.date))
  expect(option.series[0].data).toEqual([...response.data.history.map(p => p.value), ...Array(7).fill(null)])
  expect(option.series[1].data).toEqual([...Array(28).fill(null), ...response.data.predictions.map(p => p.value)])
  expect(option.series[1].lineStyle.type).toBe('dashed')
  expect(wrapper.findAll('[data-testid="prediction-points"] tbody tr').map(r => r.text())).toEqual(response.data.predictions.map(p => p.date + p.value.toFixed(6)))
  expect(wrapper.get('.model-details').attributes('open')).toBeUndefined()
  expect(getPredictions).toHaveBeenLastCalledWith('city', response.meta.datasetId)
  await wrapper.setProps({ datasetId: 'another-dataset' }); await flushPromises()
  expect(getPredictions).toHaveBeenLastCalledWith('city', 'another-dataset')
  wrapper.unmount()
})
