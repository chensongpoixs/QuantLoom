import * as echarts from 'echarts'

echarts.registerTheme('quantloom', {
  color: ['#dc2626', '#16a34a', '#2563eb', '#f57c00', '#8b5cf6', '#ec4899'],
  backgroundColor: '#ffffff',
  textStyle: {
    fontFamily: "-apple-system, BlinkMacSystemFont, 'PingFang SC', sans-serif",
  },
  title: {
    textStyle: { color: '#1a1a2e', fontWeight: 600 },
  },
  legend: {
    textStyle: { color: '#6c757d', fontSize: 11 },
    itemWidth: 12,
    itemHeight: 8,
  },
  tooltip: {
    backgroundColor: '#ffffff',
    borderColor: '#e9ecef',
    textStyle: { color: '#1a1a2e', fontSize: 12 },
  },
  grid: {
    left: 8,
    right: 16,
    top: 8,
    bottom: 32,
  },
  xAxis: {
    axisLine: { lineStyle: { color: '#e9ecef' } },
    axisLabel: { color: '#94a3b8', fontSize: 10 },
    splitLine: { show: false },
  },
  yAxis: {
    splitLine: { lineStyle: { color: '#f1f3f5' } },
    axisLabel: { color: '#94a3b8', fontSize: 10 },
  },
})

echarts.registerTheme('quantloom-dark', {
  color: ['#f87171', '#34d399', '#5b8def', '#fbbf24', '#a78bfa', '#f472b6'],
  backgroundColor: '#0f1117',
  textStyle: {
    fontFamily: "-apple-system, BlinkMacSystemFont, 'PingFang SC', sans-serif",
  },
  title: {
    textStyle: { color: '#e4e6ec', fontWeight: 600 },
  },
  legend: {
    textStyle: { color: '#9ca3af', fontSize: 11 },
    itemWidth: 12,
    itemHeight: 8,
  },
  tooltip: {
    backgroundColor: '#1e2130',
    borderColor: '#2d3143',
    textStyle: { color: '#e4e6ec', fontSize: 12 },
  },
  grid: {
    left: 8,
    right: 16,
    top: 8,
    bottom: 32,
  },
  xAxis: {
    axisLine: { lineStyle: { color: '#2d3143' } },
    axisLabel: { color: '#6b7280', fontSize: 10 },
    splitLine: { show: false },
  },
  yAxis: {
    splitLine: { lineStyle: { color: '#232738' } },
    axisLabel: { color: '#6b7280', fontSize: 10 },
  },
})

export function getEchartsTheme(): string {
  if (typeof document !== 'undefined') {
    return document.documentElement.getAttribute('data-theme') === 'dark'
      ? 'quantloom-dark'
      : 'quantloom'
  }
  return 'quantloom'
}
