<template>
  <div class="backtest-card">
    <div class="backtest-title">历史模拟收益 ({{ typeLabel }})</div>
    <div class="backtest-bars">
      <div class="backtest-item">
        <div class="backtest-label">T+1</div>
        <div class="backtest-bar-wrap">
          <div
            class="backtest-bar"
            :class="outcomeClass(data.outcome_1d)"
            :style="{ width: barWidth(data.outcome_1d) }"
          ></div>
          <span class="backtest-val" :class="outcomeClass(data.outcome_1d)">{{ fmtPct(data.outcome_1d) }}</span>
        </div>
      </div>
      <div class="backtest-item">
        <div class="backtest-label">T+3</div>
        <div class="backtest-bar-wrap">
          <div
            class="backtest-bar"
            :class="outcomeClass(data.outcome_3d)"
            :style="{ width: barWidth(data.outcome_3d) }"
          ></div>
          <span class="backtest-val" :class="outcomeClass(data.outcome_3d)">{{ fmtPct(data.outcome_3d) }}</span>
        </div>
      </div>
      <div class="backtest-item">
        <div class="backtest-label">T+5</div>
        <div class="backtest-bar-wrap">
          <div
            class="backtest-bar"
            :class="outcomeClass(data.outcome_5d)"
            :style="{ width: barWidth(data.outcome_5d) }"
          ></div>
          <span class="backtest-val" :class="outcomeClass(data.outcome_5d)">{{ fmtPct(data.outcome_5d) }}</span>
        </div>
      </div>
    </div>
    <div class="backtest-footer">
      <span>历史命中率: {{ (data.hit_rate * 100).toFixed(1) }}%</span>
      <span>样本数: {{ data.sample_count }}</span>
      <span v-if="data.benchmark_3d != null">vs 大盘: {{ fmtPct(data.benchmark_3d) }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ALERT_TYPE_LABELS } from '@/utils'

interface BacktestStats {
  outcome_1d: number | null
  outcome_3d: number | null
  outcome_5d: number | null
  hit_rate: number
  sample_count: number
  benchmark_3d?: number | null
}

const props = defineProps<{
  alertType: string
  data: BacktestStats
}>()

const typeLabel = computed(() => ALERT_TYPE_LABELS[props.alertType] || props.alertType)

function fmtPct(v: number | null): string {
  if (v == null) return '--'
  return (v > 0 ? '+' : '') + v.toFixed(2) + '%'
}

function outcomeClass(v: number | null): string {
  if (v == null) return ''
  return v >= 0 ? 'positive' : 'negative'
}

function barWidth(v: number | null): string {
  if (v == null) return '0%'
  return Math.min(Math.abs(v) * 10, 100) + '%'
}
</script>

<style scoped>
.backtest-card {
  padding: 16px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  background: var(--bg-card);
}

.backtest-title {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 12px;
}

.backtest-bars {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.backtest-item {
  display: flex;
  align-items: center;
  gap: 12px;
}

.backtest-label {
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text-muted);
  min-width: 32px;
}

.backtest-bar-wrap {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
}

.backtest-bar {
  height: 16px;
  border-radius: 3px;
  min-width: 2px;
  transition: width 0.3s ease;
}
.backtest-bar.positive { background: var(--accent-red); }
.backtest-bar.negative { background: var(--accent-green); }

.backtest-val {
  font-size: 0.85rem;
  font-weight: 600;
  font-family: var(--font-mono);
  min-width: 60px;
}
.backtest-val.positive { color: var(--accent-red); }
.backtest-val.negative { color: var(--accent-green); }

.backtest-footer {
  display: flex;
  gap: 20px;
  margin-top: 12px;
  font-size: 0.75rem;
  color: var(--text-muted);
}
</style>
