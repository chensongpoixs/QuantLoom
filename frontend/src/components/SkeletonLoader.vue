<template>
  <div>
    <!-- Card variant: rounded box with title + value lines -->
    <div v-if="variant === 'card'" class="skeleton-card">
      <div class="skeleton skeleton-title"></div>
      <div class="skeleton skeleton-value"></div>
    </div>

    <!-- Chart variant: tall rectangle -->
    <div v-else-if="variant === 'chart'" class="skeleton skeleton-chart"></div>

    <!-- Table row variant -->
    <div v-else-if="variant === 'table-row'">
      <div v-for="i in count" :key="i" class="skeleton-row">
        <div class="skeleton skeleton-cell" v-for="j in 4" :key="j"></div>
      </div>
    </div>

    <!-- Text: inline text lines -->
    <div v-else>
      <div v-for="i in count" :key="i" class="skeleton skeleton-text" :style="{ width: widths[(i - 1) % widths.length] }"></div>
    </div>
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  variant?: 'text' | 'card' | 'chart' | 'table-row'
  count?: number
}>(), {
  variant: 'text',
  count: 3,
})

const widths = ['100%', '80%', '60%', '90%', '70%', '50%']
</script>

<style scoped>
.skeleton-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 20px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  background: var(--bg-card);
}

.skeleton-title {
  height: 16px;
  width: 50%;
}

.skeleton-value {
  height: 32px;
  width: 35%;
}

.skeleton-chart {
  height: 320px;
}

.skeleton-row {
  display: flex;
  gap: 16px;
  padding: 10px 0;
}

.skeleton-cell {
  height: 16px;
  flex: 1;
}

.skeleton-text {
  height: 14px;
  margin-bottom: 10px;
}
</style>
