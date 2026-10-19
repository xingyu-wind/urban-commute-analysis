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
const sourceLabels = {
  database_catalog: '空数据库目录', mixed_catalog: '混合来源目录', dev_seed: '开发样例',
  synthetic_test: '合成测试', historical_snapshot: '历史快照登记',
  authorized_live: '授权来源登记', simulation: '模拟数据', mock: '模拟接口', forecast: '预测数据',
}
const sourceDescriptions: Record<CitiesResponse['meta']['sourceType'], string> = {
  database_catalog: '数据库城市目录本身不证明存在真实交通观测，也不能证明外部授权真实性。',
  mixed_catalog: '本次城市目录包含多个数据集，不能统一归为合成测试或真实观测；仅凭该目录不能确定单个城市的来源或授权真实性。',
  dev_seed: '本次城市目录登记为 dev_seed 开发样例，用于开发交互验证，不代表真实交通观测。',
  synthetic_test: '本次城市目录登记为 synthetic_test 合成测试数据，不代表真实交通采集，也不能据此推断通勤人数或交通状态。',
  historical_snapshot: '本次城市目录登记为 historical_snapshot 历史快照。来源及授权状态仅为数据库登记，不表示外部授权真实性已经核实，也不表示实时交通观测。',
  authorized_live: '本次城市目录登记为 authorized_live 授权来源。来源及授权状态仅为数据库登记，不表示外部授权真实性已经核实，也不能仅凭城市目录证明实时交通采集。',
  simulation: '本次城市目录登记为 simulation 模拟数据，不代表真实交通观测。',
  mock: '本次城市目录登记为 mock 模拟接口数据，不代表真实交通观测。',
  forecast: '本次城市目录登记为 forecast 预测来源，不代表已经发生的交通观测，也不表示本页面已提供交通预测结果。',
}
const sourceDescription = computed(() => {
  if (!cities.value) return loading.value
    ? '正在获取城市目录，数据来源尚未确认。'
    : '未取得有效城市目录响应，暂无法确认数据来源。'
  if (cities.value.data.length === 0) return '本次 API 未返回城市条目；空目录不能证明存在合成样例、真实交通观测或已核实的外部授权。'
  return sourceDescriptions[cities.value.meta.sourceType]
})
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
          <div class="panel-heading"><span class="panel-number">02</span><h2 id="city-title">城市选择</h2><span v-if="cities" class="source-badge">{{ sourceLabels[cities.meta.sourceType] }} <code>{{ cities.meta.sourceType }}</code></span></div>
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

      <aside class="data-notice"><span class="notice-icon" aria-hidden="true">i</span><div><strong>数据来源说明</strong><p>{{ sourceDescription }}</p></div></aside>
      <footer><span>城市通勤 · 以明确的数据来源为基础</span><span>健康状态与城市列表均来自后端请求</span></footer>
    </main>
  </div>
</template>
