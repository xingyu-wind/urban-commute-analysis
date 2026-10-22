<script setup lang="ts">
import { onUnmounted, ref, watch } from 'vue'
import { getWarehouse } from '../api/warehouse'
import { getTraffic } from '../api/traffic'
import type { WarehouseResponse } from '../types/warehouse'

const props = withDefaults(defineProps<{ cityId: string; datasetId?: string }>(), { datasetId: '' })
const dataset = ref(''), result = ref<WarehouseResponse | null>(null), error = ref(''), busy = ref(false)
const comparison = ref<{ sampleCount: number; avgSpeedKmh: number | null; congestionIndex: number | null } | null>(null)
let generation = 0
async function load() {
  const current = ++generation
  result.value = null; comparison.value = null; error.value = ''; busy.value = true
  try {
    const response = await getWarehouse(props.cityId, dataset.value)
    if (current !== generation) return
    result.value = response
    const release = response.data.release
    if (release) {
      const historical = await getTraffic('summary', { cityId: props.cityId, datasetId: response.meta.datasetId ?? undefined,
        from: release.from, to: release.to })
      if (current === generation) comparison.value = historical.data.metrics
    }
  } catch (e) {
    if (current === generation) error.value = e instanceof Error ? e.message : '离线结果请求失败。'
  } finally { if (current === generation) busy.value = false }
}
watch(() => [props.cityId, props.datasetId], () => { dataset.value = props.datasetId; void load() }, { immediate: true })
onUnmounted(() => { generation++ })
const number = (v: number | null | undefined) => v == null ? '—' : v.toFixed(2)
</script>

<template>
  <section class="panel warehouse-panel" aria-labelledby="warehouse-title" :aria-busy="busy" data-testid="warehouse-panel">
    <div class="panel-heading"><span class="panel-number">04</span><h2 id="warehouse-title">Hive 离线分析与比较</h2></div>
    <p class="panel-description">已发布的离线快照 · UTC 半开窗口 [起始, 结束) · 各层级分别统计，样本数为观测条数。</p>
    <form class="warehouse-filter" @submit.prevent="load"><label>数据集（留空使用城市登记）<input v-model="dataset" aria-label="离线数据集" maxlength="64" /></label><button class="refresh-button" :disabled="busy">{{ busy ? '查询中…' : '查询离线结果' }}</button></form>
    <p v-if="error" class="error-message" role="alert">{{ error }}</p>
    <template v-if="result">
      <p>数据来源：<code>{{ result.meta.sourceType }}</code> · <code>{{ result.meta.datasetId }}</code>。合成测试不代表真实交通采集或通勤人数。</p>
      <p v-if="!result.data.release" role="status">当前城市及数据集尚无已发布的 Hive 离线结果。</p>
      <template v-else>
        <details><summary>快照技术详情</summary><dl class="warehouse-provenance">
          <div><dt>最新发布版本</dt><dd data-testid="warehouse-release">{{ result.data.release.id }} / {{ result.data.release.datasetVersion }}</dd></div>
          <div><dt>快照统计范围 UTC</dt><dd>{{ result.data.release.from }} → {{ result.data.release.to }}（不含结束）</dd></div>
          <div><dt>发布时间 UTC</dt><dd>{{ result.data.release.publishedAt }}</dd></div>
          <div><dt>成功 ETL 批次</dt><dd>{{ result.data.release.batchIds.join('、') }}</dd></div>
          <div><dt>ADS SHA-256</dt><dd><code>{{ result.data.release.adsSha256 }}</code></dd></div>
        </dl></details>
        <div class="warehouse-table-scroll"><table class="warehouse-table" data-testid="warehouse-metrics">
          <thead><tr><th>观测层级 / 目标</th><th>样本数</th><th>平均速度 km/h</th><th>拥堵指数 0–10</th><th>观测覆盖 UTC</th></tr></thead>
          <tbody><tr v-for="row in result.data.items" :key="row.targetType + row.targetId"><td>{{ row.targetType }} / {{ row.targetId }}<small v-if="row.roadRegionId">道路目录区域：{{ row.roadRegionId }}</small></td><td>{{ row.sampleCount }}</td><td>{{ number(row.avgSpeedKmh) }}</td><td>{{ number(row.congestionIndex) }}</td><td>{{ row.observedFrom }} → {{ row.observedTo }}</td></tr></tbody>
        </table></div>
        <p v-if="comparison" data-testid="warehouse-comparison">相同窗口的 MySQL 历史观测统计（CITY）：{{ comparison.sampleCount }} 条，均速 {{ number(comparison.avgSpeedKmh) }} km/h，指数 {{ number(comparison.congestionIndex) }}。离线快照保留发布时结果；后续观测提交可能使两者不同。</p>
      </template>
    </template>
  </section>
</template>

<style scoped>
.warehouse-panel { margin-top: 24px; padding: 24px; min-width: 0; background: var(--panel); color: var(--ink); border-color: var(--line); }
.warehouse-filter { display: flex; align-items: end; gap: 16px; flex-wrap: wrap; margin: 20px 0; }
.warehouse-filter label { display: grid; gap: 8px; }
input { background: var(--panel); color: var(--ink); border: 1px solid var(--line); padding: 10px; border-radius: 6px; }
p,dt { color: var(--muted); font-size: 13px; line-height: 1.8; }
.warehouse-provenance div { margin: 8px 0; } dd { margin: 0; overflow-wrap: anywhere; }
.warehouse-table-scroll { overflow-x: auto; } .warehouse-table { width: 100%; border-collapse: collapse; font-size: 13px; }
th,td { text-align: left; padding: 12px; border-bottom: 1px solid var(--line); } th { white-space: nowrap; } td { min-width: 70px; }
small { display: block; margin-top: 6px; color: var(--muted); }
</style>
