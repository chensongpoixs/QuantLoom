<template>
  <div class="pagination" v-if="totalPages > 1">
    <button :disabled="modelValue <= 1" @click="$emit('update:modelValue', 1)">«</button>
    <button :disabled="modelValue <= 1" @click="$emit('update:modelValue', modelValue - 1)">‹</button>

    <template v-for="p in visiblePages" :key="p">
      <button v-if="p !== '...'" :class="{ active: p === modelValue }" @click="$emit('update:modelValue', p)">
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
