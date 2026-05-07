<template>
  <span
    class="risk-badge"
    :class="'risk-' + (level || 'P3')"
  >{{ level || 'P3' }}</span>
</template>

<script setup lang="ts">
defineProps<{ level: string | null }>()
</script>
