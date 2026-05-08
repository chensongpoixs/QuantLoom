<template>
  <div class="alert-table-wrapper">
    <table class="alert-table">
      <thead>
        <tr>
          <th>代码</th>
          <th>名称</th>
          <th class="hide-mobile">类型</th>
          <th>置信度</th>
          <th class="hide-mobile">风险</th>
          <th class="hide-mobile">净流入</th>
          <th>时间</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="a in alerts" :key="a.id" @click="$emit('rowClick', a.id)">
          <td class="col-code">{{ a.code }}</td>
          <td class="col-name">{{ a.name }}</td>
          <td class="hide-mobile">{{ ALERT_TYPE_LABELS[a.alert_type || ''] || a.alert_type }}</td>
          <td>
            <div class="confidence-bar" style="width:100px">
              <span class="bar-track">
                <span class="bar-fill" :class="confCls(a.confidence_score)" :style="{ width: (a.confidence_score || 0) * 100 + '%' }"></span>
              </span>
              <span class="bar-val">{{ ((a.confidence_score || 0) * 100).toFixed(0) }}%</span>
            </div>
          </td>
          <td class="hide-mobile"><RiskBadge :level="a.risk_level" /></td>
          <td class="hide-mobile col-amount" :class="a.net_inflow_amount >= 0 ? 'inflow' : 'outflow'">{{ formatAmount(a.net_inflow_amount) }}</td>
          <td class="col-time">{{ formatTime(a.ts) }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup lang="ts">
import type { Alert } from '@/types'
import RiskBadge from './RiskBadge.vue'
import { ALERT_TYPE_LABELS, formatTime, formatAmount, confidenceClass } from '@/utils'

defineProps<{ alerts: Alert[] }>()
defineEmits<{ rowClick: [id: number] }>()

function confCls(v: number | null | undefined): string {
  return confidenceClass(v)
}
</script>

<style scoped>
.alert-table-wrapper {
  overflow-x: auto;
}

.alert-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}

.alert-table th,
.alert-table td {
  padding: 10px 12px;
  text-align: left;
  border-bottom: 1px solid var(--border-light);
  white-space: nowrap;
}

.alert-table th {
  color: var(--text-secondary);
  font-weight: 600;
  background: var(--bg-secondary);
  position: sticky;
  top: 0;
}

.alert-table tbody tr {
  cursor: pointer;
  transition: background var(--transition);
}
.alert-table tbody tr:hover td {
  background: var(--bg-hover);
}

.col-code {
  font-weight: 700;
  font-family: var(--font-mono);
}

.col-name {
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.col-amount.inflow { color: var(--accent-red); }
.col-amount.outflow { color: var(--accent-green); }

.col-time {
  color: var(--text-muted);
  font-size: 0.8rem;
}

@media (max-width: 767px) {
  .hide-mobile { display: none; }
}
</style>
