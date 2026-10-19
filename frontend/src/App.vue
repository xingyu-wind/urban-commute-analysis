<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { ApiClientError, getCities, getHealth } from './api/client'
import CitySelector from './components/CitySelector.vue'
import type { CitiesResponse, HealthResponse } from './types/api'

const health = ref<HealthResponse | null>(null)
const cities = ref<CitiesResponse | null>(null)
const healthError = ref('')
const citiesError = ref('')
const loading = ref(true)
const selectedId = ref('')
const selectedCity = computed(() => cities.value?.data.find(city => city.id === selectedId.value))
const checkedTime = computed(() => health.value ? new Date(health.value.timestamp).toLocaleString('zh-CN', {
  timeZone: 'Asia/Shanghai', hour12: false,
}) : '—')
let interval: ReturnType<typeof setInterval> | undefined
let disposed = false

function failureMessage(error: unknown): string {
  return error instanceof ApiClientError ? error.message : '请求失败，请稍后重新请求。'
}

async function refresh() {
  if (loading.value && interval !== undefined) return
  loading.value = true
  health.value = null
  cities.value = null
  healthError.value = ''
  citiesError.value = ''
  const [healthResult, citiesResult] = await Promise.allSettled([getHealth(), getCities()])
  if (disposed) return
  if (healthResult.status === 'fulfilled') health.value = healthResult.value
  else healthError.value = failureMessage(healthResult.reason)
  if (citiesResult.status === 'fulfilled') {
    cities.value = citiesResult.value
    if (!cities.value.data.some(city => city.id === selectedId.value)) selectedId.value = ''
  } else {
    citiesError.value = failureMessage(citiesResult.reason)
    selectedId.value = ''
  }
  loading.value = false
}

onMounted(() => {
  void refresh()
  interval = setInterval(() => { if (!loading.value) void refresh() }, 15_000)
})
onUnmounted(() => { disposed = true; clearInterval(interval) })
</script>

<template>
  <div class="app-shell">
    <header class="topbar">
      <div class="brand"><span class="brand-mark" aria-hidden="true"><svg viewBox="0 0 28 28" fill="none"><path d="M7 20V8l7 5 7-5v12M7 8l7-3 7 3M14 13v10" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg></span><span>城市通勤<span class="brand-divider">/</span>数据工作台</span></div>
      <span class="environment"><span class="dot"></span>本地开发环境</span>
    </header>

    <main>
      <section class="page-heading">
        <div><p class="eyebrow">服务与城市</p><h1>城市通勤数据分析及智能预测系统</h1><p class="subtitle">连接后端服务，选择城市。城市列表来自 MySQL；合成测试条目必须明确标注来源，当前没有已核验的真实交通观测。</p></div>
        <button class="refresh-button" :disabled="loading" @click="refresh"><svg :class="{ spinning: loading }" viewBox="0 0 20 20" aria-hidden="true"><path d="M16 8a6.3 6.3 0 1 0 .1 4M16 3v5h-5" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>{{ loading ? '正在请求…' : '重新请求' }}</button>
      </section>

      <div class="workspace-grid">
        <section class="panel service-panel" aria-labelledby="service-title" :aria-busy="loading">
          <div class="panel-heading"><span class="panel-number">01</span><h2 id="service-title">后端服务</h2></div>
          <div class="service-indicator" :class="{ healthy: health, failed: healthError }"><svg viewBox="0 0 30 30" aria-hidden="true"><path d="M5 15h5l3-7 5 14 3-7h4" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg></div>
          <p class="service-status" role="status" data-testid="service-status">{{ loading ? '正在检查服务' : health ? '服务正常' : '服务暂不可用' }}</p>
          <p class="service-caption">{{ loading ? '正在获取最新服务状态' : health ? '健康检查已通过' : '未确认后端可用，请重新请求' }}</p>
          <p v-if="healthError" class="error-message" role="alert">{{ healthError }}</p>
          <div class="service-time"><span>服务检查时间 · 北京时间</span><time :datetime="health?.timestamp">{{ checkedTime }}</time></div>
          <p class="auto-check"><span class="dot"></span>每 15 秒自动检查，也可手动重新请求</p>
        </section>

        <section class="panel city-panel" aria-labelledby="city-title" :aria-busy="loading">
          <div class="panel-heading"><span class="panel-number">02</span><h2 id="city-title">城市选择</h2><span v-if="cities" class="source-badge">{{ cities.meta.sourceType === 'synthetic_test' ? '合成测试' : '数据库目录' }} <code>{{ cities.meta.sourceType }}</code></span></div>
          <p class="panel-description">从后端返回的城市列表中选择，查看当前城市。</p>
          <div v-if="loading" class="state-box loading-state" role="status"><span class="loading-dots">•••</span><p>正在加载城市列表…</p></div>
          <div v-else-if="citiesError" class="state-box error-state" role="alert"><strong>城市列表获取失败</strong><p>{{ citiesError }}</p><span>点击右上角“重新请求”再次连接。</span></div>
          <div v-else-if="cities && cities.data.length === 0" class="state-box empty-state" role="status"><strong>暂无可选城市</strong><p>服务已正常响应，但当前城市列表为空。</p><span>数据库查询返回空数组，未将空列表视为错误。</span></div>
          <template v-else-if="cities">
            <CitySelector v-model="selectedId" :cities="cities.data" />
            <div class="selected-city" aria-live="polite"><span class="selection-icon" aria-hidden="true">⌖</span><div><span class="field-caption">当前选择</span><strong data-testid="selected-city">{{ selectedCity?.name ?? '尚未选择城市' }}</strong></div><span class="selection-tag">{{ selectedCity ? '已选择' : '待选择' }}</span></div>
          </template>
          <div v-if="cities" class="dataset-info"><div><span>数据集</span><code>{{ cities.meta.datasetId ?? '—（空目录或混合来源）' }}</code></div><div><span>数据采集时间</span><span>不适用（城市目录非交通观测）</span></div></div>
        </section>
      </div>

      <aside class="data-notice"><span class="notice-icon" aria-hidden="true">i</span><div><strong>数据来源说明</strong><p>测试环境里的北京、上海条目属于 synthetic_test 合成测试城市目录，不能证明真实交通采集。当前不提供交通统计或预测结果。</p></div></aside>
      <footer><span>城市通勤 · 以明确的数据来源为基础</span><span>健康状态与城市列表均来自后端请求</span></footer>
    </main>
  </div>
</template>
