<template>
  <div class="signal-gauge" ref="chartRef"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as echarts from 'echarts'

const props = withDefaults(
  defineProps<{
    confidence?: number
    historicalPrecision?: number | null
    sampleCount?: number | null
    riskLevel?: string | null
  }>(),
  { confidence: 0, historicalPrecision: null, sampleCount: null, riskLevel: null },
)

const chartRef = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null

function render() {
  if (!chart) return
  const indicators = [
    {
      name: '规则得分',
      max: 100,
      value: riskScore(),
    },
    {
      name: 'AI 置信度',
      max: 100,
      value: Math.round((props.confidence || 0) * 100),
    },
    {
      name: '历史精度',
      max: 100,
      value: props.historicalPrecision != null ? Math.round(props.historicalPrecision * 100) : 0,
    },
    {
      name: '样本覆盖',
      max: 100,
      value: Math.min((props.sampleCount || 0) * 2, 100), // 50+ samples → full
    },
  ]

  chart.setOption(
    {
      radar: {
        center: ['50%', '55%'],
        radius: '65%',
        indicator: indicators,
        axisName: { color: '#6c757d', fontSize: 10 },
        splitArea: {
          areaStyle: {
            color: ['#fff', '#f8f9fa', '#fff', '#f8f9fa', '#fff'],
          },
        },
      },
      series: [
        {
          type: 'radar',
          data: [
            {
              value: indicators.map((i) => i.value),
              name: '综合评分',
              areaStyle: { color: 'rgba(37, 99, 235, 0.15)' },
              lineStyle: { color: '#2563eb', width: 2 },
              itemStyle: { color: '#2563eb' },
            },
          ],
          symbol: 'circle',
          symbolSize: 5,
        },
      ],
    },
    true,
  )
}

function riskScore(): number {
  // Map risk level to base score
  const map: Record<string, number> = { P1: 85, P2: 60, P3: 35 }
  return map[props.riskLevel || ''] || 50
}

onMounted(() => {
  if (chartRef.value) {
    chart = echarts.init(chartRef.value, 'quantloom')
    render()
  }
})

onUnmounted(() => {
  chart?.dispose()
  chart = null
})

watch(
  () => [props.confidence, props.historicalPrecision, props.sampleCount, props.riskLevel],
  render,
)
</script>

<style scoped>
.signal-gauge {
  width: 100%;
  height: 280px;
}
@media (max-width: 767px) {
  .signal-gauge {
    height: 220px;
  }
}
</style>
