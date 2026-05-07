<template>
  <div>
    <div class="page-header-row">
      <h1 class="page-title">Dashboard</h1>
      <button class="btn-refresh" @click="refresh">Refresh</button>
    </div>

    <!-- Stats Grid -->
    <div v-if="store.summaryLoading && !store.summary">
      <div class="stats-grid">
        <div class="stat-card" v-for="i in 4" :key="i">
          <div class="skeleton" style="height:20px;width:60%;margin-bottom:12px"></div>
          <div class="skeleton" style="height:36px;width:40%"></div>
        </div>
      </div>
    </div>
    <StatsGrid v-else :stats="store.summary" />

    <!-- Trend Chart -->
    <div class="section">
      <div class="section-title">Alert Trend (7 days)</div>
      <div v-if="store.trendLoading && !store.trend" class="skeleton" style="height:320px"></div>
      <TrendChart v-else :data="store.trend" />
    </div>

    <!-- Top Alerts -->
    <div class="section">
      <div class="section-title">
        Recent High-Confidence Alerts
        <router-link to="/alerts" style="margin-left:auto;font-size:0.85rem;font-weight:400">View all →</router-link>
      </div>

      <div v-if="store.loading" class="spinner">Loading...</div>

      <table v-else-if="topAlerts.length" class="top-alerts-table">
        <thead>
          <tr>
            <th>Code</th>
            <th>Name</th>
            <th>Type</th>
            <th>Confidence</th>
            <th>Risk</th>
            <th>Time</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="a in topAlerts" :key="a.id" @click="$router.push(`/alerts/${a.id}`)">
            <td><strong>{{ a.code }}</strong></td>
            <td>{{ a.name }}</td>
            <td>{{ a.alert_type }}</td>
            <td>
              <div class="confidence-bar" style="width:80px">
                <span class="bar-track">
                  <span
                    class="bar-fill"
                    :class="a.confidence_score >= 0.7 ? 'high' : a.confidence_score >= 0.4 ? 'medium' : 'low'"
                    :style="{ width: (a.confidence_score || 0) * 100 + '%' }"
                  ></span>
                </span>
                <span class="bar-val">{{ ((a.confidence_score || 0) * 100).toFixed(0) }}%</span>
              </div>
            </td>
            <td><RiskBadge :level="a.risk_level" /></td>
            <td style="font-size:0.8rem;color:var(--text-muted)">{{ fmtTs(a.ts) }}</td>
          </tr>
        </tbody>
      </table>

      <div v-else class="empty-state">
        <div class="empty-icon">📊</div>
        <div class="empty-text">No alerts yet. Run the scanner to generate alerts.</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useAlertsStore } from '@/stores/alerts'
import StatsGrid from '@/components/StatsGrid.vue'
import TrendChart from '@/components/TrendChart.vue'
import RiskBadge from '@/components/RiskBadge.vue'

const store = useAlertsStore()

const topAlerts = computed(() => {
  return [...store.alerts]
    .sort((a, b) => (b.confidence_score || 0) - (a.confidence_score || 0))
    .slice(0, 5)
})

function fmtTs(ts: string | null) {
  if (!ts) return ''
  const d = new Date(ts)
  return `${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`
}

async function refresh() {
  await Promise.all([
    store.fetchSummary(),
    store.fetchTrend(7),
    store.fetchAlerts(),
  ])
}

onMounted(refresh)
</script>
