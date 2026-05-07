<template>
  <div class="chart-container" ref="chartRef"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as echarts from 'echarts'
import type { TrendData } from '@/stores/alerts'

const props = defineProps<{ data: TrendData | null }>()

const chartRef = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null

const COLOR_MAP: Record<string, string> = {
  breakout: '#2563eb',
  accumulation: '#16a34a',
  tail_chasing: '#f57c00',
  event_driven: '#8b5cf6',
  sector_linked: '#ec4899',
  unknown: '#94a3b8',
}

function buildOption(data: TrendData) {
  const series: any[] = []
  for (const [type, values] of Object.entries(data.by_type)) {
    series.push({
      name: type,
      type: 'line',
      data: values,
      smooth: true,
      symbol: 'circle',
      symbolSize: 4,
      lineStyle: { width: 2 },
      itemStyle: { color: COLOR_MAP[type] || '#94a3b8' },
    })
  }

  series.push({
    name: 'Total',
    type: 'line',
    data: data.totals,
    smooth: true,
    symbol: 'none',
    lineStyle: { width: 2, type: 'dashed', color: '#94a3b8' },
    itemStyle: { color: '#94a3b8' },
  })

  return {
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#fff',
      borderColor: '#e9ecef',
      textStyle: { color: '#1a1a2e', fontSize: 12 },
    },
    legend: {
      bottom: 0,
      textStyle: { fontSize: 11, color: '#6c757d' },
      itemWidth: 12,
      itemHeight: 8,
    },
    grid: { left: 8, right: 16, top: 8, bottom: 32 },
    xAxis: {
      type: 'category',
      data: data.dates,
      axisLine: { lineStyle: { color: '#e9ecef' } },
      axisLabel: { color: '#94a3b8', fontSize: 10 },
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      splitLine: { lineStyle: { color: '#f1f3f5' } },
    },
    series,
  }
}

function render() {
  if (!chart || !props.data) return
  chart.setOption(buildOption(props.data), true)
}

onMounted(() => {
  if (chartRef.value) {
    chart = echarts.init(chartRef.value)
    window.addEventListener('resize', () => chart?.resize())
    render()
  }
})

onUnmounted(() => {
  chart?.dispose()
  chart = null
})

watch(() => props.data, render, { deep: true })
</script>
