<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { init, use, type EChartsCoreOption } from 'echarts/core'
import { LineChart, BarChart, ScatterChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, AriaComponent } from 'echarts/components'
import { SVGRenderer } from 'echarts/renderers'
use([LineChart, BarChart, ScatterChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, AriaComponent, SVGRenderer])
const props = defineProps<{ option: EChartsCoreOption; label: string }>()
const emit = defineEmits<{ select: [id: string] }>()
const element = ref<HTMLDivElement>()
let chart: ReturnType<typeof init> | undefined
let resize: ResizeObserver | undefined
onMounted(() => {
  chart = init(element.value!, undefined, { renderer: 'svg' })
  chart.setOption(props.option)
  chart.on('click', params => {
    const value = params.data as { id?: string } | undefined
    if (value?.id) emit('select', value.id)
  })
  resize = new ResizeObserver(() => chart?.resize())
  resize.observe(element.value!)
})
watch(() => props.option, value => chart?.setOption(value, { notMerge: true }))
onUnmounted(() => { resize?.disconnect(); chart?.dispose() })
</script>
<template><div ref="element" class="traffic-chart" role="img" :aria-label="label"></div></template>
