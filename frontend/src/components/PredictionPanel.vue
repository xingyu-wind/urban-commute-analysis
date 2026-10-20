<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { getPredictions } from '../api/prediction'
import type { PredictionResponse } from '../types/prediction'
import TrafficChart from './TrafficChart.vue'
const props = defineProps<{ cityId: string }>()
const result = ref<PredictionResponse | null>(null), error = ref(''), busy = ref(false), dataset = ref('')
let generation = 0
async function load() {
  const g = ++generation
  result.value = null; error.value = ''; busy.value = true
  try { const r = await getPredictions(props.cityId, dataset.value); if (g === generation) result.value = r }
  catch (e) { if (g === generation) error.value = e instanceof Error ? e.message : '预测查询失败' }
  finally { if (g === generation) busy.value = false }
}
watch(() => props.cityId, () => { dataset.value = ''; void load() }, { immediate: true })
onUnmounted(() => { generation++ })
const option = computed(() => {
  const h = result.value?.data.history ?? [], p = result.value?.data.predictions ?? []
  return { animation: false, aria: { enabled: true }, tooltip: { trigger: 'axis' },
    legend: { top: 0, data: ['历史实际观测', '未来七日预测'], textStyle: { color: '#b6cde3' } },
    grid: { left: 42, right: 18, top: 45, bottom: 65 },
    xAxis: { type: 'category', data: [...h, ...p].map(v => v.date), axisLabel: { color: '#b6cde3', rotate: 30 } },
    yAxis: { type: 'value', min: 0, max: 10, name: '拥堵指数 0–10', nameTextStyle: { color: '#b6cde3' }, axisLabel: { color: '#b6cde3' } },
    series: [{ name: '历史实际观测', type: 'line', connectNulls: false, data: [...h.map(v => v.value), ...p.map(() => null)], lineStyle: { color: '#51b8ed' }, itemStyle: { color: '#51b8ed' } },
      { name: '未来七日预测', type: 'line', connectNulls: false, data: [...h.map(() => null), ...p.map(v => v.value)], lineStyle: { type: 'dashed', color: '#f4bb58' }, itemStyle: { color: '#f4bb58' } }] }
})
</script>
<template>
  <section class="panel prediction-panel" data-testid="prediction-panel" :aria-busy="busy">
    <div class="panel-heading"><span class="panel-number">05</span><h2>未来七日拥堵指数预测</h2></div>
    <p>按 CITY / 单一数据集和版本计算日均拥堵指数（0–10），日期均为 UTC。每天至少四个时段，缺日或覆盖不足时拒绝训练。</p>
    <p>未来七日从数据截止日开始计算；历史快照的截止日可能早于今天。</p>
    <form @submit.prevent="load"><label>预测数据集（留空使用城市登记）<input v-model="dataset" maxlength="64" aria-label="预测数据集" /></label><button class="refresh-button" :disabled="busy">{{ busy ? '查询中…' : '查询预测' }}</button></form>
    <p v-if="busy" role="status">正在读取已发布预测…</p><p v-if="error" role="alert" class="error-message">{{ error }}</p>
    <template v-if="result">
      <p>数据来源：{{ result.meta.sourceType }} / {{ result.meta.datasetId }}</p>
      <p v-if="!result.data.release" role="status">暂无已发布模型或预测；请在离线流程中检查样本量与每日覆盖。</p>
      <template v-else>
        <p class="limitation" data-testid="prediction-limitation">{{ result.data.release.limitation }}</p>
        <dl><dt>模型 / 版本</dt><dd data-testid="prediction-model">{{ result.data.release.modelName }} / {{ result.data.release.modelVersion }}</dd>
          <dt>数据版本 / 输入 SHA-256</dt><dd>{{ result.data.release.datasetVersion }} / {{ result.data.release.inputSha256 }}</dd>
          <dt>训练时间 / 预测生成时间 UTC</dt><dd>{{ result.data.release.trainedAt }} / {{ result.data.release.generatedAt }}</dd>
          <dt>数据截止 UTC（不含此时点） / 最后观测 UTC</dt><dd>{{ result.data.release.dataCutoff }} / {{ result.meta.dataAsOf }}</dd>
          <dt>成功 ETL 批次 / 来源配置 SHA</dt><dd>{{ result.data.release.batchIds.join('、') }} / {{ result.data.release.sourceHashes.join('、') }}</dd>
          <dt>选定模型测试集 MAE / RMSE（指数单位）</dt><dd>{{ result.data.release.metrics.mae.toFixed(4) }} / {{ result.data.release.metrics.rmse.toFixed(4) }}</dd></dl>
        <TrafficChart :option="option" label="UTC 历史实际观测与未来七日预测：蓝色实线为观测，黄色虚线为预测，拥堵指数0至10" />
        <div class="table-scroll"><table data-testid="prediction-points"><thead><tr><th>未来日期 UTC</th><th>预测拥堵指数 0–10</th></tr></thead><tbody><tr v-for="p in result.data.predictions" :key="p.date"><td>{{ p.date }}</td><td>{{ p.value.toFixed(6) }}</td></tr></tbody></table></div>
        <details><summary>验证集选模与独立测试集比较（四个七日窗口）</summary><div class="table-scroll"><table><thead><tr><th>切分</th><th>模型</th><th>MAE</th><th>RMSE</th></tr></thead><tbody><tr v-for="e in result.data.evaluations" :key="e.split + e.modelName"><td>{{ e.split }}</td><td>{{ e.modelName }}</td><td>{{ e.mae.toFixed(4) }}</td><td>{{ e.rmse.toFixed(4) }}</td></tr></tbody></table></div><p>只用验证集选择模型；机器学习须比最佳基线 MAE 改善至少 1%，否则采用基线。测试集不用于调参。</p></details>
      </template>
    </template>
  </section>
</template>
<style scoped>
.prediction-panel { margin-top:24px; padding:24px; min-width:0; background:#0d1c2c; color:#e4edf6; border-color:#293e54 }
p,dt { font-size:13px; line-height:1.8; color:#b6cde3 } .limitation { padding:12px; border:1px solid #dca844; color:#f4cf88 }
form { display:flex; gap:16px; flex-wrap:wrap; align-items:end } label { display:grid; gap:8px; font-size:13px } input { padding:10px; background:#132337; color:#e4edf6; border:1px solid #496079; border-radius:6px; max-width:100% }
dd { margin:0 0 12px; overflow-wrap:anywhere; font-size:13px } table { width:100%; border-collapse:collapse; font-size:13px } td,th { padding:10px; text-align:left; border-bottom:1px solid #293e54 } .table-scroll { overflow-x:auto } summary { cursor:pointer; padding:16px 0 }
</style>
