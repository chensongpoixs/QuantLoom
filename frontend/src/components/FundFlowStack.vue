<template>
  <div class="ffstack-container" ref="chartRef"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as echarts from 'echarts'

export interface FundFlowBreakdown {
  label: string
  data: string[]
}

const props = defineProps<{
  categories: string[]
  series: FundFlowBreakdown[]
}>()

const chartRef = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null

function render() {
  if (!chart || !props.series.length) return

  const echartsSeries = props.series.map((s) => ({
    name: s.label,
    type: 'bar',
    stack: 'total',
    data: s.data.map(Number),
    emphasis: { focus: 'series' },
    itemStyle: { borderRadius: s.label === '小单' ? [3, 3, 0, 0] as any : undefined },
  }))

  chart.setOption(
    {
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        backgroundColor: '#fff',
        borderColor: '#e9ecef',
        textStyle: { color: '#1a1a2e', fontSize: 12 },
        formatter: (params: any[]) => {
          let html = `<b>${params[0].axisValue}</b><br/>`
          let total = 0
          for (const p of params) {
            total += Number(p.value) || 0
          }
          for (const p of params) {
            html += `${p.marker} ${p.seriesName}: ${(Number(p.value) / 1e8).toFixed(2)}亿<br/>`
          }
          html += `<b>合计: ${(total / 1e8).toFixed(2)}亿</b>`
          return html
        },
      },
      legend: {
        bottom: 0,
        textStyle: { fontSize: 10, color: '#6c757d' },
        itemWidth: 10,
        itemHeight: 8,
      },
      grid: { left: 8, right: 16, top: 8, bottom: 32 },
      xAxis: {
        type: 'category',
        data: props.categories,
        axisLabel: { color: '#94a3b8', fontSize: 10, rotate: 30 },
      },
      yAxis: {
        type: 'value',
        axisLabel: {
          color: '#94a3b8',
          fontSize: 10,
          formatter: (v: number) => (v / 1e8).toFixed(0) + '亿',
        },
        splitLine: { lineStyle: { color: '#f1f3f5' } },
      },
      color: ['#dc2626', '#f57c00', '#2563eb', '#16a34a'], // 超大单红, 大单橙, 中单蓝, 小单绿
      series: echartsSeries,
    },
    true,
  )
}

onMounted(() => {
  if (chartRef.value) {
    chart = echarts.init(chartRef.value, 'quantloom')
    window.addEventListener('resize', () => chart?.resize())
    render()
  }
})

onUnmounted(() => {
  chart?.dispose()
  chart = null
})

watch(() => props.series, render, { deep: true })
</script>

<style scoped>
.ffstack-container {
  width: 100%;
  height: 320px;
}
@media (max-width: 767px) {
  .ffstack-container {
    height: 240px;
  }
}
</style>
