<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { getCities, getHealth } from './api/client'
import { getAvailability, statusLabel, type Availability } from './api/availability'
import TrafficDashboard from './components/TrafficDashboard.vue'
import WarehousePanel from './components/WarehousePanel.vue'
import PredictionPanel from './components/PredictionPanel.vue'
import OperationsPanel from './components/OperationsPanel.vue'
import type { CitiesResponse } from './types/api'

type Page = 'overview' | 'traffic' | 'prediction' | 'management' | 'screen'
const pages: { id: Page; label: string; icon: string; caption: string }[] = [
  { id: 'overview', label: '总览首页', icon: '◫', caption: '从城市交通出发，读懂每一次出行。' },
  { id: 'traffic', label: '交通分析', icon: '↗', caption: '按时段探索趋势，比较区域与道路观测。' },
  { id: 'prediction', label: '智能预测', icon: '⌁', caption: '以历史观测为依据，查看已发布的未来七日预测。' },
  { id: 'management', label: '数据管理', icon: '▤', caption: '管理研究数据、映射确认与任务执行状态。' },
  { id: 'screen', label: '全屏大屏', icon: '⛶', caption: '城市通勤态势 / URBAN MOBILITY' },
]
const readPage = (): Page => pages.find(p => p.id === location.hash.slice(1))?.id ?? 'overview'
const active = ref<Page>(readPage()), heading = computed(() => pages.find(p => p.id === active.value)!)
const cities = ref<CitiesResponse | null>(null), availability = ref<Record<string, Availability>>({})
const selectedId = ref(''), datasetId = ref(''), loading = ref(true), error = ref(''), metadataErrors = ref<Record<string, string>>({})
const service = ref('正在检查服务'), warehouseVisible = ref(false), fullscreenError = ref('')
const city = computed(() => cities.value?.data.find(c => c.id === selectedId.value))
const catalog = computed(() => availability.value[selectedId.value])
const dataset = computed(() => catalog.value?.datasets.find(d => d.datasetId === datasetId.value))
const sourceLabels: Record<string, string> = { synthetic_test: '合成演示数据', dev_seed: '目录示例', historical_snapshot: '历史快照登记', authorized_live: '授权来源登记' }
let generation = 0, disposed = false, interval: ReturnType<typeof setInterval> | undefined
function selectCity(id: string) {
  selectedId.value = id
  const a = availability.value[id]
  const preferred = a?.datasets.find(d => d.datasetId === a.defaultDatasetId)
  datasetId.value = (preferred && (Object.values(preferred.levels).some(r => r.sampleCount) || preferred.predictionAvailable)
    ? preferred : a?.datasets.find(d => Object.values(d.levels).some(r => r.sampleCount) || d.predictionAvailable) ?? preferred)?.datasetId ?? ''
}
async function checkHealth() {
  try { await getHealth(); if (!disposed) service.value = '服务正常' }
  catch { if (!disposed) service.value = '服务暂不可用' }
}
async function refresh() {
  const g = ++generation
  loading.value = true; error.value = ''; metadataErrors.value = {}; availability.value = {}
  void checkHealth()
  try {
    const response = await getCities()
    if (disposed || g !== generation) return
    cities.value = response
    const results = await Promise.allSettled(response.data.map(c => getAvailability(c.id)))
    if (disposed || g !== generation) return
    const ranges: Record<string, Availability> = {}, failures: Record<string, string> = {}
    results.forEach((r, i) => {
      const id = response.data[i]!.id
      if (r.status === 'fulfilled') ranges[id] = r.value
      else failures[id] = r.reason instanceof Error ? r.reason.message : '数据范围读取失败'
    })
    availability.value = ranges; metadataErrors.value = failures
    const preferred = response.data.find(c => ranges[c.id]?.datasets.some(d => d.predictionAvailable || Object.values(d.levels).some(r => r.sampleCount)))
    const id = response.data.some(c => c.id === selectedId.value) ? selectedId.value : preferred?.id ?? response.data[0]?.id ?? ''
    const previousDataset = datasetId.value
    selectCity(id)
    if (ranges[id]?.datasets.some(d => d.datasetId === previousDataset)) datasetId.value = previousDataset
  } catch (e) {
    if (disposed || g !== generation) return
    error.value = e instanceof Error ? e.message : '城市列表获取失败'
    cities.value = null; selectedId.value = ''; datasetId.value = ''
  } finally { if (!disposed && g === generation) loading.value = false }
}
function navigate(id: Page) { active.value = id; location.hash = id; window.scrollTo({ top: 0, behavior: 'instant' }) }
function hashChanged() { active.value = readPage() }
async function fullscreen() {
  fullscreenError.value = ''
  try { if (document.fullscreenElement) await document.exitFullscreen(); else await document.documentElement.requestFullscreen() }
  catch { fullscreenError.value = '浏览器未允许全屏，仍可使用当前大屏视图。' }
}
onMounted(() => { void refresh(); interval = setInterval(() => { void checkHealth() }, 15000); window.addEventListener('hashchange', hashChanged) })
onUnmounted(() => { disposed = true; generation++; clearInterval(interval); window.removeEventListener('hashchange', hashChanged) })
</script>

