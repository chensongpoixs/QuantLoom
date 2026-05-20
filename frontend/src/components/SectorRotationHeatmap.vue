<template>
  <div class="rotation-heatmap">
    <div class="heatmap-header">
      <h3>板块轮动热力图</h3>
      <div class="heatmap-controls">
        <label>回溯周数:</label>
        <select v-model.number="weeks" @change="refresh">
          <option :value="2">2 周</option>
          <option :value="4">4 周</option>
          <option :value="6">6 周</option>
          <option :value="8">8 周</option>
        </select>
      </div>
    </div>

    <div v-if="loading" class="loading">加载中...</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else ref="chartRef" class="chart-container"></div>

    <div v-if="momentum.length" class="momentum-section">
      <h4>期间动量排名 (累计收益 Top 5)</h4>
      <div class="momentum-list">
        <div
          v-for="(item, idx) in momentum.slice(0, 5)"
          :key="item.sector"
          class="momentum-item"
        >
          <span class="rank">{{ idx + 1 }}</span>
          <span class="sector-name">{{ item.sector }}</span>
          <span :class="['cum-return', item.cumulative_return >= 0 ? 'positive' : 'negative']">
            {{ item.cumulative_return >= 0 ? '+' : '' }}{{ item.cumulative_return }}%
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import { getEchartsTheme } from '@/utils/echarts-theme'

interface RotationData {
  sectors: string[]
  dates: string[]
  data: (number | null)[][]
  latest_ranking: { sector: string; pct_change: number }[]
  momentum_ranking: { sector: string; cumulative_return: number; avg_daily_return: number }[]
  lookback_days: number
}

const weeks = ref(4)
const loading = ref(false)
const error = ref('')
const chartRef = ref<HTMLDivElement | null>(null)
const momentum = ref<RotationData['momentum_ranking']>([])

let chart: echarts.ECharts | null = null

function renderHeatmap(result: RotationData) {
  if (!chartRef.value) return

  if (chart) chart.dispose()
  chart = echarts.init(chartRef.value, getEchartsTheme())

  const { sectors, dates, data } = result
  momentum.value = result.momentum_ranking

  // Build heatmap series data: [dateIdx, sectorIdx, value]
  const seriesData: [number, number, number][] = []
  let minVal = Infinity
  let maxVal = -Infinity

  for (let i = 0; i < sectors.length; i++) {
    for (let j = 0; j < dates.length; j++) {
      const val = data[i][j]
      if (val != null) {
        seriesData.push([j, i, val])
        if (val < minVal) minVal = val
        if (val > maxVal) maxVal = val
      }
    }
  }

  // Symmetric color range around 0
  const absMax = Math.max(Math.abs(minVal), Math.abs(maxVal), 0.5)

  chart.setOption({
    tooltip: {
      position: 'top',
      formatter: (p: any) => {
        const d = p.data
        const date = dates[d[0]] || ''
        const sector = sectors[d[1]] || ''
        const val = d[2] != null ? (d[2] >= 0 ? '+' : '') + d[2].toFixed(2) + '%' : '--'
        return `${sector}<br/>${date}: <b>${val}</b>`
      },
    },
    grid: {
      left: 90,
      right: 40,
      top: 20,
      bottom: 60,
    },
    xAxis: {
      type: 'category',
      data: dates,
      splitArea: { show: true },
      axisLabel: {
        fontSize: 10,
        formatter: (v: string) => v.slice(5), // MM-DD
      },
    },
    yAxis: {
      type: 'category',
      data: sectors,
      splitArea: { show: true },
      axisLabel: { fontSize: 11 },
    },
    visualMap: {
      min: -absMax,
      max: absMax,
      calculable: true,
      orient: 'vertical',
      right: 0,
      top: 'center',
      inRange: {
        color: ['#22c55e', '#86efac', '#f0f0f0', '#fca5a5', '#ef4444'],
      },
      text: ['涨', '跌'],
    },
    series: [{
      type: 'heatmap',
      data: seriesData,
      label: { show: false },
      emphasis: {
        itemStyle: {
          shadowBlur: 10,
          shadowColor: 'rgba(0, 0, 0, 0.5)',
        },
      },
      itemStyle: {
        borderColor: 'var(--bg-primary)',
        borderWidth: 1,
      },
    }],
  }, true)

  chart.resize()
}

async function refresh() {
  loading.value = true
  error.value = ''
  try {
    const resp = await fetch(`/api/sectors/rotation?weeks=${weeks.value}`)
    if (!resp.ok) {
      const msg = await resp.text()
      throw new Error(msg || `HTTP ${resp.status}`)
    }
    const result: RotationData = await resp.json()
    await nextTick()
    renderHeatmap(result)
  } catch (e: any) {
    error.value = e.message || '加载失败'
  } finally {
    loading.value = false
  }
}

function onResize() {
  chart?.resize()
}

onMounted(() => {
  window.addEventListener('resize', onResize)
  refresh()
})

onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  chart?.dispose()
  chart = null
})
</script>

<style scoped>
.rotation-heatmap {
  background: var(--bg-card);
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.heatmap-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.heatmap-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.heatmap-controls {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text-secondary);
}

.heatmap-controls select {
  padding: 4px 10px;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  background: var(--bg-primary);
  color: var(--text-primary);
  font-size: 13px;
}

.chart-container {
  width: 100%;
  height: 520px;
}

.loading {
  text-align: center;
  padding: 60px 0;
  color: var(--text-secondary);
}

.error {
  text-align: center;
  padding: 60px 0;
  color: #ef4444;
}

.momentum-section {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--border-color);
}

.momentum-section h4 {
  margin: 0 0 10px 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.momentum-list {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.momentum-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  background: var(--bg-primary);
  border-radius: 8px;
  font-size: 13px;
}

.rank {
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: var(--accent-color);
  color: #fff;
  font-size: 11px;
  font-weight: 700;
}

.sector-name {
  color: var(--text-primary);
  min-width: 60px;
}

.cum-return {
  font-weight: 600;
}

.positive {
  color: #ef4444;
}

.negative {
  color: #22c55e;
}

@media (max-width: 767px) {
  .chart-container {
    height: 360px;
  }
  .momentum-list {
    flex-direction: column;
  }
}
</style>
