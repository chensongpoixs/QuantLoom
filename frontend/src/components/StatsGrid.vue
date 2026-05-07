<template>
  <div class="stats-grid">
    <div class="stat-card stat-blue">
      <div class="stat-label">Today Alerts</div>
      <div class="stat-value">{{ stats?.today.total ?? '--' }}</div>
      <div class="stat-sub">7d avg: {{ stats?.week_avg_daily ?? '--' }}/day</div>
    </div>

    <div class="stat-card stat-red">
      <div class="stat-label">P1 High Risk</div>
      <div class="stat-value">{{ stats?.today.p1 ?? '--' }}</div>
      <div class="stat-sub">P2: {{ stats?.today.p2 ?? '--' }} · P3: {{ stats?.today.p3 ?? '--' }}</div>
    </div>

    <div class="stat-card stat-green">
      <div class="stat-label">AI Coverage</div>
      <div class="stat-value">{{ aiCoverage }}%</div>
      <div class="stat-sub">{{ stats?.today.ai_analyzed ?? 0 }} / {{ stats?.today.total ?? 0 }} analyzed</div>
    </div>

    <div class="stat-card stat-orange">
      <div class="stat-label">Alert Types</div>
      <div class="stat-value">{{ typeCount }}</div>
      <div class="stat-sub" v-if="topType">{{ topType.type }}: {{ topType.count }}</div>
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

const topType = computed(() => {
  if (!props.stats?.by_type.length) return null
  return [...props.stats.by_type].sort((a, b) => b.count - a.count)[0]
})
</script>
