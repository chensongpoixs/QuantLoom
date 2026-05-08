import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './styles/global.css'
import './utils/echarts-theme'
import { BANNER_TEXT } from './utils/banner'

// QuantLoom·量梭 — 浏览器控制台 ASCII 横幅
console.log('%c' + BANNER_TEXT, 'color: #2563eb; font-weight: bold;')

// Register service worker for PWA offline support
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js').catch(() => {})
}

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')
