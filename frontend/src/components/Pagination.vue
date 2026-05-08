<template>
  <div class="pagination" v-if="totalPages > 1">
    <button :disabled="modelValue <= 1" @click="$emit('update:modelValue', 1)">«</button>
    <button :disabled="modelValue <= 1" @click="$emit('update:modelValue', modelValue - 1)">‹</button>

    <template v-for="p in visiblePages" :key="p">
      <button v-if="p !== '...'" :class="{ active: p === modelValue }" @click="$emit('update:modelValue', (p as number))">
        {{ p }}
      </button>
      <span v-else class="page-info">...</span>
    </template>

    <button :disabled="modelValue >= totalPages" @click="$emit('update:modelValue', modelValue + 1)">›</button>
    <button :disabled="modelValue >= totalPages" @click="$emit('update:modelValue', totalPages)">»</button>

    <span class="page-info">{{ modelValue }} / {{ totalPages }}</span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  modelValue: number
  total: number
  pageSize: number
}>()

defineEmits<{
  'update:modelValue': [value: number]
}>()

const totalPages = computed(() => Math.max(1, Math.ceil(props.total / props.pageSize)))

const visiblePages = computed(() => {
  const pages: (number | string)[] = []
  const tp = totalPages.value
  const cur = props.modelValue

  if (tp <= 7) {
    for (let i = 1; i <= tp; i++) pages.push(i)
    return pages
  }

  pages.push(1)
  if (cur > 3) pages.push('...')

  const start = Math.max(2, cur - 1)
  const end = Math.min(tp - 1, cur + 1)
  for (let i = start; i <= end; i++) pages.push(i)

  if (cur < tp - 2) pages.push('...')
  pages.push(tp)

  return pages
})
</script>

<style scoped>
.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  margin-top: 20px;
  flex-wrap: wrap;
}

.pagination button {
  padding: 8px 14px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  background: var(--bg-primary);
  color: var(--text-primary);
  font-size: 0.85rem;
  cursor: pointer;
  transition: all var(--transition);
}
.pagination button:hover:not(:disabled) {
  background: var(--accent-blue-light);
  border-color: var(--accent-blue);
  color: var(--accent-blue);
}
.pagination button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.pagination button.active {
  background: var(--accent-blue);
  color: #fff;
  border-color: var(--accent-blue);
}

.page-info {
  padding: 8px 12px;
  font-size: 0.8rem;
  color: var(--text-muted);
}
</style>