<template>
  <div class="workbench" :class="{ 'screen-mode': active === 'screen' }">
    <aside class="sidebar">
      <a class="brand" href="#overview" @click.prevent="navigate('overview')"><span class="brand-mark">M</span><span>城市通勤<small>URBAN MOBILITY</small></span></a>
      <p class="nav-caption">分析工作台</p>
      <nav aria-label="主要功能"><button v-for="p in pages" :key="p.id" :class="{ active: active === p.id }" :aria-current="active === p.id ? 'page' : undefined" @click="navigate(p.id)"><span aria-hidden="true">{{ p.icon }}</span>{{ p.label }}<span v-if="active === p.id" class="nav-dot" /></button></nav>
      <div class="sidebar-note"><span class="dot" /> 让数据连接城市<p>观测 · 分析 · 预测</p></div>
    </aside>
    <div class="workspace-body">
      <header class="topbar"><span>城市通勤数据分析及智能预测系统</span><div class="topbar-actions"><span class="service-status" data-testid="service-status" :class="{ failed: service === '服务暂不可用' }" role="status"><span class="dot" />{{ service }}</span><button :disabled="loading" @click="refresh">{{ loading ? '正在加载…' : '刷新数据' }}</button><button v-if="active === 'screen'" @click="fullscreen">全屏 / 退出</button></div></header>
      <main>
        <section class="page-heading"><div><p class="eyebrow">{{ active === 'screen' ? 'CITY INTELLIGENCE / DATA SCREEN' : 'CITY INTELLIGENCE / WORKSPACE' }}</p><h1>{{ heading.label === '全屏大屏' ? '城市通勤态势总览' : heading.label }}</h1><p class="subtitle">{{ heading.caption }}</p></div><span v-if="dataset" class="source-badge">{{ sourceLabels[dataset.sourceType] ?? dataset.sourceType }}</span></section>
        <p v-if="fullscreenError" role="status">{{ fullscreenError }}</p>
        <section v-if="active !== 'management'" class="context-bar" aria-label="分析条件">
          <label>分析城市<select :value="selectedId" aria-label="城市选择" :disabled="loading || !cities?.data.length" @change="selectCity(($event.target as HTMLSelectElement).value)"><option v-if="!cities?.data.length" value="">{{ loading ? '正在加载城市列表…' : '暂无可选城市' }}</option><option v-for="c in cities?.data" :key="c.id" :value="c.id">{{ c.name }} · {{ availability[c.id] ? statusLabel(availability[c.id]!.datasets) : metadataErrors[c.id] ? '范围读取失败' : '读取中' }}</option></select></label>
          <label>关联数据集<select v-model="datasetId" aria-label="数据集选择" :disabled="loading || !catalog"><option v-for="d in catalog?.datasets" :key="d.datasetId" :value="d.datasetId">{{ d.datasetId }} · {{ statusLabel([d]) }}</option></select></label>
          <div class="context-summary"><span>当前分析范围</span><strong data-testid="selected-city">{{ city?.name ?? '等待城市目录' }}</strong><small v-if="dataset">{{ statusLabel([dataset]) }} · UTC</small></div>
        </section>
        <div v-if="active !== 'management' && loading" class="state-box" role="status">正在读取城市及有效观测范围…</div>
        <div v-else-if="active !== 'management' && (error || metadataErrors[selectedId])" class="state-box error-state" role="alert"><strong>数据连接暂不可用</strong><p>{{ error || metadataErrors[selectedId] }}</p><button @click="refresh">重试连接</button></div>
        <div v-else-if="active !== 'management' && !dataset" class="state-box" role="status">暂无可分析数据，请刷新城市目录。</div>
        <template v-if="dataset && city && !loading && !error">
          <TrafficDashboard v-show="['overview', 'traffic', 'screen'].includes(active)" :key="selectedId + '/' + datasetId" :city-id="selectedId" :city-name="city.name" :availability="dataset" :view="active === 'traffic' ? 'analysis' : active === 'screen' ? 'screen' : 'overview'" />
          <div v-if="active === 'overview'" class="section-link"><span>从历史走向未来</span><button @click="navigate('prediction')">查看完整预测 →</button><button @click="navigate('traffic')">深入交通分析 →</button></div>
          <PredictionPanel v-show="['overview', 'prediction', 'screen'].includes(active)" :key="'prediction/' + selectedId + '/' + datasetId" :city-id="selectedId" :dataset-id="datasetId" :compact="active !== 'prediction'" />
          <section v-if="active === 'traffic'" class="warehouse-entry"><button :aria-expanded="warehouseVisible" @click="warehouseVisible = !warehouseVisible">{{ warehouseVisible ? '收起数仓快照' : '查看 Hive 数仓快照与同窗比较' }}</button><WarehousePanel v-if="warehouseVisible" :city-id="selectedId" :dataset-id="datasetId" /></section>
        </template>
        <OperationsPanel v-if="active === 'management'" />
        <details v-if="dataset && active !== 'management' && active !== 'screen'" class="data-details"><summary>数据详情与使用边界</summary><p>{{ sourceLabels[dataset.sourceType] }}（{{ dataset.sourceType }}）· {{ dataset.datasetId }}。来源及许可状态仅为数据库登记，不表示外部授权真实性已经核实。合成演示不能用于判断真实交通准确率。</p><p>CITY、REGION、ROAD 独立统计；样本数量为观测条数。日期使用 UTC，结束日期不包含当日；预测窗口由已发布模型的数据截止日决定。</p><dl><template v-for="(range, level) in dataset.levels" :key="level"><dt>{{ level }} · {{ range.sampleCount }} 条</dt><dd>{{ range.firstObservedAt ?? '无观测' }} → {{ range.lastObservedAt ?? '无观测' }}</dd></template></dl></details>
        <footer><span>城市通勤 · 数据驱动出行洞察</span><span>统计与预测来自已发布数据</span></footer>
      </main>
    </div>
  </div>
</template>
