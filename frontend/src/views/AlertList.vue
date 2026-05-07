<template>
  <div>
    <div class="page-header-row">
      <h1 class="page-title">Alerts</h1>
    </div>

    <!-- Filters -->
    <div class="filter-bar">
      <select v-model="store.filterType" @change="search">
        <option value="">All Types</option>
        <option value="breakout">Breakout</option>
        <option value="accumulation">Accumulation</option>
        <option value="tail_chasing">Tail Chasing</option>
        <option value="event_driven">Event Driven</option>
        <option value="sector_linked">Sector Linked</option>
      </select>

      <select v-model="store.filterRisk" @change="search">
        <option value="">All Risks</option>
        <option value="P1">P1</option>
        <option value="P2">P2</option>
        <option value="P3">P3</option>
      </select>

      <input
        v-model="store.filterCode"
        type="text"
        placeholder="Code / Name ..."
        @keyup.enter="search"
        style="width:140px"
      />

      <input v-model="store.filterStart" type="date" @change="search" style="width:140px" />
      <input v-model="store.filterEnd" type="date" @change="search" style="width:140px" />

      <button class="btn-reset" @click="resetAll">Reset</button>
    </div>

    <!-- Alert list -->
    <div v-if="store.loading" class="spinner">
      <span>Loading alerts...</span>
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
      <div class="empty-text">No alerts found matching your filters.</div>
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
