<template>
  <div class="heatmap-container" ref="chartRef"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as echarts from 'echarts'
import { getEchartsTheme } from '@/utils/echarts-theme'
import type { SectorHeatmapItem } from '@/types'

const props = defineProps<{ data: SectorHeatmapItem[] }>()

const chartRef = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null

function render() {
  if (!chart || !props.data.length) return

  const items = props.data.map((d) => ({
    name: d.sector,
    value: d.alert_count,
    avgConfidence: d.avg_confidence,
  }))

  chart.setOption({
    tooltip: {
      formatter: (p: any) => {
        const d = p.data
        return `${d.name}<br/>告警数: ${d.value}<br/>平均置信度: ${(d.avgConfidence * 100).toFixed(1)}%`
      },
    },
    series: [{
      type: 'treemap',
      roam: false,
      nodeClick: false,
      width: '100%',
      height: '100%',
      breadcrumb: { show: false },
      label: {
        show: true,
        formatter: '{b}',
        fontSize: 11,
        color: '#fff',
      },
      upperLabel: { show: false },
      itemStyle: {
        borderColor: '#fff',
        borderWidth: 2,
      },
      levels: [{
        colorMapping: 'value',
        color: ['#eff6ff', '#bfdbfe', '#93c5fd', '#60a5fa', '#2563eb'],
      }],
      data: items,
    }],
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

watch(() => props.data, render, { deep: true })
</script>

<style scoped>
.heatmap-container {
  width: 100%;
  height: 320px;
}

@media (max-width: 767px) {
  .heatmap-container {
    height: 240px;
  }
}
</style>
