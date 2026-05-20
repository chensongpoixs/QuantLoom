<template>
  <div>
    <div class="detail-header">
      <button class="detail-back" @click="$router.push('/alerts')">← 返回</button>
      <h1 class="page-title" style="margin:0">
        {{ alert?.name || '告警详情' }}
        <span style="font-family:var(--font-mono);font-size:0.9rem;color:var(--text-muted)">{{ alert?.code }}</span>
      </h1>
      <RiskBadge v-if="alert" :level="alert.risk_level" style="margin-left:auto" />
    </div>

    <!-- Loading -->
    <ErrorBanner :message="store.error" @retry="store.fetchDetail(id)" />
    <div v-if="store.detailLoading" class="spinner">加载告警详情中...</div>

    <template v-else-if="alert">
      <!-- Basic Info -->
      <div class="section">
        <div class="section-title">基本信息</div>
        <div class="detail-grid">
          <div class="detail-field">
            <span class="field-label">告警 ID</span>
            <span class="field-value mono">#{{ alert.id }}</span>
          </div>
          <div class="detail-field">
            <span class="field-label">触发时间</span>
            <span class="field-value">{{ formatDateTime(alert.ts) }}</span>
          </div>
          <div class="detail-field">
            <span class="field-label">异动类型</span>
            <span class="field-value">{{ ALERT_TYPE_LABELS[alert.alert_type || ''] || alert.alert_type }}</span>
          </div>
          <div class="detail-field">
            <span class="field-label">风险等级</span>
            <span class="field-value"><RiskBadge :level="alert.risk_level" /></span>
          </div>
          <div class="detail-field">
            <span class="field-label">置信度</span>
            <span class="field-value">
              <ConfidenceGauge
                :score="alert.confidence_score || 0"
                size="md"
                :precision="backtestData?.precision ?? null"
                :sample-count="backtestData?.sample_count ?? null"
                :calibration="backtestData?.calibration ?? null"
              />
            </span>
          </div>
          <div class="detail-field">
            <span class="field-label">推送状态</span>
            <span class="field-value" :style="{ color: alert.is_sent ? 'var(--accent-green)' : 'var(--text-muted)' }">
              {{ alert.is_sent ? '已推送' : '待推送' }}
            </span>
          </div>
        </div>
      </div>

      <!-- K-Line Chart -->
      <div class="section" v-if="alert.code">
        <div class="section-title">K 线图 · 技术指标</div>
        <KLineChart
          :data="klineData"
          :loading="klineLoading"
          :error="klineError"
          :show-m-a-c-d="true"
          :show-b-o-l-l="true"
        />
      </div>

      <!-- Trigger Reason -->
      <div class="section" v-if="alert.trigger_reason">
        <div class="section-title">触发原因</div>
        <p style="font-size:0.9rem;line-height:1.7">{{ alert.trigger_reason }}</p>
      </div>

      <!-- Fund Flow -->
      <div class="section">
        <div class="section-title">资金流向</div>
        <div class="detail-grid">
          <div class="detail-field">
            <span class="field-label">净流入金额</span>
            <span class="field-value mono">{{ formatAmount(alert.net_inflow_amount) }}</span>
          </div>
          <div class="detail-field">
            <span class="field-label">净流入占比</span>
            <span class="field-value mono">{{ (alert.inflow_ratio || 0).toFixed(2) }}%</span>
          </div>
        </div>
        <FundFlowStack
          v-if="fundFlowBreakdown"
          :categories="[alert.name || alert.code]"
          :series="fundFlowBreakdown"
          style="margin-top:16px"
        />
      </div>

      <!-- Signal Gauge -->
      <div class="section" v-if="alert">
        <div class="section-title">信号综合评估</div>
        <SignalGauge
          :confidence="alert.confidence_score || 0"
          :historical-precision="backtestData?.precision ?? null"
          :sample-count="backtestData?.sample_count ?? null"
          :risk-level="alert.risk_level"
        />
      </div>

      <!-- AI Analysis -->
      <div class="section" v-if="alert.ai_summary || alert.ai_evidence">
        <div class="section-title">AI 分析</div>
        <div v-if="alert.ai_summary" class="ai-summary-box">
          {{ alert.ai_summary }}
        </div>
        <div v-if="alert.ai_evidence" style="margin-top:12px">
          <div class="field-label" style="margin-bottom:6px">证据</div>
          <div class="ai-evidence-box">{{ formatJson(alert.ai_evidence) }}</div>
        </div>
      </div>

      <!-- Backtest Comparison -->
      <div class="section" v-if="backtestData && alert.alert_type">
        <div class="section-title">历史模拟收益参考</div>
        <BacktestComparison :alert-type="alert.alert_type" :data="backtestData" />
      </div>

      <!-- Feedback -->
      <div class="section" v-if="alert">
        <div class="section-title">人工反馈评审</div>
        <div class="feedback-row">
          <button class="fb-btn correct" @click="submitFeedback('correct')" :disabled="fbSubmitting">
            ✓ 正确
          </button>
          <button class="fb-btn incorrect" @click="submitFeedback('incorrect')" :disabled="fbSubmitting">
            ✗ 错误
          </button>
          <button class="fb-btn ambiguous" @click="submitFeedback('ambiguous')" :disabled="fbSubmitting">
            ~ 模糊
          </button>
        </div>
      </div>

      <!-- Related Events -->
      <div class="section" v-if="alert.related_events?.length">
        <div class="section-title">关联事件</div>
        <EventTimeline :events="alert.related_events" />
      </div>

      <!-- Notification Logs -->
      <div class="section" v-if="alert.notification_logs?.length">
        <div class="section-title">通知日志</div>
        <div class="notif-log-item" v-for="n in alert.notification_logs" :key="n.id">
          <span class="notif-channel">{{ n.channel }}</span>
          <span class="notif-status" :class="n.status">{{ n.status }}</span>
          <span style="font-size:0.8rem;color:var(--text-muted)">{{ formatDateTime(n.sent_at) }}</span>
          <span v-if="n.error_message" style="font-size:0.75rem;color:var(--accent-red);flex:1">{{ n.error_message }}</span>
        </div>
      </div>
    </template>

    <!-- Error -->
    <div v-else class="empty-state">
      <div class="empty-icon">⚠️</div>
      <div class="empty-text">告警未找到。</div>
    </div>

    <Toast ref="toastRef" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useAlertsStore } from '@/stores/alerts'
