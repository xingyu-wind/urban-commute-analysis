<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { getTraffic } from '../api/traffic'
import { ApiClientError } from '../api/client'
import type { TrafficFilter, TrafficResponse } from '../types/traffic'
import TrafficChart from './TrafficChart.vue'

const props = defineProps<{ cityId: string; cityName: string }>()
const day = (offset: number) => new Date(Date.now() + offset * 86400000).toISOString().slice(0, 10)
const from = ref(day(-2)), to = ref(day(0)), dataset = ref(''), granularity = ref('day')
const region = ref(''), search = ref(''), page = ref(1), pageSize = ref(10)
const summary = ref<TrafficResponse<'summary'> | null>(null)
const series = ref<TrafficResponse<'series'> | null>(null)
const regions = ref<TrafficResponse<'regions'> | null>(null)
const roads = ref<TrafficResponse<'roads'> | null>(null)
const busy = ref(false), error = ref(''), presentation = ref(false)
let version = 0
const number = (v: number | null | undefined) => v == null ? '—' : v.toFixed(2)
const metrics = computed(() => summary.value?.data.metrics)
const points = computed(() => regions.value?.data.items.filter(r => r.coordinateSystem === 'WGS84' && r.latitude !== null && r.longitude !== null) ?? [])
const missing = computed(() => (regions.value?.data.items.length ?? 0) - points.value.length)
const selectedRegion = computed(() => regions.value?.data.items.find(r => r.id === region.value))
const pageCount = computed(() => Math.max(1, Math.ceil((roads.value?.data.total ?? 0) / pageSize.value)))
const empty = computed(() => metrics.value?.sampleCount === 0)
const sparse = computed(() => series.value?.data.items.some(r => r.metrics.sampleCount === 0) || (metrics.value?.sampleCount ?? 0) < 5)
const provenance = computed(() => summary.value?.meta)
const common = { animation: false, backgroundColor: 'transparent', textStyle: { color: '#91a5be', fontFamily: 'Segoe UI, Microsoft YaHei, sans-serif' },
  tooltip: { trigger: 'axis', renderMode: 'richText', confine: true }, aria: { enabled: true },
  grid: { left: 48, right: 48, top: 45, bottom: 65 } }
const axis = { axisLine: { lineStyle: { color: '#293e54' } }, axisTick: { show: false }, splitLine: { lineStyle: { color: '#1e3044', type: 'dashed' } } }
const trendOption = computed(() => ({ ...common, color: ['#48d9bf', '#ffbd72'],
  legend: { textStyle: { color: '#aabdd0' }, top: 5, data: ['平均速度 km/h', '拥堵指数 0–10'] },
  xAxis: { ...axis, type: 'category', data: series.value?.data.items.map(r => r.bucket.slice(5, granularity.value === 'day' ? 10 : 16).replace('T', ' ')) ?? [] },
  yAxis: [{ ...axis, type: 'value', name: 'km/h', min: 0 }, { ...axis, type: 'value', name: '指数', min: 0, max: 10 }],
  dataZoom: [{ type: 'inside' }, { type: 'slider', bottom: 8, height: 18, borderColor: '#293e54', textStyle: { color: '#91a5be' } }],
  series: [{ name: '平均速度 km/h', type: 'line', connectNulls: false, symbolSize: 8, data: series.value?.data.items.map(r => r.metrics.avgSpeedKmh) ?? [], lineStyle: { width: 3 }, areaStyle: { opacity: 0.08 } },
    { name: '拥堵指数 0–10', type: 'line', yAxisIndex: 1, connectNulls: false, symbolSize: 7, data: series.value?.data.items.map(r => r.metrics.congestionIndex) ?? [] }] }))
const regionOption = computed(() => ({ ...common, grid: { left: 100, right: 35, top: 15, bottom: 30 },
  tooltip: { trigger: 'item', renderMode: 'richText', confine: true },
  xAxis: { ...axis, type: 'value', min: 0, max: 10 },
  yAxis: { ...axis, type: 'category', inverse: true, data: regions.value?.data.items.map(r => r.name) ?? [] },
  series: [{ type: 'bar', barMaxWidth: 28, data: regions.value?.data.items.map(r => ({ id: r.id, value: r.metrics.congestionIndex, itemStyle: { color: r.id === region.value ? '#ffbd72' : '#48cdb8', borderRadius: [0, 5, 5, 0] } })) ?? [] }] }))
