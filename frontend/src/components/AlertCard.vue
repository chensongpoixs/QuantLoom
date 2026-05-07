<template>
  <div class="alert-card" @click="$router.push(`/alerts/${alert.id}`)">
    <div class="alert-card-top">
      <span class="alert-card-code">{{ alert.code }}</span>
      <span class="alert-card-name">{{ alert.name }}</span>
      <RiskBadge :level="alert.risk_level" />
      <span style="flex:1"></span>
      <span class="confidence-bar" style="width:120px">
        <span class="bar-track">
          <span
            class="bar-fill"
            :class="confidenceClass"
            :style="{ width: (alert.confidence_score || 0) * 100 + '%' }"
          ></span>
        </span>
        <span class="bar-val">{{ ((alert.confidence_score || 0) * 100).toFixed(0) }}%</span>
      </span>
    </div>
    <div class="alert-card-reason" v-if="alert.trigger_reason">
      {{ alert.trigger_reason }}
    </div>
    <div class="alert-card-bottom">
      <span>{{ alert.alert_type }}</span>
      <span>·</span>
      <span v-if="alert.ts">{{ formatTime(alert.ts) }}</span>
      <span>·</span>
      <span>{{ formatAmount(alert.net_inflow_amount) }}</span>
      <span v-if="alert.ai_summary" style="margin-left:auto;color:var(--accent-blue)">AI ✓</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import RiskBadge from './RiskBadge.vue'
import type { Alert } from '@/stores/alerts'

const props = defineProps<{ alert: Alert }>()

const confidenceClass = computed(() => {
  const v = props.alert.confidence_score || 0
  if (v >= 0.7) return 'high'
  if (v >= 0.4) return 'medium'
  return 'low'
})

function formatTime(ts: string) {
  const d = new Date(ts)
  const mon = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  return `${mon}-${day} ${hh}:${mm}`
}

function formatAmount(v: number) {
  if (!v) return '--'
  const abs = Math.abs(v)
  const sign = v >= 0 ? '+' : '-'
  if (abs >= 1e8) return sign + (abs / 1e8).toFixed(2) + '亿'
  if (abs >= 1e4) return sign + (abs / 1e4).toFixed(0) + '万'
  return sign + abs.toFixed(0)
}
</script>