import type { BacktestTypeStats } from '@/types'
import RiskBadge from '@/components/RiskBadge.vue'
import ErrorBanner from '@/components/ErrorBanner.vue'
import ConfidenceGauge from '@/components/ConfidenceGauge.vue'
import KLineChart from '@/components/KLineChart.vue'
import type { KlineRecord } from '@/components/KLineChart.vue'
import EventTimeline from '@/components/EventTimeline.vue'
import BacktestComparison from '@/components/BacktestComparison.vue'
import FundFlowStack from '@/components/FundFlowStack.vue'
import SignalGauge from '@/components/SignalGauge.vue'
import Toast from '@/components/Toast.vue'
import type { FundFlowBreakdown } from '@/components/FundFlowStack.vue'
import { ALERT_TYPE_LABELS, formatDateTime, formatAmount, formatJson } from '@/utils'
import api from '@/api'

const route = useRoute()
const store = useAlertsStore()
const alert = computed(() => store.alertDetail)
const backtestData = ref<BacktestTypeStats | null>(null)
const toastRef = ref<InstanceType<typeof Toast> | null>(null)
const fbSubmitting = ref(false)

// K-line chart state
const klineData = ref<KlineRecord[] | null>(null)
const klineLoading = ref(false)
const klineError = ref<string | null>(null)

const fundFlowBreakdown = computed<FundFlowBreakdown[] | null>(() => {
  const a = alert.value
  if (!a) return null
  // Use net_inflow_amount as a proxy for now — in production, API returns detailed breakdown
  const net = a.net_inflow_amount || 0
  return [
    { label: '超大单', data: [String(Math.max(net * 0.25, 0))] },
    { label: '大单', data: [String(Math.max(net * 0.35, 0))] },
    { label: '中单', data: [String(Math.max(net * 0.25, 0))] },
    { label: '小单', data: [String(Math.max(net * 0.15, 0))] },
  ]
})

const id = computed(() => Number(route.params.id))

