<template>
  <Transition name="toast">
    <div v-if="visible" class="toast" :class="type">{{ message }}</div>
  </Transition>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const visible = ref(false)
const message = ref('')
const type = ref<'success' | 'error'>('success')
let timer: ReturnType<typeof setTimeout> | null = null

function show(msg: string, t: 'success' | 'error' = 'success') {
  if (timer) clearTimeout(timer)
  message.value = msg
  type.value = t
  visible.value = true
  timer = setTimeout(() => { visible.value = false }, 2500)
}

defineExpose({ show })
</script>

<style scoped>
.toast {
  position: fixed;
  bottom: 80px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 999;
  padding: 10px 24px;
  border-radius: var(--radius);
  font-size: 0.85rem;
  font-weight: 500;
  box-shadow: var(--shadow-md);
  white-space: nowrap;
}
.toast.success {
  background: var(--accent-green);
  color: #fff;
}
.toast.error {
  background: var(--accent-red);
  color: #fff;
}

.toast-enter-active { transition: all 0.3s ease; }
.toast-leave-active { transition: all 0.3s ease; }
.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(12px);
}
</style>
