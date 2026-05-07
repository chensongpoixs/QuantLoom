<template>
  <div>
    <div class="page-header-row">
      <h1 class="page-title">告警列表</h1>
    </div>

    <!-- Filters -->
    <div class="filter-bar">
      <select v-model="store.filterType" @change="search">
        <option value="">全部类型</option>
        <option value="breakout">放量上攻</option>
        <option value="accumulation">底部吸筹</option>
        <option value="tail_chasing">尾盘抢筹</option>
        <option value="event_driven">事件驱动</option>
        <option value="sector_linked">板块联动</option>
      </select>

      <select v-model="store.filterRisk" @change="search">
        <option value="">全部风险</option>
        <option value="P1">P1</option>
        <option value="P2">P2</option>
        <option value="P3">P3</option>
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
    </div>

    <!-- Alert list -->
    <div v-if="store.loading" class="spinner">
      <span>加载告警中...</span>
    </div>

    <template v-else-if="store.alerts.length">
      <AlertCard
        v-for="alert in store.alerts"
        :key="alert.id"
        :alert="alert"
        @click="$router.push(`/alerts/${alert.id}`)"
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
import { onMounted } from 'vue'
import { useAlertsStore } from '@/stores/alerts'
import AlertCard from '@/components/AlertCard.vue'
import Pagination from '@/components/Pagination.vue'

const store = useAlertsStore()

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

onMounted(() => store.fetchAlerts())
</script>
