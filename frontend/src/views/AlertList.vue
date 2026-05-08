<template>
  <div>
    <div class="page-header-row">
      <h1 class="page-title">告警列表</h1>
    </div>

    <!-- Filters -->
    <div class="filter-bar">
      <select v-model="store.filterType" @change="search">
        <option value="">全部类型</option>
        <option v-for="opt in ALERT_TYPE_OPTIONS" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
      </select>

      <select v-model="store.filterRisk" @change="search">
        <option value="">全部风险</option>
        <option v-for="r in RISK_LEVELS" :key="r" :value="r">{{ r }}</option>
      </select>

      <input
        v-model="store.filterCode"
        type="text"
        placeholder="代码 / 名称 ..."
        @keyup.enter="search"
        style="width:140px"
      />

      <input v-model="store.filterStart" type="date" @change="search" style="width:140px" />
      <input v-model="store.filterEnd" type="date" @change="search" style="width:140px" />

      <button class="btn-reset" @click="resetAll">重置</button>

      <span style="flex:1"></span>

      <button class="btn-view-toggle" @click="viewMode = viewMode === 'card' ? 'table' : 'card'">
        {{ viewMode === 'card' ? '📋 表格' : '🃏 卡片' }}
      </button>
      <button class="btn-export" @click="exportAlerts">📥 导出CSV</button>
    </div>

    <!-- Alert list -->
    <ErrorBanner :message="store.error" @retry="store.fetchAlerts()" />
    <div v-if="store.loading" class="spinner">
      <span>加载告警中...</span>
    </div>

    <template v-else-if="store.alerts.length">
      <!-- Card view -->
      <template v-if="viewMode === 'card'">
        <AlertCard
          v-for="alert in store.alerts"
          :key="alert.id"
          :alert="alert"
          @click="$router.push(`/alerts/${alert.id}`)"
        />
      </template>

      <!-- Table view -->
      <AlertTable
        v-else
        :alerts="store.alerts"
        @row-click="(id: number) => $router.push(`/alerts/${id}`)"
      />

      <Pagination
        v-model="store.page"
        :total="store.total"
        :page-size="store.pageSize"
        @update:model-value="onPageChange"
      />
    </template>

    <div v-else class="empty-state">
      <div class="empty-icon">🔍</div>
      <div class="empty-text">没有匹配筛选条件的告警。</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useAlertsStore } from '@/stores/alerts'
import AlertCard from '@/components/AlertCard.vue'
import AlertTable from '@/components/AlertTable.vue'
import Pagination from '@/components/Pagination.vue'
import ErrorBanner from '@/components/ErrorBanner.vue'
import { exportCSV, ALERT_TYPE_OPTIONS, RISK_LEVELS } from '@/utils'

const store = useAlertsStore()
const viewMode = ref<'card' | 'table'>('card')

async function search() {
  store.page = 1
  await store.fetchAlerts()
}

async function onPageChange(p: number) {
  store.page = p
  await store.fetchAlerts()
}

function resetAll() {
  store.resetFilters()
  store.fetchAlerts()
}

function exportAlerts() {
  exportCSV(store.alerts, `quantloom-alerts-${new Date().toISOString().slice(0, 10)}.csv`)
}

onMounted(() => store.fetchAlerts())
</script>

<style scoped>
.btn-view-toggle,
.btn-export {
  padding: 8px 14px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  background: var(--bg-primary);
  color: var(--text-secondary);
  font-size: 0.85rem;
  cursor: pointer;
  transition: all var(--transition);
  white-space: nowrap;
}
.btn-view-toggle:hover,
.btn-export:hover {
  background: var(--bg-secondary);
  color: var(--text-primary);
}
</style>
