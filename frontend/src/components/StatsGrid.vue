<template>
  <div class="stats-grid">
    <div class="stat-card stat-blue">
      <div class="stat-label">今日告警</div>
      <div class="stat-value">{{ stats?.today.total ?? '--' }}</div>
      <div class="stat-sub">近7日均值: {{ stats?.week_avg_daily ?? '--' }}/天</div>
    </div>

    <div class="stat-card stat-red">
      <div class="stat-label">P1 高风险</div>
      <div class="stat-value">{{ stats?.today.p1 ?? '--' }}</div>
      <div class="stat-sub">P2: {{ stats?.today.p2 ?? '--' }} · P3: {{ stats?.today.p3 ?? '--' }}</div>
    </div>

    <div class="stat-card stat-green">
      <div class="stat-label">AI 分析覆盖</div>
      <div class="stat-value">{{ aiCoverage }}%</div>
      <div class="stat-sub">{{ stats?.today.ai_analyzed ?? 0 }} / {{ stats?.today.total ?? 0 }} 已分析</div>
    </div>

    <div class="stat-card stat-orange">
      <div class="stat-label">异动类型</div>
      <div class="stat-value">{{ typeCount }}</div>
      <div class="stat-sub" v-if="topType">{{ ALERT_TYPE_LABELS[topType.type] || topType.type }}: {{ topType.count }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { SummaryStats } from '@/types'
import { ALERT_TYPE_LABELS } from '@/utils'

const props = defineProps<{ stats: SummaryStats | null }>()

const aiCoverage = computed(() => {
  if (!props.stats || props.stats.today.total === 0) return 0
  return Math.round((props.stats.today.ai_analyzed / props.stats.today.total) * 100)
})

const typeCount = computed(() => props.stats?.by_type.length ?? 0)

const topType = computed(() => {
  if (!props.stats?.by_type.length) return null
  return [...props.stats.by_type].sort((a, b) => b.count - a.count)[0]
})
</script>

<style scoped>
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}

.stat-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  padding: 20px;
  box-shadow: var(--shadow-sm);
  transition: box-shadow var(--transition);
}
.stat-card:hover {
  box-shadow: var(--shadow-md);
}

.stat-label {
  font-size: 0.8rem;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 8px;
}

.stat-value {
  font-size: 2rem;
  font-weight: 700;
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
}

.stat-sub {
  font-size: 0.8rem;
  color: var(--text-muted);
  margin-top: 4px;
}

.stat-red .stat-value { color: var(--accent-red); }
.stat-orange .stat-value { color: var(--accent-orange); }
.stat-blue .stat-value { color: var(--accent-blue); }
.stat-green .stat-value { color: var(--accent-green); }

@media (max-width: 1024px) {
  .stats-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 767px) {
  .stats-grid { grid-template-columns: 1fr; gap: 10px; }
  .stat-card { padding: 14px; }
  .stat-value { font-size: 1.6rem; }
}
</style>
