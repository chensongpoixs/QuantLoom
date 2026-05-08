<template>
  <div
    :class="['gauge-container', size]"
    ref="chartRef"
    :title="tooltipText"
  ></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, computed } from 'vue'
import * as echarts from 'echarts'

const props = withDefaults(
  defineProps<{
    score: number
    size?: 'sm' | 'md'
    precision?: number | null
    sampleCount?: number | null
    calibration?: number | null
  }>(),
  { size: 'md', precision: null, sampleCount: null, calibration: null },
)

const chartRef = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null

const tooltipText = computed(() => {
  const parts: string[] = [`置信度: ${Math.round((props.score || 0) * 100)}%`]
  if (props.precision != null) parts.push(`历史精度: ${(props.precision * 100).toFixed(0)}%`)
  if (props.sampleCount != null) parts.push(`样本数: ${props.sampleCount}`)
  if (props.calibration != null) parts.push(`校准系数: ${props.calibration.toFixed(2)}`)
  return parts.join('\n')
})

function render() {
  if (!chart) return
  const pct = Math.round((props.score || 0) * 100)
  chart.setOption(
    {
      tooltip: {
        show: true,
        backgroundColor: '#fff',
        borderColor: '#e9ecef',
        textStyle: { color: '#1a1a2e', fontSize: 12 },
        formatter: () => {
          const lines: string[] = [
            `<b>置信度: ${pct}%</b>`,
          ]
          if (props.precision != null) lines.push(`历史精度: ${(props.precision * 100).toFixed(0)}%`)
          if (props.sampleCount != null) lines.push(`样本数: ${props.sampleCount}`)
          if (props.calibration != null) lines.push(`校准系数: ${props.calibration.toFixed(2)}`)
          return lines.join('<br/>')
        },
      },
      series: [
        {
          type: 'gauge',
          startAngle: 210,
          endAngle: -30,
          center: ['50%', '60%'],
          radius: '90%',
          min: 0,
          max: 100,
          splitNumber: 5,
          axisLine: {
            show: true,
            lineStyle: {
              width: 12,
              color: [
                [0.3, '#dc2626'],
                [0.7, '#f57c00'],
                [1, '#16a34a'],
              ],
            },
          },
          pointer: { show: false },
          axisTick: { show: false },
          splitLine: { show: false },
          axisLabel: { show: false },
          detail: {
            valueAnimation: true,
            fontSize: props.size === 'sm' ? 20 : 28,
            fontWeight: 'bold',
            color: '#1a1a2e',
            offsetCenter: [0, '40%'],
            formatter: '{value}%',
          },
          data: [{ value: pct }],
        },
      ],
    },
    true,
  )
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

watch(() => [props.score, props.precision, props.sampleCount, props.calibration], render)
</script>

<style scoped>
.gauge-container {
  display: inline-block;
  cursor: help;
}
.gauge-container.sm {
  width: 80px;
  height: 60px;
}
.gauge-container.md {
  width: 140px;
  height: 100px;
}
</style>
