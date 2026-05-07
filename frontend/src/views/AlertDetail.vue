<template>
  <div>
    <div class="detail-header">
      <button class="detail-back" @click="$router.push('/alerts')">← Back</button>
      <h1 class="page-title" style="margin:0">
        {{ alert?.name || 'Alert Detail' }}
        <span style="font-family:var(--font-mono);font-size:0.9rem;color:var(--text-muted)">{{ alert?.code }}</span>
      </h1>
      <RiskBadge v-if="alert" :level="alert.risk_level" style="margin-left:auto" />
    </div>

    <!-- Loading -->
    <div v-if="store.detailLoading" class="spinner">Loading alert detail...</div>

    <template v-else-if="alert">
      <!-- Basic Info -->
      <div class="section">
        <div class="section-title">Basic Information</div>
        <div class="detail-grid">
          <div class="detail-field">
            <span class="field-label">Alert ID</span>
            <span class="field-value mono">#{{ alert.id }}</span>
          </div>
          <div class="detail-field">
            <span class="field-label">Trigger Time</span>
            <span class="field-value">{{ fmtDt(alert.ts) }}</span>
          </div>
          <div class="detail-field">
            <span class="field-label">Alert Type</span>
            <span class="field-value">{{ alert.alert_type }}</span>
          </div>
          <div class="detail-field">
            <span class="field-label">Risk Level</span>
            <span class="field-value"><RiskBadge :level="alert.risk_level" /></span>
          </div>
          <div class="detail-field">
            <span class="field-label">Confidence Score</span>
            <span class="field-value">
              <div class="confidence-bar" style="width:160px">
                <span class="bar-track">
                  <span
                    class="bar-fill"
                    :class="alert.confidence_score >= 0.7 ? 'high' : alert.confidence_score >= 0.4 ? 'medium' : 'low'"
                    :style="{ width: (alert.confidence_score || 0) * 100 + '%' }"
                  ></span>
                </span>
                <span class="bar-val">{{ ((alert.confidence_score || 0) * 100).toFixed(1) }}%</span>
              </div>
            </span>
          </div>
          <div class="detail-field">
            <span class="field-label">Push Status</span>
            <span class="field-value" :style="{ color: alert.is_sent ? 'var(--accent-green)' : 'var(--text-muted)' }">
              {{ alert.is_sent ? 'Sent' : 'Pending' }}
            </span>
          </div>
        </div>
      </div>

      <!-- Trigger Reason -->
      <div class="section" v-if="alert.trigger_reason">
        <div class="section-title">Trigger Reason</div>
        <p style="font-size:0.9rem;line-height:1.7">{{ alert.trigger_reason }}</p>
      </div>

      <!-- Fund Flow -->
      <div class="section">
        <div class="section-title">Fund Flow</div>
        <div class="detail-grid">
          <div class="detail-field">
            <span class="field-label">Net Inflow Amount</span>
            <span class="field-value mono">{{ fmtAmt(alert.net_inflow_amount) }}</span>
          </div>
          <div class="detail-field">
            <span class="field-label">Inflow Ratio</span>
            <span class="field-value mono">{{ (alert.inflow_ratio || 0).toFixed(2) }}%</span>
          </div>
        </div>
      </div>

      <!-- AI Analysis -->
      <div class="section" v-if="alert.ai_summary || alert.ai_evidence">
        <div class="section-title">AI Analysis</div>
        <div v-if="alert.ai_summary" class="ai-summary-box">
          {{ alert.ai_summary }}
        </div>
        <div v-if="alert.ai_evidence" style="margin-top:12px">
          <div class="field-label" style="margin-bottom:6px">Evidence</div>
          <div class="ai-evidence-box">{{ fmtJson(alert.ai_evidence) }}</div>
        </div>
      </div>

      <!-- Related Events -->
      <div class="section" v-if="alert.related_events?.length">
        <div class="section-title">Related Events</div>
        <ul class="event-list">
          <li v-for="e in alert.related_events" :key="e.id">
            <div class="event-title">{{ e.title }}</div>
            <div class="event-meta">
              {{ e.event_type }} · {{ e.source }} · {{ fmtDt(e.published_at) }}
              <span v-if="e.sentiment_score != null" style="margin-left:4px">
                (sentiment: {{ e.sentiment_score.toFixed(2) }})
              </span>
            </div>
          </li>
        </ul>
      </div>

      <!-- Notification Logs -->
      <div class="section" v-if="alert.notification_logs?.length">
        <div class="section-title">Notification Logs</div>
        <div class="notif-log-item" v-for="n in alert.notification_logs" :key="n.id">
          <span class="notif-channel">{{ n.channel }}</span>
          <span class="notif-status" :class="n.status">{{ n.status }}</span>
          <span style="font-size:0.8rem;color:var(--text-muted)">{{ fmtDt(n.sent_at) }}</span>
          <span v-if="n.error_message" style="font-size:0.75rem;color:var(--accent-red);flex:1">{{ n.error_message }}</span>
        </div>
      </div>
    </template>

    <!-- Error -->
    <div v-else class="empty-state">
      <div class="empty-icon">⚠️</div>
      <div class="empty-text">Alert not found.</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAlertsStore } from '@/stores/alerts'
import RiskBadge from '@/components/RiskBadge.vue'

const route = useRoute()
const store = useAlertsStore()
const alert = computed(() => store.alertDetail)

const id = computed(() => Number(route.params.id))

onMounted(() => store.fetchDetail(id.value))
onUnmounted(() => { store.alertDetail = null })

function fmtDt(ts: string | null) {
  if (!ts) return '--'
  return new Date(ts).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function fmtAmt(v: number) {
  if (!v) return '--'
  const abs = Math.abs(v)
  const sign = v >= 0 ? '+' : '-'
  if (abs >= 1e8) return sign + (abs / 1e8).toFixed(2) + '亿'
  if (abs >= 1e4) return sign + (abs / 1e4).toFixed(0) + '万'
  return sign + abs.toFixed(0)
}

function fmtJson(v: any) {
  if (typeof v === 'string') {
    try { return JSON.stringify(JSON.parse(v), null, 2) } catch { return v }
  }
  return JSON.stringify(v, null, 2)
}
</script>
