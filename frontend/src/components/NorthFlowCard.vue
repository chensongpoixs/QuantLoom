<template>
  <div class="north-card">
    <div class="north-title">北向资金 · 沪深港通</div>

    <div v-if="loading" class="north-loading">加载中...</div>
    <div v-else-if="!data" class="north-empty">暂无数据</div>

    <template v-else>
      <div class="north-main-row">
        <div class="north-item primary">
          <span class="north-value" :class="inflowClass">
            {{ inflowLabel }}
          </span>
          <span class="north-label">今日净流入</span>
        </div>
        <div class="north-item">
          <span class="north-value">{{ avgLabel }}</span>
          <span class="north-label">5日均值</span>
        </div>
        <div class="north-item">
          <span class="north-value" :class="accelClass">{{ accelLabel }}</span>
          <span class="north-label">加速率</span>
        </div>
      </div>

      <!-- Top10 净买入 -->
      <div v-if="top10Entries.length" class="north-top10">
        <div class="north-subtitle">十大成交净买入 (亿元)</div>
        <div class="north-top10-grid">
          <div
            v-for="(entry, i) in top10Entries"
            :key="entry.code"
            class="north-top10-item"
          >
            <span class="top10-rank">{{ i + 1 }}</span>
            <span class="top10-code">{{ entry.code }}</span>
            <span class="top10-name">{{ entry.name }}</span>
            <span class="top10-net" :class="entry.net > 0 ? 'positive' : 'negative'">
              {{ entry.net > 0 ? '+' : '' }}{{ entry.net.toFixed(1) }}
            </span>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

export interface NorthFlowData {
  net_inflow_today: number
  net_inflow_5d_avg: number
  inflow_accel: number
  top10_net_buy: Record<string, number>
  holding_top: { code: string; name: string; hold_ratio: number }[]
}

const props = withDefaults(
  defineProps<{
    data: NorthFlowData | null
    loading?: boolean
  }>(),
  { loading: false },
)

const inflowLabel = computed(() => {
  if (!props.data) return '--'
  const v = props.data.net_inflow_today
  return (v >= 0 ? '+' : '') + v.toFixed(1) + '亿'
})

const avgLabel = computed(() => {
  if (!props.data) return '--'
  const v = props.data.net_inflow_5d_avg
  return (v >= 0 ? '+' : '') + v.toFixed(1) + '亿'
})

const accelLabel = computed(() => {
  if (!props.data) return '--'
  const v = props.data.inflow_accel
  return (v >= 0 ? '+' : '') + v.toFixed(0) + '%'
})

const inflowClass = computed(() => {
  if (!props.data) return ''
  return props.data.net_inflow_today >= 0 ? 'positive' : 'negative'
})

const accelClass = computed(() => {
  if (!props.data) return ''
  return props.data.inflow_accel >= 0 ? 'positive' : 'negative'
})

const top10Entries = computed(() => {
  if (!props.data?.top10_net_buy) return []
  const entries = Object.entries(props.data.top10_net_buy)
    .map(([code, net]) => ({
      code,
      name: '',
      net: Number(net) || 0,
    }))
    .filter((e) => Math.abs(e.net) > 0.5)
    .sort((a, b) => Math.abs(b.net) - Math.abs(a.net))
    .slice(0, 10)
  return entries
})
</script>

<style scoped>
.north-card {
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  padding: 16px;
  margin-bottom: 20px;
}

.north-title {
  font-size: 0.75rem;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 12px;
  font-weight: 600;
}

.north-main-row {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.north-item {
  flex: 1;
  min-width: 80px;
  text-align: center;
  padding: 8px 4px;
  border-radius: var(--radius-sm);
  background: var(--bg-secondary);
}

.north-item.primary {
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
}

.north-value {
  display: block;
  font-size: 1.15rem;
  font-weight: 700;
  font-family: var(--font-mono);
  color: var(--text-primary);
}

.north-value.positive { color: #16a34a; }
.north-value.negative { color: #dc2626; }

.north-label {
  display: block;
  font-size: 0.65rem;
  color: var(--text-muted);
  margin-top: 2px;
  text-transform: uppercase;
}

.north-loading,
.north-empty {
  text-align: center;
  color: var(--text-muted);
  font-size: 0.8rem;
  padding: 12px;
}

.north-top10 {
  margin-top: 14px;
}

.north-subtitle {
  font-size: 0.7rem;
  color: var(--text-muted);
  margin-bottom: 8px;
  font-weight: 500;
}

.north-top10-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.north-top10-item {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  border-radius: var(--radius-sm);
  background: var(--bg-secondary);
  font-size: 0.75rem;
}

.top10-rank {
  color: var(--text-muted);
  font-size: 0.65rem;
  min-width: 14px;
}

.top10-code {
  font-family: var(--font-mono);
  font-weight: 600;
  color: var(--text-primary);
}

.top10-name {
  color: var(--text-secondary);
  max-width: 60px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.top10-net {
  font-family: var(--font-mono);
  font-weight: 500;
  margin-left: auto;
}

.top10-net.positive { color: #16a34a; }
.top10-net.negative { color: #dc2626; }
</style>
