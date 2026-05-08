import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '@/api'
import type { NotificationLog } from '@/types'

export const useNotificationsStore = defineStore('notifications', () => {
  const items = ref<NotificationLog[]>([])
  const total = ref(0)
  const page = ref(1)
  const pageSize = ref(20)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchNotifications() {
    loading.value = true
    error.value = null
    try {
      const data = (await api.get('/notifications', {
        params: { page: page.value, page_size: pageSize.value },
      })) as { items: NotificationLog[]; total: number }
      items.value = data.items
      total.value = data.total
    } catch (e: unknown) {
      error.value = (e as Error).message || 'Failed to fetch notifications'
    } finally {
      loading.value = false
    }
  }

  return {
    items,
    total,
    page,
    pageSize,
    loading,
    error,
    fetchNotifications,
  }
})
