<template>
  <span
    class="risk-badge"
    :class="'risk-' + (level || 'P3')"
  >{{ level || 'P3' }}</span>
</template>

<script setup lang="ts">
defineProps<{ level: string | null }>()
</script>

<style scoped>
.risk-badge {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 12px;
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.3px;
  text-align: center;
  min-width: 32px;
}
.risk-P1 {
  background: var(--accent-red-light);
  color: var(--accent-red);
}
.risk-P2 {
  background: var(--accent-orange-light);
  color: var(--accent-orange);
}
.risk-P3 {
  background: var(--bg-secondary);
  color: var(--text-secondary);
}
</style>
