import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, expect, it, vi } from 'vitest'
import PredictionPanel from '../src/components/PredictionPanel.vue'
import { getPredictions } from '../src/api/prediction'
import type { PredictionResponse } from '../src/types/prediction'
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