const mapOption = computed(() => ({ ...common, grid: { left: 65, right: 45, top: 35, bottom: 55 },
  tooltip: { trigger: 'item', renderMode: 'richText', confine: true },
  xAxis: { ...axis, type: 'value', name: '经度 °E', min: points.value.length ? Math.max(-180, Math.min(...points.value.map(r => r.longitude!)) - 0.06) : -180,
    max: points.value.length ? Math.min(180, Math.max(...points.value.map(r => r.longitude!)) + 0.06) : 180, axisLabel: { formatter: (v: number) => v.toFixed(3) } },
  yAxis: { ...axis, type: 'value', name: '纬度 °N', min: points.value.length ? Math.max(-90, Math.min(...points.value.map(r => r.latitude!)) - 0.04) : -90,
    max: points.value.length ? Math.min(90, Math.max(...points.value.map(r => r.latitude!)) + 0.04) : 90, axisLabel: { formatter: (v: number) => v.toFixed(3) } },
  dataZoom: [{ type: 'inside', xAxisIndex: 0, filterMode: 'none' }, { type: 'inside', yAxisIndex: 0, filterMode: 'none' }],
  series: [{ type: 'scatter', symbolSize: 22, label: { show: true, position: 'top', formatter: '{b}', color: '#d3e5f7', distance: 15 },
    data: points.value.map(r => ({ id: r.id, name: r.name, value: [r.longitude, r.latitude, r.metrics.congestionIndex],
      itemStyle: { color: r.id === region.value ? '#ffbd72' : '#48d9bf', borderColor: '#9af1e0', borderWidth: 2, shadowBlur: 18, shadowColor: '#48d9bf66' } })) }] }))

async function load() {
  const current = ++version
  busy.value = true; error.value = ''
  summary.value = null; series.value = null; regions.value = null; roads.value = null
  try {
    if (!from.value || !to.value || from.value >= to.value) throw new Error('请选择有效的 UTC 起止日期，结束日期必须晚于开始日期。')
    const filter: TrafficFilter = { cityId: props.cityId, from: `${from.value}T00:00:00Z`, to: `${to.value}T00:00:00Z` }
    if (dataset.value.trim()) filter.datasetId = dataset.value.trim()
    const [a, b, c, d] = await Promise.all([getTraffic('summary', filter), getTraffic('series', filter, { granularity: granularity.value }),
      getTraffic('regions', filter), getTraffic('roads', filter, { page: String(page.value), pageSize: String(pageSize.value),
        ...(region.value ? { regionId: region.value } : {}), ...(search.value ? { search: search.value } : {}) })])
    if (current !== version) return
    if ([b, c, d].some(r => r.meta.datasetId !== a.meta.datasetId)) throw new Error('数据集登记发生变化，请刷新分析。')
    summary.value = a; series.value = b; regions.value = c; roads.value = d
  } catch (e) {
    if (current !== version) return
    error.value = e instanceof Error ? e.message : '统计请求失败。'
    if (e instanceof ApiClientError && e.requestId) error.value += ` 请求 ID：${e.requestId}`
  } finally { if (current === version) busy.value = false }
}
function selectRegion(id: string) { region.value = region.value === id ? '' : id; page.value = 1 }
function fixtureWindow() { from.value = '2026-10-15'; to.value = '2026-10-17'; granularity.value = 'day'; page.value = 1 }
watch(() => props.cityId, () => { region.value = ''; search.value = ''; dataset.value = ''; page.value = 1 })
watch([from, to, dataset, granularity, region, search, pageSize], () => { page.value = 1 })
watch([() => props.cityId, from, to, dataset, granularity, region, search, page, pageSize], () => { void load() }, { immediate: true })
onUnmounted(() => { version++ })
</script>

