<template>
  <header class="app-header">
    <div class="header-inner">
      <router-link to="/" class="header-brand">
        <span class="brand-icon">Q</span>
        <span>QuantLoom·量梭</span>
      </router-link>
      <button class="menu-toggle" @click="open = !open" aria-label="Menu">
        {{ open ? '✕' : '☰' }}
      </button>
      <nav class="header-nav" :class="{ open }">
        <router-link to="/" @click="open = false">仪表盘</router-link>
        <router-link to="/alerts" @click="open = false">告警列表</router-link>
        <router-link to="/portfolio" @click="open = false">持仓</router-link>
        <router-link to="/notifications" @click="open = false" class="notif-nav-link">
          通知
          <span v-if="newNotifCount > 0" class="notif-badge">{{ newNotifCount > 99 ? '99+' : newNotifCount }}</span>
        </router-link>
      </nav>
    </div>
  </header>

  <!-- New alert slide-down banner -->
  <Transition name="slide">
    <div v-if="showAlertBanner" class="alert-banner" @click="goAlerts">
      <span class="alert-banner-dot blink"></span>
      <span class="alert-banner-text">发现 {{ newP1Count }} 个新的 P1 高风险信号</span>
      <button class="alert-banner-close" @click.stop="dismissBanner">✕</button>
    </div>
  </Transition>

  <!-- Mobile bottom tab bar: only visible < 768px -->
  <nav class="bottom-tabs" aria-label="底部导航">
    <router-link to="/" class="bottom-tab" :class="{ active: $route.path === '/' }">
      <span class="tab-icon">📈</span>
      <span class="tab-label">行情</span>
    </router-link>
    <router-link to="/alerts" class="bottom-tab" :class="{ active: $route.path.startsWith('/alerts') }">
      <span class="tab-icon">🚨</span>
      <span class="tab-label">信号</span>
    </router-link>
    <router-link to="/portfolio" class="bottom-tab" :class="{ active: $route.path === '/portfolio' }">
      <span class="tab-icon">💼</span>
      <span class="tab-label">持仓</span>
    </router-link>
    <router-link to="/notifications" class="bottom-tab" :class="{ active: $route.path === '/notifications' }">
      <span class="tab-icon">🔔</span>
      <span class="tab-label">通知</span>
      <span v-if="newNotifCount > 0" class="bottom-tab-badge">{{ newNotifCount > 99 ? '99+' : newNotifCount }}</span>
    </router-link>
  </nav>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '@/api'

const route = useRoute()
const router = useRouter()
const open = ref(false)

// Notification polling
const newNotifCount = ref(0)
let pollTimer: ReturnType<typeof setInterval> | null = null

// New P1 alert banner
const showAlertBanner = ref(false)
const newP1Count = ref(0)
let prevAlertTotal = 0

async function pollNotifications() {
  try {
    const data = (await api.get('/notifications', { params: { page_size: 1 } })) as { total: number }
    newNotifCount.value = data?.total ?? 0
  } catch {
    // silent fail
  }
}

async function checkNewAlerts() {
  try {
    const data = (await api.get('/alerts', { params: { page_size: 1, risk_level: 'P1' } })) as {
      total: number
    }
    if (data && prevAlertTotal > 0 && data.total > prevAlertTotal) {
      newP1Count.value = data.total - prevAlertTotal
      showAlertBanner.value = true
      // Auto-dismiss after 8 seconds
      setTimeout(() => { showAlertBanner.value = false }, 8000)
    }
    if (data) prevAlertTotal = data.total
  } catch {
    // silent
  }
}

function dismissBanner() {
  showAlertBanner.value = false
}

function goAlerts() {
  showAlertBanner.value = false
  router.push('/alerts')
}

function startPolling() {
  pollNotifications()
  checkNewAlerts()
  pollTimer = setInterval(() => {
    pollNotifications()
    checkNewAlerts()
  }, 30_000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

// Reset badge when user navigates to notifications page
watch(
  () => route.path,
  (path) => {
    if (path === '/notifications') {
      newNotifCount.value = 0
    }
  },
)

onMounted(startPolling)
onUnmounted(stopPolling)
</script>

<style scoped>
.notif-nav-link {
  position: relative;
}

.notif-badge {
  position: absolute;
  top: 2px;
  right: 2px;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  background: var(--accent-red);
  color: #fff;
  font-size: 0.65rem;
  font-weight: 700;
  border-radius: 9px;
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
}

/* Alert banner */
.alert-banner {
  position: fixed;
  top: 56px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 200;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 20px;
  background: #fff;
  border: 1px solid var(--accent-red);
  border-radius: var(--radius);
  box-shadow: var(--shadow-md);
  cursor: pointer;
  max-width: 420px;
  width: calc(100% - 32px);
}

.alert-banner-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--accent-red);
  flex-shrink: 0;
}

.alert-banner-text {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--accent-red);
  flex: 1;
}

.alert-banner-close {
  background: none;
  border: none;
  font-size: 1rem;
  cursor: pointer;
  color: var(--text-muted);
  padding: 2px;
}

/* Blink animation — 3 flashes then stop */
@keyframes blink {
  0%, 50%, 100% { opacity: 1; }
  25%, 75% { opacity: 0.3; }
}

.alert-banner-dot.blink {
  animation: blink 0.6s ease 3;
  animation-fill-mode: forwards;
}

/* Slide transition */
.slide-enter-active { transition: all 0.4s ease; }
.slide-leave-active { transition: all 0.3s ease; }
.slide-enter-from {
  opacity: 0;
  transform: translateX(-50%) translateY(-20px);
}
.slide-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(-20px);
}

/* Bottom tab bar — mobile only */
.bottom-tabs {
  display: none;
}

@media (max-width: 767px) {
  .bottom-tabs {
    display: flex;
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    z-index: 100;
    background: var(--bg-primary);
    border-top: 1px solid var(--border-color);
    box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.06);
    justify-content: space-around;
    align-items: center;
    height: 56px;
    padding-bottom: env(safe-area-inset-bottom, 0);
  }

  .bottom-tab {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
    padding: 4px 12px;
    color: var(--text-muted);
    font-size: 0.7rem;
    text-decoration: none;
    position: relative;
  }

  .bottom-tab.active {
    color: var(--accent-blue);
  }

  .tab-icon {
    font-size: 1.2rem;
  }

  .tab-label {
    font-weight: 500;
  }

  .bottom-tab-badge {
    position: absolute;
    top: 0;
    right: 4px;
    min-width: 16px;
    height: 16px;
    padding: 0 4px;
    background: var(--accent-red);
    color: #fff;
    font-size: 0.6rem;
    font-weight: 700;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    line-height: 1;
  }
}
</style>
