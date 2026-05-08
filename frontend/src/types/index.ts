export interface Alert {
  id: number
  ts: string | null
  code: string
  name: string
  alert_type: string | null
  trigger_reason: string | null
  net_inflow_amount: number
  inflow_ratio: number
  confidence_score: number
  risk_level: string | null
  ai_summary: string | null
  ai_evidence: unknown | null
  is_sent: boolean
}

export interface AlertDetail extends Alert {
  ai_evidence: unknown
  created_at: string | null
  related_events: EventItem[]
  notification_logs: NotificationLog[]
}

export interface EventItem {
  id: number
  event_type: string
  title: string
  content: string | null
  source: string | null
  published_at: string | null
  sentiment_score: number | null
}

export interface NotificationLog {
  id: number
  alert_id: number | null
  channel: string
  recipient: string | null
  status: string
  sent_at: string | null
  error_message: string | null
}

export interface SummaryStats {
  today: {
    total: number
    p1: number
    p2: number
    p3: number
    ai_analyzed: number
  }
  by_type: { type: string; count: number }[]
  week_avg_daily: number
}

export interface TrendData {
  dates: string[]
  totals: number[]
  by_type: Record<string, number[]>
}

export interface AlertsPage {
  total: number
  page: number
  page_size: number
  items: Alert[]
}

export interface PortfolioHolding {
  id: number
  code: string
  name: string
  shares: number
  cost_price: number
  created_at?: string
  updated_at?: string
}

export interface FundFlowItem {
  code: string
  name: string
  net_inflow: number
  inflow_ratio: number
}

export interface SectorHeatmapItem {
  sector: string
  alert_count: number
  avg_confidence: number
}

export interface FeedbackRequest {
  alert_id: number
  verdict: 'correct' | 'incorrect' | 'ambiguous'
  notes?: string
  reviewer?: string
}

export interface BacktestTypeStats {
  outcome_1d: number | null
  outcome_3d: number | null
  outcome_5d: number | null
  hit_rate: number
  sample_count: number
  precision: number | null
  calibration: number | null
}
