import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '@/api'
import type { Alert, AlertDetail } from '@/types'

export type { Alert, AlertDetail }

export const useAlertsStore = defineStore('alerts', () => {
  // -- state --
  const alerts = ref<Alert[]>([])
  const total = ref(0)
  const page = ref(1)
  const pageSize = ref(20)
  const loading = ref(false)

  const alertDetail = ref<AlertDetail | null>(null)
  const detailLoading = ref(false)

  const error = ref<string | null>(null)

  // filters
  const filterType = ref('')
  const filterRisk = ref('')
  const filterCode = ref('')
  const filterStart = ref('')
  const filterEnd = ref('')

  // -- actions --
  async function fetchAlerts() {
    loading.value = true
    error.value = null
    try {
      const params: Record<string, unknown> = {
        page: page.value,
        page_size: pageSize.value,
      }
      if (filterType.value) params.alert_type = filterType.value
      if (filterRisk.value) params.risk_level = filterRisk.value
      if (filterCode.value) params.code = filterCode.value
      if (filterStart.value) params.start_date = filterStart.value
      if (filterEnd.value) params.end_date = filterEnd.value

      const data = (await api.get('/alerts', { params })) as { items: Alert[]; total: number }
      alerts.value = data.items
      total.value = data.total
    } catch (e: unknown) {
      error.value = (e as Error).message || 'Failed to fetch alerts'
    } finally {
      loading.value = false
    }
  }

  async function fetchDetail(id: number) {
    detailLoading.value = true
    error.value = null
    try {
      alertDetail.value = (await api.get(`/alerts/${id}`)) as AlertDetail
    } catch (e: unknown) {
      error.value = (e as Error).message || 'Failed to fetch alert detail'
    } finally {
      detailLoading.value = false
    }
  }

  function resetFilters() {
    filterType.value = ''
    filterRisk.value = ''
    filterCode.value = ''
    filterStart.value = ''
    filterEnd.value = ''
    page.value = 1
  }

  return {
    alerts,
    total,
    page,
    pageSize,
    loading,
    alertDetail,
    detailLoading,
    error,
    filterType,
    filterRisk,
    filterCode,
    filterStart,
    filterEnd,
    fetchAlerts,
    fetchDetail,
    resetFilters,
  }
})
