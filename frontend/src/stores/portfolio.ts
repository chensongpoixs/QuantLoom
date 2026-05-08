import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '@/api'
import type { PortfolioHolding } from '@/types'

export interface QuoteData {
  last_price: number | null
  pct_change: number | null
}

export const usePortfolioStore = defineStore('portfolio', () => {
  const holdings = ref<PortfolioHolding[]>([])
  const quotes = ref<Record<string, QuoteData>>({})
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchHoldings() {
    loading.value = true
    error.value = null
    try {
      const data = (await api.get('/portfolio')) as { items: PortfolioHolding[] }
      holdings.value = data.items
      if (data.items.length) await fetchQuotes(data.items.map((h) => h.code))
    } catch (e: unknown) {
      error.value = (e as Error).message || 'Failed to fetch portfolio'
    } finally {
      loading.value = false
    }
  }

  async function fetchQuotes(codes: string[]) {
    if (!codes.length) return
    try {
      const data = (await api.get('/quotes/batch', { params: { codes: codes.join(',') } })) as { quotes: Record<string, QuoteData> }
      quotes.value = data.quotes
    } catch {
      // quotes optional
    }
  }

  async function addHolding(req: { code: string; name?: string; shares: number; cost_price?: number }) {
    error.value = null
    try {
      await api.post('/portfolio', req)
      await fetchHoldings()
    } catch (e: unknown) {
      error.value = (e as Error).message || 'Failed to add holding'
      throw e
    }
  }

  async function removeHolding(id: number) {
    error.value = null
    try {
      await api.delete(`/portfolio/${id}`)
      holdings.value = holdings.value.filter((h) => h.id !== id)
    } catch (e: unknown) {
      error.value = (e as Error).message || 'Failed to remove holding'
    }
  }

  return {
    holdings,
    quotes,
    loading,
    error,
    fetchHoldings,
    addHolding,
    removeHolding,
  }
})
