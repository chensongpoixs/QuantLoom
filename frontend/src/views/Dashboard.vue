<template>
  <div>
    <div class="page-header-row">
      <h1 class="page-title">仪表盘</h1>
      <button class="btn-refresh" @click="refresh">刷新</button>
    </div>

    <!-- AI Daily Analysis -->
    <DailyAnalysis />

    <!-- Stats Grid -->
    <ErrorBanner :message="dashStore.error" @retry="dashStore.fetchSummary()" />
    <div v-if="dashStore.summaryLoading && !dashStore.summary" class="stats-grid">
      <SkeletonLoader v-for="i in 4" :key="i" variant="card" />
    </div>
    <StatsGrid v-else :stats="dashStore.summary" />

    <!-- Trend Chart -->
    <div class="section">
      <div class="section-title">告警趋势（近7天）</div>
      <SkeletonLoader v-if="dashStore.trendLoading && !dashStore.trend" variant="chart" />
      <TrendChart v-else :data="dashStore.trend" :variant="isMobile ? 'sparkline' : 'full'" />
    </div>

    <!-- Fund Flow Top10 -->
    <div class="section">
      <div class="section-title">主力资金流向 Top10</div>
      <SkeletonLoader v-if="dashStore.fundFlowLoading && !dashStore.fundFlow" variant="chart" />
      <FundFlowBar
        v-else-if="dashStore.fundFlow"
        :inflows="dashStore.fundFlow.inflows"
        :outflows="dashStore.fundFlow.outflows"
      />
      <div v-else class="empty-state" style="padding:40px">
        <div class="empty-text">暂无资金流数据。</div>
      </div>
    </div>

    <!-- Sector Heatmap -->
    <div class="section">
      <div class="section-title">板块异动热力图</div>
      <SkeletonLoader v-if="dashStore.sectorsLoading && !dashStore.sectors.length" variant="chart" />
      <SectorHeatmap v-else-if="dashStore.sectors.length" :data="dashStore.sectors" />
      <div v-else class="empty-state" style="padding:40px">
        <div class="empty-text">暂无板块数据。</div>
      </div>
    </div>

    <!-- Top Alerts -->
    <div class="section">
      <div class="section-title">
        最近高置信度告警
        <router-link to="/alerts" style="margin-left:auto;font-size:0.85rem;font-weight:400">查看全部 →</router-link>
      </div>

      <div v-if="alertsStore.loading" class="spinner">加载中...</div>

      <table v-else-if="topAlerts.length" class="top-alerts-table">
        <thead>
          <tr>
            <th>代码</th>
            <th>名称</th>
            <th>类型</th>
            <th>置信度</th>
            <th>风险</th>
            <th>时间</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="a in topAlerts" :key="a.id" @click="$router.push(`/alerts/${a.id}`)">
            <td><strong>{{ a.code }}</strong></td>
            <td>{{ a.name }}</td>
            <td>{{ ALERT_TYPE_LABELS[a.alert_type || ''] || a.alert_type }}</td>
            <td><ConfidenceGauge :score="a.confidence_score || 0" size="sm" /></td>
            <td><RiskBadge :level="a.risk_level" /></td>
            <td style="font-size:0.8rem;color:var(--text-muted)">{{ formatTime(a.ts) }}</td>
          </tr>
        </tbody>
      </table>

      <div v-else class="empty-state">
        <div class="empty-icon">📊</div>
        <div class="empty-text">暂无告警数据，请运行扫描器生成告警。</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useAlertsStore } from '@/stores/alerts'
import { useDashboardStore } from '@/stores/dashboard'
import { ALERT_TYPE_LABELS, formatTime } from '@/utils'
import StatsGrid from '@/components/StatsGrid.vue'
import TrendChart from '@/components/TrendChart.vue'
import RiskBadge from '@/components/RiskBadge.vue'
import ErrorBanner from '@/components/ErrorBanner.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import ConfidenceGauge from '@/components/ConfidenceGauge.vue'
import FundFlowBar from '@/components/FundFlowBar.vue'
import SectorHeatmap from '@/components/SectorHeatmap.vue'
import DailyAnalysis from '@/components/DailyAnalysis.vue'

const alertsStore = useAlertsStore()
const dashStore = useDashboardStore()

// Mobile detection for sparkline chart variant
const isMobile = ref(window.innerWidth < 768)
function onResize() {
  isMobile.value = window.innerWidth < 768
}
window.addEventListener('resize', onResize)
onUnmounted(() => window.removeEventListener('resize', onResize))

const topAlerts = computed(() => {
  const list = alertsStore.alerts ?? []
  return [...list]
    .sort((a, b) => (b.confidence_score || 0) - (a.confidence_score || 0))
    .slice(0, 10)
})


async function refresh() {
  await Promise.all([
    dashStore.fetchSummary(),
    dashStore.fetchTrend(7),
    dashStore.fetchSectors(),
    dashStore.fetchFundFlow(),
    alertsStore.fetchAlerts(),
  ])
}

onMounted(refresh)
</script>

<style scoped>
.top-alerts-table {
  width: 100%;
  border-collapse: collapse;
}
.top-alerts-table th,
.top-alerts-table td {
  padding: 10px 12px;
  text-align: left;
  border-bottom: 1px solid var(--border-light);
  font-size: 0.85rem;
}
.top-alerts-table th {
  color: var(--text-secondary);
  font-weight: 600;
  background: var(--bg-secondary);
}
.top-alerts-table tr {
  cursor: pointer;
  transition: background var(--transition);
}
.top-alerts-table tr:hover td {
  background: var(--bg-hover);
}

@media (max-width: 767px) {
  .top-alerts-table th:nth-child(3),
  .top-alerts-table td:nth-child(3),
  .top-alerts-table th:nth-child(5),
  .top-alerts-table td:nth-child(5) {
    display: none;
  }
}
</style>