<template>
  <section class="traffic-workspace" :class="{ presentation }" data-testid="traffic-dashboard" :aria-busy="busy">
    <div class="analysis-header"><div><p class="analysis-kicker">URBAN MOBILITY / ANALYTICS</p><h2>{{ cityName }}<span>交通态势分析</span></h2><p>CITY 样本统计 · UTC 时间 · MySQL 数据驱动</p></div>
      <div class="analysis-actions"><span class="live-pill"><i></i>S4 ANALYSIS</span><button @click="presentation = !presentation">{{ presentation ? '退出大屏' : '比赛大屏' }}</button></div></div>
    <form class="traffic-filters" @submit.prevent="load">
      <label>开始日期 · UTC<input v-model="from" aria-label="开始日期 UTC" type="date" min="2000-01-01" max="2099-12-31" required></label>
      <label>结束日期 · 不含当日<input v-model="to" aria-label="结束日期 UTC" type="date" min="2000-01-01" max="2099-12-31" required></label>
      <label>趋势粒度<select v-model="granularity" aria-label="趋势粒度"><option value="day">按天</option><option value="hour">按小时 · 最长 31 天</option></select></label>
      <label class="dataset-filter">数据集<input v-model.lazy="dataset" aria-label="统计数据集" placeholder="默认：城市登记数据集" maxlength="64"></label>
      <button type="submit" class="primary-action" :disabled="busy">{{ busy ? '读取中…' : '刷新分析' }}</button>
      <button type="button" class="fixture-action" @click="fixtureWindow">合成样本时段</button>
    </form>
    <p class="window-caption">UTC 左闭右开区间；最长 366 天。改变筛选后自动刷新。区域选择仅筛选 ROAD 排名，CITY 指标保持城市口径。</p>
    <div v-if="busy" class="traffic-state" role="status">正在读取 MySQL 交通统计…</div>
    <div v-else-if="error" class="traffic-state traffic-error" role="alert"><strong>分析暂不可用</strong><p>{{ error }}</p><button @click="load">重试分析</button></div>
    <template v-else-if="summary && series && regions && roads">
      <div class="traffic-provenance"><span :class="{ synthetic: provenance?.sourceType === 'synthetic_test' }">{{ provenance?.sourceType }}</span><code>{{ provenance?.datasetId }}</code>
        <span>观测截至 {{ provenance?.dataAsOf ?? '无观测' }}</span></div>
      <p v-if="provenance?.sourceType === 'synthetic_test'" class="synthetic-notice">synthetic_test 合成测试：指标与地图点位均为测试样本，不代表真实城市交通或地理采集结果。</p>
      <p v-else class="synthetic-notice">来源及授权状态仅为数据库登记；不表示外部授权真实性已经核实。</p>
      <p v-if="empty" class="traffic-state" data-testid="traffic-empty">当前时段无 CITY 观测，指标以 — 表示；区域、道路按各自层级独立展示。</p>
      <p v-else-if="sparse" class="sparse-notice">样本稀疏：均值仅描述当前观测；缺失时段不补零、不连线，不推断车辆或通勤人数。</p>
      <div class="kpi-grid">
        <article class="kpi-card"><span>城市平均速度</span><strong data-testid="kpi-speed">{{ number(metrics?.avgSpeedKmh) }}<small>km/h</small></strong><p>CITY · 样本算术平均</p><div class="kpi-accent"></div></article>
        <article class="kpi-card amber"><span>城市拥堵指数</span><strong data-testid="kpi-congestion">{{ number(metrics?.congestionIndex) }}<small>/ 10</small></strong><p>范围 0–10 · 非通行时间比</p><div class="kpi-accent"></div></article>
        <article class="kpi-card"><span>城市观测样本</span><strong data-testid="kpi-count">{{ metrics?.sampleCount }}<small>条</small></strong><p>严格隔离 REGION / ROAD</p><div class="kpi-accent"></div></article>
        <article class="kpi-card blue"><span>分析覆盖区域</span><strong>{{ regions.data.items.filter(r => r.metrics.sampleCount > 0).length }}<small>/ {{ regions.data.items.length }}</small></strong><p>{{ points.length }} 个 WGS84 点 · {{ missing }} 个无坐标</p><div class="kpi-accent"></div></article>
      </div>
      <div class="analysis-grid">
        <article class="analysis-panel trend-panel"><div class="analysis-panel-title"><h3><i></i>城市历史趋势</h3><span>CITY / {{ granularity === 'day' ? 'DAILY' : 'HOURLY' }} · UTC</span></div>
          <TrafficChart :option="trendOption" label="城市平均速度和拥堵指数趋势；可滚轮缩放，底部拖动时段" />
          <details class="chart-data"><summary>查看趋势数据表</summary><div class="table-scroll"><table><thead><tr><th>UTC 时段</th><th>样本</th><th>km/h</th><th>指数</th></tr></thead><tbody><tr v-for="item in series.data.items" :key="item.bucket"><td>{{ item.bucket }}</td><td>{{ item.metrics.sampleCount }}</td><td>{{ number(item.metrics.avgSpeedKmh) }}</td><td>{{ number(item.metrics.congestionIndex) }}</td></tr></tbody></table></div></details>
        </article>
        <article class="analysis-panel region-panel"><div class="analysis-panel-title"><h3><i></i>区域拥堵对比</h3><span>REGION / 0–10</span></div>
          <TrafficChart :option="regionOption" label="区域拥堵对比；点击区域筛选路段" @select="selectRegion" />
          <div class="region-buttons"><button v-for="item in regions.data.items" :key="item.id" :aria-pressed="region === item.id" @click="selectRegion(item.id)">{{ item.name }} · {{ number(item.metrics.congestionIndex) }}</button></div>
          <p v-if="!regions.data.items.length" class="chart-caption">当前城市无区域登记。</p>
        </article>
        <article class="analysis-panel map-panel"><div class="analysis-panel-title"><h3><i></i>区域点位地图</h3><span>WGS84 / 无外部底图</span></div>
          <TrafficChart v-if="points.length" :option="mapOption" label="WGS84 经纬度区域点位地图；可缩放，点击点位联动路段" @select="selectRegion" />
          <div v-else class="traffic-state">当前城市无可用 WGS84 坐标，未绘制地图点位。</div>
          <div class="map-controls"><button v-for="point in points" :key="point.id" :aria-pressed="region === point.id" :data-map-point="point.id" @click="selectRegion(point.id)">⌖ {{ point.name }} <span>{{ point.longitude }}, {{ point.latitude }}</span></button></div>
          <p class="chart-caption">经纬度点位视图，非道路底图；{{ missing }} 个区域缺少坐标已省略。无道路几何，不绘制道路。{{ provenance?.sourceType === 'synthetic_test' ? '点位为合成绘图测试值。' : '' }}</p>
        </article>
        <article class="analysis-panel roads-panel"><div class="analysis-panel-title"><h3><i></i>路段拥堵排名</h3><span>ROAD / 指数降序</span></div>
          <div class="road-filters"><label>区域<select v-model="region" aria-label="路段区域"><option value="">全部区域</option><option v-for="item in regions.data.items" :key="item.id" :value="item.id">{{ item.name }}</option></select></label><label>路段名称<input v-model.lazy="search" aria-label="路段关键词" placeholder="输入后回车或移开焦点" maxlength="100"></label><label>每页<select v-model.number="pageSize" aria-label="每页路段数"><option :value="1">1</option><option :value="10">10</option><option :value="20">20</option></select></label></div>
          <p v-if="selectedRegion" class="filter-caption">当前联动：{{ selectedRegion.name }} <button @click="region = ''">清除</button></p>
          <div class="table-scroll"><table data-testid="roads-table"><thead><tr><th>排名 / 路段</th><th>速度 km/h</th><th>指数</th><th>样本</th></tr></thead><tbody><tr v-for="(road, index) in roads.data.items" :key="road.id"><td><span class="rank">{{ (page - 1) * pageSize + index + 1 }}</span>{{ road.name }}<small>{{ road.id }}</small></td><td>{{ number(road.metrics.avgSpeedKmh) }}</td><td><span class="index-pill">{{ number(road.metrics.congestionIndex) }}</span></td><td>{{ road.metrics.sampleCount }}</td></tr></tbody></table></div>
          <p v-if="!roads.data.items.length" class="chart-caption" data-testid="roads-empty">没有匹配的路段。请调整关键词、区域或页码。</p>
          <div class="pagination"><span>共 {{ roads.data.total }} 条 · 第 {{ page }} / {{ pageCount }} 页</span><button :disabled="page <= 1" aria-label="路段上一页" @click="page--">←</button><button :disabled="page >= pageCount" aria-label="路段下一页" @click="page++">→</button></div>
        </article>
      </div>
      <div class="analysis-footnote"><span>窗口 {{ summary.data.window.from }} → {{ summary.data.window.to }}</span><code>Request {{ provenance?.requestId }}</code></div>
    </template>
  </section>
</template>
