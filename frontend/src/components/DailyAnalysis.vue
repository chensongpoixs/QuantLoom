<template>
  <div class="section">
    <div class="section-header">
      <span class="section-title">🤖 AI 每日洞察</span>
      <button class="btn-refresh" @click="fetchAnalysis" :disabled="loading">刷新分析</button>
    </div>

    <!-- status bar -->
    <div v-if="!loading && items.length > 0" class="analysis-status">
      今日共扫描 <strong>{{ totalToday }}</strong> 只股票，AI 已深度分析 <strong>{{ analyzedCount }}</strong> 只
    </div>

    <!-- loading -->
    <div v-if="loading" class="analysis-grid">
      <SkeletonLoader v-for="i in 4" :key="i" variant="card" />
    </div>

    <!-- error -->
    <ErrorBanner v-else-if="error" :message="error" @retry="fetchAnalysis" />

    <!-- cards -->
    <div v-else-if="items.length > 0" class="analysis-grid">
      <div
        v-for="a in items"
        :key="a.id"
        class="analysis-card"
        @click="$router.push(`/alerts/${a.id}`)"
      >
        <div class="card-top">
          <div class="card-stock">
            <span class="card-code">{{ a.code }}</span>
            <span class="card-name">{{ a.name }}</span>
          </div>
          <RiskBadge :level="a.risk_level" />
        </div>

        <div class="card-metrics">
          <ConfidenceGauge :score="a.confidence_score || 0" size="sm" />
          <span v-if="a.pct_change != null" class="card-pct" :class="a.pct_change >= 0 ? 'up' : 'down'">
            {{ a.pct_change >= 0 ? '+' : '' }}{{ a.pct_change.toFixed(2) }}%
          </span>
        </div>

        <p class="card-summary">{{ a.ai_summary }}</p>

        <div class="card-footer">
          <span class="card-type">{{ ALERT_TYPE_LABELS[a.alert_type || ''] || a.alert_type }}</span>
          <span v-if="actionLabel(a)" class="card-action" :class="'action-' + (a.ai_evidence?.action || '')">
            {{ actionLabel(a) }}
          </span>
        </div>
      </div>
    </div>

    <!-- empty -->
    <div v-else class="empty-state">
      <div class="empty-icon">🔬</div>
      <div class="empty-text">今日暂无 AI 分析结果。</div>
      <div class="empty-hint">请运行扫描器生成告警并触发 AI 分析：<br/><code>python scripts/run_scanner.py --top 10</code></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '@/api'
import { ALERT_TYPE_LABELS } from '@/utils'
import RiskBadge from '@/components/RiskBadge.vue'
import ConfidenceGauge from '@/components/ConfidenceGauge.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import ErrorBanner from '@/components/ErrorBanner.vue'

interface AnalysisAlert {
  id: number
  code: string
  name: string
  alert_type: string | null
  risk_level: string | null
  confidence_score: number | null
  pct_change: number | null
  trigger_reason: string | null
  ai_summary: string | null
  ai_evidence: { action?: string; reason_type?: string; risk_points?: string[]; evidence?: string[] } | null
}

const items = ref<AnalysisAlert[]>([])
const totalToday = ref(0)
const analyzedCount = ref(0)
const loading = ref(false)
const error = ref<string | null>(null)

const ACTION_MAP: Record<string, string> = {
  watch: '加入观察池',
  review: '需复核',
  ignore: '可忽略',
}

function actionLabel(a: AnalysisAlert): string | null {
  const act = a.ai_evidence?.action
  if (!act) return null
  return ACTION_MAP[act] || act
}

async function fetchAnalysis() {
  loading.value = true
  error.value = null
  try {
    const data = (await api.get('/analysis/daily', { params: { limit: 10 } })) as {
      total_today: number
      analyzed_count: number
      items: AnalysisAlert[]
    }
    totalToday.value = data?.total_today ?? 0
    analyzedCount.value = data?.analyzed_count ?? 0
    items.value = data?.items ?? []
  } catch (e: unknown) {
    error.value = (e as Error).message || '获取 AI 分析失败'
  } finally {
    loading.value = false
  }
}

onMounted(fetchAnalysis)
</script>

<style scoped>
.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.analysis-status {
  font-size: 0.82rem;
  color: var(--text-secondary);
  margin-bottom: 16px;
  padding: 8px 14px;
  background: var(--accent-blue-light);
  border-radius: var(--radius-sm);
}
.analysis-status strong {
  color: var(--accent-blue);
}

.analysis-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}

.analysis-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  padding: 16px;
  cursor: pointer;
  transition: all var(--transition);
}
.analysis-card:hover {
  border-color: var(--accent-blue);
  box-shadow: var(--shadow-sm);
}

.card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.card-stock {
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.card-code {
  font-weight: 700;
  font-family: var(--font-mono);
  font-size: 0.95rem;
  color: var(--text-primary);
}
.card-name {
  font-size: 0.82rem;
  color: var(--text-secondary);
}

.card-metrics {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 10px;
}
.card-pct {
  font-size: 0.95rem;
  font-weight: 700;
  font-family: var(--font-mono);
}
.card-pct.up { color: var(--accent-red); }
.card-pct.down { color: var(--accent-green); }

.card-summary {
  font-size: 0.85rem;
  line-height: 1.6;
  color: var(--text-primary);
  margin-bottom: 10px;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.card-footer {
  display: flex;
  align-items: center;
  gap: 10px;
}
.card-type {
  font-size: 0.72rem;
  padding: 2px 8px;
  border-radius: 10px;
  background: var(--bg-secondary);
  color: var(--text-muted);
}
.card-action {
  font-size: 0.72rem;
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 600;
}
.card-action.action-watch {
  background: var(--accent-blue-light);
  color: var(--accent-blue);
}
.card-action.action-review {
  background: var(--accent-orange-light);
  color: var(--accent-orange);
}
.card-action.action-ignore {
  background: var(--bg-secondary);
  color: var(--text-muted);
}

.empty-hint {
  font-size: 0.78rem;
  color: var(--text-muted);
  margin-top: 8px;
}
.empty-hint code {
  background: var(--bg-secondary);
  padding: 2px 6px;
  border-radius: 3px;
  font-family: var(--font-mono);
  font-size: 0.75rem;
}

@media (max-width: 767px) {
  .analysis-grid {
    grid-template-columns: 1fr;
  }
}
</style>
