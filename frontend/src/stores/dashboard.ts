import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '@/api'
import type { SummaryStats, TrendData, SectorHeatmapItem, FundFlowItem } from '@/types'
import type { BreadthData } from '@/components/MarketBreadthCard.vue'
import type { NorthFlowData } from '@/components/NorthFlowCard.vue'

export const useDashboardStore = defineStore('dashboard', () => {
  // -- state --
  const summary = ref<SummaryStats | null>(null)
  const summaryLoading = ref(false)

  const trend = ref<TrendData | null>(null)
  const trendLoading = ref(false)

  const sectors = ref<SectorHeatmapItem[]>([])
  const sectorsLoading = ref(false)

  const fundFlow = ref<{ inflows: FundFlowItem[]; outflows: FundFlowItem[] } | null>(null)
  const fundFlowLoading = ref(false)

  const breadth = ref<BreadthData | null>(null)
  const breadthLoading = ref(false)

  const northFlow = ref<NorthFlowData | null>(null)
  const northFlowLoading = ref(false)

  const error = ref<string | null>(null)

  // -- actions --
  async function fetchSummary() {
    summaryLoading.value = true
    error.value = null
    try {
      summary.value = (await api.get('/stats/summary')) as SummaryStats
    } catch (e: unknown) {
      error.value = (e as Error).message || 'Failed to fetch summary'
    } finally {
      summaryLoading.value = false
    }
  }

  async function fetchTrend(days = 7) {
    trendLoading.value = true
    error.value = null
    try {
      trend.value = (await api.get('/stats/trend', { params: { days } })) as TrendData
    } catch (e: unknown) {
      error.value = (e as Error).message || 'Failed to fetch trend'
    } finally {
      trendLoading.value = false
    }
  }

  async function fetchSectors() {
    sectorsLoading.value = true
    try {
      const data = (await api.get('/sectors/heatmap')) as { items: SectorHeatmapItem[] }
      sectors.value = data?.items ?? []
    } catch (e: unknown) {
      error.value = (e as Error).message || 'Failed to fetch sectors'
    } finally {
      sectorsLoading.value = false
    }
  }

  async function fetchFundFlow() {
    fundFlowLoading.value = true
    try {
      fundFlow.value = (await api.get('/fund-flow/top')) as { inflows: FundFlowItem[]; outflows: FundFlowItem[] }
    } catch (e: unknown) {
      error.value = (e as Error).message || 'Failed to fetch fund flow'
    } finally {
      fundFlowLoading.value = false
    }
  }

  async function fetchBreadth() {
    breadthLoading.value = true
    try {
      const data = (await api.get('/market/breadth', { params: { days: 1 } })) as { latest: BreadthData | null }
      breadth.value = data?.latest ?? null
    } catch {
      // breadth is optional
    } finally {
      breadthLoading.value = false
    }
  }

  async function fetchNorthFlow() {
    northFlowLoading.value = true
    try {
      northFlow.value = (await api.get('/north-flow/latest')) as NorthFlowData
    } catch {
      // north flow is optional
    } finally {
      northFlowLoading.value = false
    }
  }

  return {
    summary,
    summaryLoading,
    trend,
    trendLoading,
    sectors,
    sectorsLoading,
    fundFlow,
    fundFlowLoading,
    breadth,
    breadthLoading,
    northFlow,
    northFlowLoading,
    error,
    fetchSummary,
    fetchTrend,
    fetchSectors,
    fetchFundFlow,
    fetchBreadth,
    fetchNorthFlow,
  }
})
