import type { Alert } from '@/types'
import { ALERT_TYPE_LABELS } from './constants'

export function exportCSV(alerts: Alert[], filename = 'alerts.csv') {
  const headers = ['ID', '代码', '名称', '类型', '风险等级', '置信度', '触发原因', '净流入', '时间']
  const rows = alerts.map((a) => [
    a.id,
    a.code,
    a.name,
    ALERT_TYPE_LABELS[a.alert_type || ''] || a.alert_type || '',
    a.risk_level || '',
    ((a.confidence_score || 0) * 100).toFixed(1) + '%',
    (a.trigger_reason || '').replace(/,/g, '，'),
    a.net_inflow_amount?.toFixed(2) || '0',
    a.ts || '',
  ])

  const csv = [headers, ...rows]
    .map((row) => row.map((v) => `"${String(v)}"`).join(','))
    .join('\n')

  const bom = '\uFEFF'
  const blob = new Blob([bom + csv], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}
