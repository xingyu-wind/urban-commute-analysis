<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { getPredictions } from '../api/prediction'
import type { PredictionResponse } from '../types/prediction'
import TrafficChart from './TrafficChart.vue'
const props = withDefaults(defineProps<{ cityId: string; datasetId?: string; compact?: boolean }>(), { datasetId: '', compact: false })
const result = ref<PredictionResponse | null>(null), error = ref(''), busy = ref(false)
let generation = 0
async function load() {
  const g = ++generation
  result.value = null; error.value = ''; busy.value = true
  try { const r = await getPredictions(props.cityId, props.datasetId); if (g === generation) result.value = r }
  catch (e) { if (g === generation) error.value = e instanceof Error ? e.message : '预测查询失败' }
  finally { if (g === generation) busy.value = false }
}
watch(() => [props.cityId, props.datasetId], () => { void load() }, { immediate: true })
onUnmounted(() => { generation++ })
const release = computed(() => result.value?.data.release)
const option = computed(() => {
  const h = result.value?.data.history ?? [], p = result.value?.data.predictions ?? []
  return { animation: false, aria: { enabled: true }, tooltip: { trigger: 'axis', confine: true, renderMode: 'richText' },
    color: ['#2563eb', '#E8A34B'],
    legend: { top: 0, data: ['历史实际观测', '未来七日预测'], textStyle: { color: '#71859e' } },
    grid: { left: 45, right: 24, top: 50, bottom: 65 },
    dataZoom: [{ type: 'inside' }, { type: 'slider', height: 16, bottom: 6, textStyle: { color: '#71859e' } }],
    xAxis: { type: 'category', data: [...h, ...p].map(v => v.date), axisLabel: { color: '#71859e', formatter: (v: string) => v.slice(5) } },
    yAxis: { type: 'value', min: 0, max: 10, name: '拥堵指数 0–10', nameTextStyle: { color: '#71859e' }, axisLabel: { color: '#71859e' }, splitLine: { lineStyle: { color: '#94a3b833' } } },
    series: [{ name: '历史实际观测', type: 'line', connectNulls: false, symbolSize: 5, data: [...h.map(v => v.value), ...p.map(() => null)], lineStyle: { width: 2 }, areaStyle: { opacity: 0.05 } },
      { name: '未来七日预测', type: 'line', connectNulls: false, symbolSize: 6, data: [...h.map(() => null), ...p.map(v => v.value)], lineStyle: { type: 'dashed', width: 3 } }] }
})
</script>
<template>
  <section class="panel prediction-panel" :class="{ compact }" data-testid="prediction-panel" :aria-busy="busy">
    <div class="prediction-heading"><div><p class="eyebrow">NEXT 7 DAYS / FORECAST</p><h2>七日拥堵预测</h2></div><form @submit.prevent="load"><button :disabled="busy">{{ busy ? '查询中…' : '刷新预测' }}</button></form></div>
    <p v-if="busy" class="state-box" role="status">正在读取已发布预测…</p>
    <div v-else-if="error" role="alert" class="state-box error-state"><p>{{ error }}</p><button @click="load">重试预测</button></div>
    <template v-else-if="result">
      <div class="prediction-context"><span>{{ result.meta.datasetId }}</span><span>{{ result.meta.sourceType === 'synthetic_test' ? '合成演示数据' : '登记数据' }} · {{ result.meta.sourceType }}</span><span v-if="release">依据最后观测 {{ result.meta.dataAsOf }} · UTC</span></div>
      <div v-if="!release" class="chart-empty" role="status">暂无已发布模型或预测<p>此数据集尚未完成预测发布，可继续查看已有交通统计。</p></div>
      <template v-else>
        <div class="model-summary"><span data-testid="prediction-model">选定模型 <strong>{{ release.modelName }}</strong></span><span>MAE <strong>{{ release.metrics.mae.toFixed(4) }}</strong></span><span>RMSE <strong>{{ release.metrics.rmse.toFixed(4) }}</strong></span><span>预测起点 <strong>{{ release.dataCutoff.slice(0, 10) }}</strong> UTC</span></div>
        <div class="prediction-content"><div v-if="!compact" class="forecast-chart"><TrafficChart :option="option" label="UTC 历史实际观测与未来七日预测；蓝色实线为观测，橙色虚线为预测，拥堵指数0至10" /></div>
          <table data-testid="prediction-points" class="prediction-points"><thead><tr><th>预测日期 UTC</th><th>拥堵指数 / 10</th></tr></thead><tbody><tr v-for="p in result.data.predictions" :key="p.date"><td>{{ p.date }}</td><td>{{ p.value.toFixed(6) }}</td></tr></tbody></table></div>
        <p class="prediction-limitation" data-testid="prediction-limitation">{{ release.limitation }}</p>
        <details v-if="!compact" class="model-details"><summary>模型详情 · 版本、输入与回测</summary>
          <dl><dt>完整模型版本</dt><dd>{{ release.modelVersion }}</dd><dt>数据版本 / 输入 SHA-256</dt><dd>{{ release.datasetVersion }} / {{ release.inputSha256 }}</dd>
          <dt>训练时间 / 预测生成时间 UTC</dt><dd>{{ release.trainedAt }} / {{ release.generatedAt }}</dd>
          <dt>数据截止 UTC（不含此时点）</dt><dd>{{ release.dataCutoff }}</dd>
          <dt>成功 ETL 批次 / 来源配置 SHA</dt><dd>{{ release.batchIds.join('、') }} / {{ release.sourceHashes.join('、') }}</dd></dl>
          <p>预测结果来自既有 MySQL 发布版本。每天至少四个时段，缺日或覆盖不足拒绝训练。仅用验证集选模，测试集不参与调参；合成误差不能解释为真实交通准确率。运行依赖固定于 ml/requirements.lock.txt，完整版本随离线包提供。</p>
          <div class="table-scroll"><table><thead><tr><th>切分</th><th>模型</th><th>MAE</th><th>RMSE</th></tr></thead><tbody><tr v-for="e in result.data.evaluations" :key="e.split + e.modelName"><td>{{ e.split }}</td><td>{{ e.modelName }}</td><td>{{ e.mae.toFixed(4) }}</td><td>{{ e.rmse.toFixed(4) }}</td></tr></tbody></table></div>
        </details>
      </template>
    </template>
  </section>
</template>
