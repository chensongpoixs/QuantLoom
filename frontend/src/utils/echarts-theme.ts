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
