<template>
  <div v-if="message" class="error-banner">
    <span class="error-icon">⚠️</span>
    <span class="error-text">{{ message }}</span>
    <button class="error-retry" @click="$emit('retry')">重试</button>
  </div>
</template>

<script setup lang="ts">
defineProps<{ message: string | null }>()
defineEmits<{ retry: [] }>()
</script>

<style scoped>
.error-banner {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  margin-bottom: 16px;
  border: 1px solid #fecaca;
  border-radius: var(--radius);
  background: var(--accent-red-light);
  font-size: 0.85rem;
}

.error-icon {
  font-size: 1.1rem;
  flex-shrink: 0;
}

.error-text {
  flex: 1;
  color: var(--accent-red);
}

.error-retry {
  padding: 4px 14px;
  border: 1px solid var(--accent-red);
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--accent-red);
  font-size: 0.8rem;
  cursor: pointer;
  transition: all var(--transition);
  flex-shrink: 0;
}
.error-retry:hover {
  background: var(--accent-red);
  color: #fff;
}
</style>
