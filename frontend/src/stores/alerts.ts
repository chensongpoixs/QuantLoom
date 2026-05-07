import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '@/api'

export interface Alert {
  id: number
  ts: string | null
  code: string
  name: string
  alert_type: string | null
  trigger_reason: string | null
  net_inflow_amount: number
  inflow_ratio: number
  confidence_score: number
  risk_level: string | null
  ai_summary: string | null
  is_sent: boolean
}

export interface AlertDetail extends Alert {
  ai_evidence: any
  created_at: string | null
  related_events: EventItem[]
  notification_logs: NotificationLog[]
}

export interface EventItem {
  id: number
  event_type: string
  title: string
  content: string | null
  source: string | null
  published_at: string | null
  sentiment_score: number | null
}

export interface NotificationLog {
  id: number
  channel: string
  status: string
  sent_at: string | null
  error_message: string | null
}

export interface SummaryStats {
  today: {
    total: number
    p1: number
    p2: number
    p3: number
    ai_analyzed: number
  }
  by_type: { type: string; count: number }[]
  week_avg_daily: number
}

export interface TrendData {
  dates: string[]
  totals: number[]
  by_type: Record<string, number[]>
}

export interface AlertsPage {
  total: number
  page: number
  page_size: number
  items: Alert[]
}

export const useAlertsStore = defineStore('alerts', () => {
  // -- state --
  const alerts = ref<Alert[]>([])
  const total = ref(0)
  const page = ref(1)
  const pageSize = ref(20)
  const loading = ref(false)

  const alertDetail = ref<AlertDetail | null>(null)
  const detailLoading = ref(false)

  const summary = ref<SummaryStats | null>(null)
  const summaryLoading = ref(false)

  const trend = ref<TrendData | null>(null)
  const trendLoading = ref(false)

  // filters
  const filterType = ref('')
  const filterRisk = ref('')
  const filterCode = ref('')
  const filterStart = ref('')
  const filterEnd = ref('')

  // -- actions --
  async function fetchAlerts() {
    loading.value = true
    try {
      const params: Record<string, any> = {
        page: page.value,
        page_size: pageSize.value,
      }
      if (filterType.value) params.alert_type = filterType.value
      if (filterRisk.value) params.risk_level = filterRisk.value
      if (filterCode.value) params.code = filterCode.value
      if (filterStart.value) params.start_date = filterStart.value
      if (filterEnd.value) params.end_date = filterEnd.value

      const data = (await api.get('/alerts', { params })) as any
      alerts.value = data.items
      total.value = data.total
    } finally {
      loading.value = false
    }
  }

  async function fetchDetail(id: number) {
    detailLoading.value = true
    try {
      alertDetail.value = (await api.get(`/alerts/${id}`)) as any
    } finally {
      detailLoading.value = false
    }
  }

  async function fetchSummary() {
    summaryLoading.value = true
    try {
      summary.value = (await api.get('/stats/summary')) as any
    } finally {
      summaryLoading.value = false
    }
  }

  async function fetchTrend(days = 7) {
    trendLoading.value = true
    try {
      trend.value = (await api.get('/stats/trend', { params: { days } })) as any
    } finally {
      trendLoading.value = false
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
    summary,
    summaryLoading,
    trend,
    trendLoading,
    filterType,
    filterRisk,
    filterCode,
    filterStart,
    filterEnd,
    fetchAlerts,
    fetchDetail,
    fetchSummary,
    fetchTrend,
    resetFilters,
  }
})
