/// <reference types="vite/client" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}

interface QuantLoomConfig {
  apiBaseUrl: string
  appTitle: string
  timeout: number
  pageSize: number
  trendDays: number
}

declare global {
  interface Window {
    __QUANTLOOM_CONFIG__: QuantLoomConfig
  }
}

export {}
