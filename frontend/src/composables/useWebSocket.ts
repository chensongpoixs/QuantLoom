import { ref, onUnmounted, type Ref } from 'vue'

export interface WsAlert {
  code: string
  name: string
  alert_type: string
  confidence_score: number
  risk_level: string
  trigger_reason: string
  ai_summary?: string
}

type AlertHandler = (alert: WsAlert) => void

const handlers = new Set<AlertHandler>()
const connectedRefs = new Set<Ref<boolean>>()

let ws: WebSocket | null = null
let reconnectTimer: ReturnType<typeof setTimeout> | null = null
let pingTimer: ReturnType<typeof setInterval> | null = null
const MAX_RECONNECT_DELAY = 30_000
let reconnectDelay = 2_000

function getWsUrl(): string {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  return `${proto}//${host}/ws/alerts`
}

function connect() {
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
    return
  }

  try {
    ws = new WebSocket(getWsUrl())
  } catch {
    scheduleReconnect()
    return
  }

  ws.onopen = () => {
    reconnectDelay = 2_000
    connectedRefs.forEach((r) => { r.value = true })
    pingTimer = setInterval(() => {
      if (ws?.readyState === WebSocket.OPEN) {
        ws.send('ping')
      }
    }, 30_000)
  }

  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data)
      if (msg.type === 'new_alert' && msg.data) {
        for (const handler of handlers) {
          handler(msg.data)
        }
      }
    } catch {
      // ignore malformed messages
    }
  }

  ws.onclose = () => {
    connectedRefs.forEach((r) => { r.value = false })
    if (pingTimer) {
      clearInterval(pingTimer)
      pingTimer = null
    }
    scheduleReconnect()
  }

  ws.onerror = () => {
    ws?.close()
  }
}

function scheduleReconnect() {
  if (reconnectTimer) return
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null
    reconnectDelay = Math.min(reconnectDelay * 1.5, MAX_RECONNECT_DELAY)
    connect()
  }, reconnectDelay)
}

function disconnect() {
  if (reconnectTimer) {
    clearTimeout(reconnectTimer)
    reconnectTimer = null
  }
  if (pingTimer) {
    clearInterval(pingTimer)
    pingTimer = null
  }
  if (ws) {
    ws.onclose = null // prevent reconnect
    ws.close()
    ws = null
  }
}

export function useWebSocket() {
  const connected = ref(false)

  // Register connected ref so connect()/close() can update it
  connectedRefs.add(connected)
  if (ws?.readyState === WebSocket.OPEN) {
    connected.value = true
  }

  function onAlert(handler: AlertHandler) {
    handlers.add(handler)
    if (handlers.size === 1) {
      connect()
    }
    return () => {
      handlers.delete(handler)
      if (handlers.size === 0) {
        disconnect()
      }
    }
  }

  onUnmounted(() => {
    connectedRefs.delete(connected)
  })

  return { connected, onAlert }
}
