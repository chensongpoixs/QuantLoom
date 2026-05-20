<template>
  <div class="breadth-card">
    <div class="breadth-title">市场情绪</div>
    <div class="breadth-row">
      <div class="breadth-item up" :title="`涨停 ${breadth?.limit_up_count ?? '--'} 家`">
        <span class="breadth-value">{{ breadth?.limit_up_count ?? '--' }}</span>
        <span class="breadth-label">涨停</span>
      </div>
      <div class="breadth-item down" :title="`跌停 ${breadth?.limit_down_count ?? '--'} 家`">
        <span class="breadth-value">{{ breadth?.limit_down_count ?? '--' }}</span>
        <span class="breadth-label">跌停</span>
      </div>
      <div class="breadth-item" :class="sentimentClass">
        <span class="breadth-value">{{ upDownLabel }}</span>
        <span class="breadth-label">涨跌比</span>
      </div>
      <div class="breadth-item">
        <span class="breadth-value">{{ avgPctLabel }}</span>
        <span class="breadth-label">均涨幅</span>
      </div>
      <div class="breadth-item">
        <span class="breadth-value">{{ turnoverLabel }}</span>
        <span class="breadth-label">成交额</span>
      </div>
      <div class="breadth-item">
        <span class="breadth-value">{{ breadth?.broken_board_count ?? '--' }}</span>
        <span class="breadth-label">炸板</span>
      </div>
    </div>
    <div v-if="breadth" class="breadth-bar">
      <div class="bar-segment up" :style="{ width: upPct + '%' }"></div>
      <div class="bar-segment flat" :style="{ width: flatPct + '%' }"></div>
      <div class="bar-segment down" :style="{ width: downPct + '%' }"></div>
    </div>
    <div v-if="loading" class="breadth-loading">加载中...</div>
    <div v-else-if="!breadth" class="breadth-empty">暂无数据</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

export interface BreadthData {
  ts: string | null
  limit_up_count: number
  limit_down_count: number
  up_count: number
  down_count: number
  flat_count: number
  up_down_ratio: number
  adl: number
  broken_board_count: number
  avg_pct_change: number
  total_turnover: number
  limit_up_pct: number
  limit_down_pct: number
  sentiment: string
}

const props = withDefaults(
  defineProps<{
    breadth: BreadthData | null
    loading?: boolean
  }>(),
  { loading: false },
)

const sentimentClass = computed(() => {
  if (!props.breadth) return ''
  if (props.breadth.sentiment === 'bullish') return 'bullish'
  if (props.breadth.sentiment === 'bearish') return 'bearish'
  return 'neutral'
})

const upDownLabel = computed(() => {
  if (!props.breadth) return '--'
  const r = props.breadth.up_down_ratio
  if (r >= 5) return r.toFixed(0) + ':1'
  return r.toFixed(1)
})

const avgPctLabel = computed(() => {
  if (!props.breadth) return '--'
  const v = props.breadth.avg_pct_change
  return (v >= 0 ? '+' : '') + v.toFixed(2) + '%'
})

const turnoverLabel = computed(() => {
  if (!props.breadth) return '--'
  const v = props.breadth.total_turnover
  if (v >= 1e12) return (v / 1e12).toFixed(2) + '万亿'
  return (v / 1e8).toFixed(0) + '亿'
})

const totalStocks = computed(() => {
  if (!props.breadth) return 1
  return props.breadth.up_count + props.breadth.down_count + props.breadth.flat_count || 1
})

const upPct = computed(() =>
  props.breadth ? (props.breadth.up_count / totalStocks.value * 100) : 0,
)
const downPct = computed(() =>
  props.breadth ? (props.breadth.down_count / totalStocks.value * 100) : 0,
)
const flatPct = computed(() =>
  props.breadth ? (props.breadth.flat_count / totalStocks.value * 100) : 0,
)
</script>

<style scoped>
.breadth-card {
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  padding: 16px;
  margin-bottom: 20px;
}

.breadth-title {
  font-size: 0.75rem;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 12px;
  font-weight: 600;
}

.breadth-row {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.breadth-item {
  flex: 1;
  min-width: 60px;
  text-align: center;
  padding: 6px 4px;
  border-radius: var(--radius-sm);
  background: var(--bg-secondary);
}

.breadth-value {
  display: block;
  font-size: 1.1rem;
  font-weight: 700;
  font-family: var(--font-mono);
  color: var(--text-primary);
}

.breadth-label {
  display: block;
  font-size: 0.65rem;
  color: var(--text-muted);
  margin-top: 2px;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

.breadth-item.up .breadth-value { color: #ef4444; }
.breadth-item.down .breadth-value { color: #22c55e; }
.breadth-item.bullish .breadth-value { color: #ef4444; }
.breadth-item.bearish .breadth-value { color: #22c55e; }

.breadth-bar {
  display: flex;
  height: 4px;
  border-radius: 2px;
  overflow: hidden;
  margin-top: 12px;
  background: var(--bg-secondary);
}

.bar-segment.up { background: #ef4444; }
.bar-segment.flat { background: #cbd5e1; }
.bar-segment.down { background: #22c55e; }

.breadth-loading,
.breadth-empty {
  text-align: center;
  color: var(--text-muted);
  font-size: 0.8rem;
  padding: 8px;
}
</style>
