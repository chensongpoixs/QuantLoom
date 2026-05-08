<template>
  <div class="alert-card" @click="$router.push(`/alerts/${alert.id}`)">
    <div class="alert-card-top">
      <span class="alert-card-code">{{ alert.code }}</span>
      <span class="alert-card-name">{{ alert.name }}</span>
      <RiskBadge :level="alert.risk_level" />
      <span style="flex:1"></span>
      <ConfidenceGauge :score="alert.confidence_score || 0" size="sm" />
    </div>
    <div class="alert-card-reason" v-if="alert.trigger_reason">
      {{ alert.trigger_reason }}
    </div>
    <div class="alert-card-bottom">
      <span>{{ ALERT_TYPE_LABELS[alert.alert_type || ''] || alert.alert_type }}</span>
      <span>·</span>
      <span v-if="alert.ts">{{ formatTime(alert.ts) }}</span>
      <span>·</span>
      <span>{{ formatAmount(alert.net_inflow_amount) }}</span>
      <span v-if="alert.ai_summary" style="color:var(--accent-blue)">AI ✓</span>
      <span v-if="actionLabel" :class="['action-tag', actionClass]" style="margin-left:auto">{{ actionLabel }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import RiskBadge from './RiskBadge.vue'
import ConfidenceGauge from './ConfidenceGauge.vue'
import type { Alert } from '@/types'
import { ALERT_TYPE_LABELS, formatTime, formatAmount } from '@/utils'

const props = defineProps<{ alert: Alert }>()

interface AiEvidence {
  action?: string
  reason_type?: string
  risk_points?: string[]
}

const actionLabel = computed(() => {
  const ev = props.alert.ai_evidence as AiEvidence | null
  if (!ev?.action) return null
  const map: Record<string, string> = { watch: '加入观察池', review: '需复核', ignore: '可忽略' }
  return map[ev.action] || ev.action
})

const actionClass = computed(() => {
  const ev = props.alert.ai_evidence as AiEvidence | null
  if (!ev?.action) return ''
  return ev.action === 'watch' ? 'action-watch' : ev.action === 'review' ? 'action-review' : 'action-ignore'
})
</script>

<style scoped>
.alert-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  padding: 16px;
  margin-bottom: 12px;
  box-shadow: var(--shadow-sm);
  cursor: pointer;
  transition: all var(--transition);
}
.alert-card:hover {
  box-shadow: var(--shadow-md);
  border-color: var(--accent-blue);
}

.alert-card-top {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.alert-card-code {
  font-weight: 700;
  font-family: var(--font-mono);
  font-size: 0.95rem;
  color: var(--text-primary);
  min-width: 70px;
}

.alert-card-name {
  font-size: 0.9rem;
  color: var(--text-secondary);
  flex: 1;
}

.alert-card-reason {
  font-size: 0.85rem;
  color: var(--text-secondary);
  margin-bottom: 8px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.alert-card-bottom {
  display: flex;
  align-items: center;
  gap: 16px;
  font-size: 0.8rem;
  color: var(--text-muted);
}

.action-tag {
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 0.7rem;
  font-weight: 600;
}
.action-watch { background: var(--accent-blue-light); color: var(--accent-blue); }
.action-review { background: var(--accent-orange-light); color: var(--accent-orange); }
.action-ignore { background: var(--bg-secondary); color: var(--text-muted); }
</style>
