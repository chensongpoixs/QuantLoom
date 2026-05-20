<template>
  <div class="kline-wrapper">
    <div v-if="loading" class="kline-loading">加载 K 线数据中...</div>
    <div v-else-if="error" class="kline-error">{{ error }}</div>
    <div
      v-else
      class="chart-container"
      ref="chartRef"
    ></div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as echarts from 'echarts'
import { getEchartsTheme } from '@/utils/echarts-theme'

export interface KlineRecord {
  date: string
  open: number
  close: number
  high: number
  low: number
  volume: number
  ma5: number | null
  ma10: number | null
  ma20: number | null
  ma60: number | null
  ma120: number | null
  macd_dif: number | null
  macd_dea: number | null
  macd_hist: number | null
  boll_upper: number | null
  boll_mid: number | null
  boll_lower: number | null
}

const props = withDefaults(
  defineProps<{
    data: KlineRecord[] | null
    loading?: boolean
    error?: string | null
    showMACD?: boolean
    showBOLL?: boolean
    height?: number
  }>(),
  {
    loading: false,
    error: null,
    showMACD: true,
    showBOLL: true,
    height: 520,
  },
)

const chartRef = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null

function buildOption(data: KlineRecord[]) {
  const dates = data.map((d) => d.date)
  const ohlc = data.map((d) => [d.open, d.close, d.low, d.high])
  const volumes = data.map((d) => d.volume)
  const ma5 = data.map((d) => d.ma5)
  const ma10 = data.map((d) => d.ma10)
  const ma20 = data.map((d) => d.ma20)
  const ma60 = data.map((d) => d.ma60)
  const ma120 = data.map((d) => d.ma120)
  const macdDif = data.map((d) => d.macd_dif)
  const macdDea = data.map((d) => d.macd_dea)
  const macdHist = data.map((d) => d.macd_hist)
  const bollUpper = data.map((d) => d.boll_upper)
  const bollMid = data.map((d) => d.boll_mid)
  const bollLower = data.map((d) => d.boll_lower)

  // Volume bar colors
  const volumeColors = data.map((d) => (d.close >= d.open ? '#ef4444' : '#22c55e'))
  // MACD histogram colors
  const macdColors = macdHist.map((v) =>
    v == null ? 'transparent' : v >= 0 ? '#ef4444' : '#22c55e',
  )

  const volumeMax = Math.max(...volumes.filter((v) => v > 0), 1)
  const volumeGridTop = props.showMACD ? '48%' : '67%'
  const volumeGridBottom = props.showMACD ? '62%' : '85%'
  const macdGridTop = '72%'

  // K-line + MA grid
  const topGrid = {
    left: 4,
    right: 12,
    top: 12,
    bottom: props.showMACD ? '55%' : '38%',
  }
  const volumeGrid = {
    left: 4,
    right: 12,
    top: volumeGridTop,
    bottom: volumeGridBottom,
  }

  const series: any[] = [
    // ---- Panel 1: Candlestick ----
    {
      name: 'K线',
      type: 'candlestick',
      xAxisIndex: 0,
      yAxisIndex: 0,
      data: ohlc,
      itemStyle: {
        color: '#ef4444',
        color0: '#22c55e',
        borderColor: '#ef4444',
        borderColor0: '#22c55e',
      },
      markLine: {
        silent: true,
        symbol: 'none',
        lineStyle: { type: 'dashed', color: '#94a3b8', opacity: 0.5 },
        data: [
          {
            yAxis: data[data.length - 1].close,
            label: { formatter: '{c}', fontSize: 10, color: '#64748b' },
          },
        ],
      },
    },
    // MA5
    {
      name: 'MA5',
      type: 'line',
      xAxisIndex: 0,
      yAxisIndex: 0,
      data: ma5,
      smooth: false,
      symbol: 'none',
      lineStyle: { width: 1, color: '#f59e0b' },
    },
    // MA10
    {
      name: 'MA10',
      type: 'line',
      xAxisIndex: 0,
      yAxisIndex: 0,
      data: ma10,
      smooth: false,
      symbol: 'none',
      lineStyle: { width: 1, color: '#3b82f6' },
    },
    // MA20
    {
      name: 'MA20',
      type: 'line',
      xAxisIndex: 0,
      yAxisIndex: 0,
      data: ma20,
      smooth: false,
      symbol: 'none',
      lineStyle: { width: 1.5, color: '#8b5cf6' },
    },
    // MA60
    {
      name: 'MA60',
      type: 'line',
      xAxisIndex: 0,
      yAxisIndex: 0,
      data: ma60,
      smooth: false,
      symbol: 'none',
      lineStyle: { width: 1, color: '#ec4899' },
    },
    // MA120
    {
      name: 'MA120',
      type: 'line',
      xAxisIndex: 0,
      yAxisIndex: 0,
      data: ma120,
      smooth: false,
      symbol: 'none',
      lineStyle: { width: 1, color: '#14b8a6', type: 'dashed' },
    },
    // ---- Panel 2: Volume ----
    {
      name: '成交量',
      type: 'bar',
      xAxisIndex: 1,
      yAxisIndex: 1,
      data: volumes.map((v, i) => ({
        value: v,
        itemStyle: { color: volumeColors[i] },
      })),
    },
    // ---- Panel 3: MACD (if enabled) ----
    ...(props.showMACD
      ? [
          {
            name: 'MACD Hist',
            type: 'bar',
            xAxisIndex: 2,
            yAxisIndex: 2,
            data: macdHist.map((v, i) => ({
              value: v,
              itemStyle: { color: macdColors[i] },
            })),
          },
          {
            name: 'DIF',
            type: 'line',
            xAxisIndex: 2,
            yAxisIndex: 2,
            data: macdDif,
            smooth: false,
            symbol: 'none',
            lineStyle: { width: 1, color: '#f59e0b' },
          },
          {
            name: 'DEA',
            type: 'line',
            xAxisIndex: 2,
            yAxisIndex: 2,
            data: macdDea,
            smooth: false,
            symbol: 'none',
            lineStyle: { width: 1, color: '#3b82f6' },
          },
        ]
      : []),
    // BOLL (if enabled)
    ...(props.showBOLL
      ? [
          {
            name: 'BOLL上轨',
            type: 'line',
            xAxisIndex: 0,
            yAxisIndex: 0,
            data: bollUpper,
            smooth: false,
            symbol: 'none',
            lineStyle: { width: 0.5, color: '#94a3b8', type: 'dashed' },
          },
          {
            name: 'BOLL中轨',
            type: 'line',
            xAxisIndex: 0,
            yAxisIndex: 0,
            data: bollMid,
            smooth: false,
            symbol: 'none',
            lineStyle: { width: 0.5, color: '#64748b', type: 'dashed' },
          },
          {
            name: 'BOLL下轨',
            type: 'line',
            xAxisIndex: 0,
            yAxisIndex: 0,
            data: bollLower,
            smooth: false,
            symbol: 'none',
            lineStyle: { width: 0.5, color: '#94a3b8', type: 'dashed' },
          },
        ]
      : []),
  ]

  const xAxes: any[] = [
    {
      type: 'category',
      data: dates,
      gridIndex: 0,
      axisLine: { lineStyle: { color: '#e9ecef' } },
      axisLabel: { color: '#94a3b8', fontSize: 10 },
      axisTick: { show: false },
    },
    {
      type: 'category',
      data: dates,
      gridIndex: 1,
      axisLine: { show: false },
      axisLabel: { show: false },
      axisTick: { show: false },
    },
    ...(props.showMACD
      ? [
          {
            type: 'category',
            data: dates,
            gridIndex: 2,
            axisLine: { lineStyle: { color: '#e9ecef' } },
            axisLabel: { color: '#94a3b8', fontSize: 10 },
            axisTick: { show: false },
          },
        ]
      : []),
  ]

  // Volume yAxis: show values like 1.2M
  const yAxes: any[] = [
    {
      type: 'value',
      scale: true,
      splitLine: { lineStyle: { color: '#f1f3f5' } },
      axisLabel: { color: '#94a3b8', fontSize: 10 },
      position: 'right',
    },
    {
      type: 'value',
      scale: true,
      splitLine: { show: false },
      axisLabel: {
        show: true,
        fontSize: 9,
        color: '#94a3b8',
        formatter: (v: number) => {
          if (v >= 1e8) return (v / 1e8).toFixed(1) + '亿'
          if (v >= 1e6) return (v / 1e6).toFixed(1) + 'M'
          if (v >= 1e4) return (v / 1e4).toFixed(0) + '万'
          return v > 0 ? String(v) : ''
        },
      },
    },
    ...(props.showMACD
      ? [
          {
            type: 'value',
            scale: true,
            splitLine: { lineStyle: { color: '#f1f3f5' } },
            axisLabel: { color: '#94a3b8', fontSize: 10 },
            position: 'right',
          },
        ]
      : []),
  ]

  return {
    animation: true,
    animationDuration: 500,
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross',
        crossStyle: { color: '#94a3b8' },
      },
      backgroundColor: '#fff',
      borderColor: '#e9ecef',
      textStyle: { color: '#1a1a2e', fontSize: 12 },
      formatter: (params: any[]) => {
        if (!params || params.length === 0) return ''
        const date = params[0].axisValue
        let html = `<div style="font-weight:600;margin-bottom:4px">${date}</div>`
        for (const p of params) {
          if (p.seriesName === '成交量') {
            const v = p.value
            const volStr =
              v >= 1e8
                ? (v / 1e8).toFixed(2) + '亿'
                : v >= 1e4
                  ? (v / 1e4).toFixed(0) + '万'
                  : v
            html += `<div style="font-size:11px;color:#64748b">${p.marker} ${p.seriesName}: ${volStr}</div>`
          } else {
            html += `<div style="font-size:11px;color:#64748b">${p.marker} ${p.seriesName}: ${p.value}</div>`
          }
        }
        return html
      },
    },
    legend: {
      data: ['MA5', 'MA10', 'MA20', 'MA60'],
      bottom: 0,
      textStyle: { fontSize: 10, color: '#6c757d' },
      itemWidth: 14,
      itemHeight: 6,
    },
    grid: [topGrid, volumeGrid, ...(props.showMACD ? [{ left: 4, right: 12, top: macdGridTop, bottom: '5%' }] : [])],
    xAxis: xAxes,
    yAxis: yAxes,
    series,
    dataZoom: [
      {
        type: 'inside',
        xAxisIndex: [0, 1, ...(props.showMACD ? [2] : [])],
        start: Math.max(0, 100 - (120 / data.length) * 100),
        end: 100,
      },
      {
        type: 'slider',
        xAxisIndex: [0, 1, ...(props.showMACD ? [2] : [])],
        start: Math.max(0, 100 - (120 / data.length) * 100),
        end: 100,
        height: 20,
        bottom: props.showMACD ? 0 : 10,
        borderColor: '#e9ecef',
        backgroundColor: '#f8f9fa',
      },
    ],
  }
}

function render() {
  if (!chart || !props.data || props.data.length === 0) return
  const option = buildOption(props.data)
  chart.setOption(option, true)
}

function handleResize() {
  chart?.resize()
}

onMounted(() => {
  if (chartRef.value) {
    chart = echarts.init(chartRef.value, getEchartsTheme())
    window.addEventListener('resize', handleResize)
    render()
  }
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  chart?.dispose()
  chart = null
})

watch(
  () => [props.data, props.showMACD, props.showBOLL],
  () => render(),
  { deep: true },
)
</script>

<style scoped>
.kline-wrapper {
  width: 100%;
}

.chart-container {
  width: 100%;
  height: v-bind(height + 'px');
}

.kline-loading,
.kline-error {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 300px;
  color: var(--text-muted);
  font-size: 0.9rem;
}

.kline-error {
  color: var(--accent-red);
}

@media (max-width: 767px) {
  .chart-container {
    height: 360px;
  }
}
</style>
