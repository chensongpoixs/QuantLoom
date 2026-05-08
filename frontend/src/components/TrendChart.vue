<template>
  <div
    class="chart-container"
    :class="{ sparkline: variant === 'sparkline' }"
    ref="chartRef"
  ></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as echarts from 'echarts'
import type { TrendData } from '@/types'
import { ALERT_TYPE_LABELS, CHART_COLOR_MAP } from '@/utils'

const props = withDefaults(
  defineProps<{
    data: TrendData | null
    variant?: 'full' | 'sparkline'
  }>(),
  { variant: 'full' },
)

const chartRef = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null

function buildSparklineOption(data: TrendData) {
  return {
    grid: { left: 0, right: 0, top: 4, bottom: 0 },
    xAxis: { show: false, data: data.dates },
    yAxis: { show: false, min: (v: { min: number }) => Math.floor(v.min * 0.9) },
    series: [
      {
        type: 'line',
        data: data.totals,
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 2, color: '#2563eb' },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(37, 99, 235, 0.25)' },
            { offset: 1, color: 'rgba(37, 99, 235, 0.02)' },
          ]),
        },
      },
    ],
  }
}

function buildFullOption(data: TrendData) {
  const series: any[] = []
  for (const [type, values] of Object.entries(data.by_type)) {
    series.push({
      name: ALERT_TYPE_LABELS[type] || type,
      type: 'line',
      data: values,
      smooth: true,
      symbol: 'circle',
      symbolSize: 4,
      lineStyle: { width: 2 },
      itemStyle: { color: CHART_COLOR_MAP[type] || '#94a3b8' },
    })
  }

  series.push({
    name: '总计',
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
  const option =
    props.variant === 'sparkline' ? buildSparklineOption(props.data) : buildFullOption(props.data)
  chart.setOption(option, true)
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

watch(() => props.data, render, { deep: true })
</script>

<style scoped>
.chart-container {
  width: 100%;
  height: 320px;
}

.chart-container.sparkline {
  height: 100px;
}

@media (max-width: 767px) {
  .chart-container:not(.sparkline) {
    height: 240px;
  }
  .chart-container.sparkline {
    height: 80px;
  }
}
</style>