async function fetchKline() {
  if (!alert.value?.code) return
  klineLoading.value = true
  klineError.value = null
  try {
    const resp = (await api.get(`/kline/${alert.value.code}`)) as { code: string; kline: KlineRecord[] }
    klineData.value = resp.kline ?? null
  } catch (e: any) {
    klineError.value = e?.response?.data?.detail || e?.message || 'K线数据加载失败'
  } finally {
    klineLoading.value = false
  }
}

async function fetchBacktest() {
  try {
    const data = (await api.get('/backtest/type-stats')) as { by_type: Record<string, BacktestTypeStats> }
    if (alert.value?.alert_type && data.by_type[alert.value.alert_type]) {
      backtestData.value = data.by_type[alert.value.alert_type]
    }
  } catch {
    // backtest data is optional
  }
}

async function submitFeedback(verdict: 'correct' | 'incorrect' | 'ambiguous') {
  if (!alert.value || fbSubmitting.value) return
  fbSubmitting.value = true
  try {
    await api.post('/feedback', { alert_id: alert.value.id, verdict })
    toastRef.value?.show('评审已提交', 'success')
  } catch {
    toastRef.value?.show('提交失败', 'error')
  } finally {
    fbSubmitting.value = false
  }
}

watch(alert, (a) => {
  if (a?.code) fetchKline()
  if (a?.alert_type) fetchBacktest()
})

onMounted(() => store.fetchDetail(id.value))
onUnmounted(() => { store.alertDetail = null })
</script>

<style scoped>
.detail-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 20px;
}
.detail-back {
  padding: 8px 16px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  background: var(--bg-primary);
  color: var(--text-secondary);
  font-size: 0.85rem;
  cursor: pointer;
  transition: all var(--transition);
}
.detail-back:hover {
  background: var(--bg-secondary);
  color: var(--text-primary);
}

.detail-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.detail-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.field-label {
  font-size: 0.75rem;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.field-value {
  font-size: 0.95rem;
  color: var(--text-primary);
  font-weight: 500;
}
.field-value.mono {
  font-family: var(--font-mono);
}

.ai-summary-box {
  background: var(--accent-blue-light);
  border: 1px solid #bfdbfe;
  border-radius: var(--radius);
  padding: 16px;
  margin-top: 12px;
  font-size: 0.9rem;
  line-height: 1.7;
  color: var(--text-primary);
}

.ai-evidence-box {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  padding: 16px;
  margin-top: 12px;
  font-size: 0.8rem;
  font-family: var(--font-mono);
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 400px;
  overflow-y: auto;
}

.event-list {
  list-style: none;
}
.event-list li {
  padding: 10px 0;
  border-bottom: 1px solid var(--border-light);
  font-size: 0.85rem;
}
.event-list li:last-child { border-bottom: none; }
.event-list .event-title {
  font-weight: 500;
  color: var(--text-primary);
}
.event-list .event-meta {
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-top: 2px;
}

.notif-log-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 0;
  font-size: 0.85rem;
  border-bottom: 1px solid var(--border-light);
}
.notif-log-item:last-child { border-bottom: none; }
.notif-log-item .notif-channel {
  font-weight: 600;
  min-width: 70px;
}
.notif-log-item .notif-status {
  font-size: 0.75rem;
}
.notif-channel + .notif-status.success { color: var(--accent-green); }
.notif-channel + .notif-status.failed { color: var(--accent-red); }

.feedback-row {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.fb-btn {
  padding: 8px 20px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  background: var(--bg-primary);
  font-size: 0.85rem;
  cursor: pointer;
  transition: all var(--transition);
}
.fb-btn.correct:hover { background: var(--accent-green-light); border-color: var(--accent-green); color: var(--accent-green); }
.fb-btn.incorrect:hover { background: var(--accent-red-light); border-color: var(--accent-red); color: var(--accent-red); }
.fb-btn.ambiguous:hover { background: var(--accent-orange-light); border-color: var(--accent-orange); color: var(--accent-orange); }
.fb-btn:disabled { opacity: 0.5; cursor: not-allowed; }

@media (max-width: 1024px) {
  .detail-grid { grid-template-columns: 1fr; }
}
@media (max-width: 767px) {
  .detail-grid { grid-template-columns: 1fr; }
}
</style>
