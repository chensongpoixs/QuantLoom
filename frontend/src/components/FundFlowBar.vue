<template>
  <div class="ffbar-container" ref="chartRef"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as echarts from 'echarts'
import { getEchartsTheme } from '@/utils/echarts-theme'
import type { FundFlowItem } from '@/types'

const props = defineProps<{
  inflows: FundFlowItem[]
  outflows: FundFlowItem[]
}>()

const chartRef = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null

function render() {
  if (!chart) return
  if (!props.inflows.length && !props.outflows.length) return

  const inData = [...props.inflows]
    .sort((a, b) => a.net_inflow - b.net_inflow)
    .map((d) => ({
      name: d.name,
      value: Math.abs(d.net_inflow),
      code: d.code,
    }))

  const outData = [...props.outflows]
    .sort((a, b) => b.net_inflow - a.net_inflow)
    .map((d) => ({
      name: d.name,
      value: -d.net_inflow,
      code: d.code,
    }))

  const allNames = [...outData.map((d) => d.name).reverse(), ...inData.map((d) => d.name)]

  chart.setOption({
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params: any) => {
        const p = Array.isArray(params) ? params[0] : params
        const d = p.data
        return `${d.name} (${d.code})<br/>净流入: ${(d.value / 1e8).toFixed(2)} 亿`
      },
    },
    grid: { left: 80, right: 16, top: 8, bottom: 8 },
    xAxis: {
      type: 'value',
      axisLabel: {
        formatter: (v: number) => (v / 1e8).toFixed(1) + '亿',
        fontSize: 10,
      },
      splitLine: { lineStyle: { color: '#f1f3f5' } },
    },
    yAxis: {
      type: 'category',
      data: allNames,
      axisLabel: { fontSize: 10, width: 70, overflow: 'truncate' },
      axisLine: { show: false },
      axisTick: { show: false },
    },
    series: [
      {
        type: 'bar',
        data: [
          ...outData.map((d) => ({ ...d, itemStyle: { color: '#16a34a' } })).reverse(),
          ...inData.map((d) => ({ ...d, itemStyle: { color: '#dc2626' } })),
        ],
        barWidth: 14,
      },
    ],
  }, true)
}

onMounted(() => {
  if (chartRef.value) {
    chart = echarts.init(chartRef.value, getEchartsTheme())
    window.addEventListener('resize', () => chart?.resize())
    render()
  }
})

onUnmounted(() => {
  chart?.dispose()
  chart = null
})

watch(() => [props.inflows, props.outflows], render, { deep: true })
</script>

<style scoped>
.ffbar-container {
  width: 100%;
  height: 400px;
}

@media (max-width: 767px) {
  .ffbar-container {
    height: 300px;
  }
}
</style>
