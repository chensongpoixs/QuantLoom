import axios from 'axios'

const cfg = window.__QUANTLOOM_CONFIG__ || {} as any

const apiBaseUrl = cfg.apiBaseUrl || '/api'
const timeout = cfg.timeout || 15000

const api = axios.create({
  baseURL: apiBaseUrl,
  timeout,
  headers: { 'Content-Type': 'application/json' },
})

// 响应拦截器 — 统一提取 data
api.interceptors.response.use(
  (resp) => resp.data,
  (err) => {
    const msg = err.response?.data?.detail || err.message || 'Request failed'
    console.error(`[API] ${msg}`)
    return Promise.reject(err)
  },
)

export default api
