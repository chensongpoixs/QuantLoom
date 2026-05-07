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
      <div class="stat-sub" v-if="topType">{{ topTypeLabel(topType.type) }}: {{ topType.count }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { SummaryStats } from '@/stores/alerts'

const props = defineProps<{ stats: SummaryStats | null }>()

const aiCoverage = computed(() => {
  if (!props.stats || props.stats.today.total === 0) return 0
  return Math.round((props.stats.today.ai_analyzed / props.stats.today.total) * 100)
})

const typeCount = computed(() => props.stats?.by_type.length ?? 0)

const ALERT_TYPE_LABELS: Record<string, string> = {
  breakout: '放量上攻',
  accumulation: '底部吸筹',
  tail_chasing: '尾盘抢筹',
  event_driven: '事件驱动',
  sector_linked: '板块联动',
}
function topTypeLabel(type: string) {
  return ALERT_TYPE_LABELS[type] || type
}

const topType = computed(() => {
  if (!props.stats?.by_type.length) return null
  return [...props.stats.by_type].sort((a, b) => b.count - a.count)[0]
})
</script>
