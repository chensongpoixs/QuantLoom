/**
 * QuantLoom 共享格式化函数
 */

/** 时间戳 → MM-DD HH:mm */
export function formatTime(ts: string | null): string {
  if (!ts) return '--'
  const d = new Date(ts)
  if (isNaN(d.getTime())) return '--'
  const mon = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  return `${mon}-${day} ${hh}:${mm}`
}

/** 时间戳 → 完整中文日期 (YYYY年MM月DD日 HH:mm:ss) */
export function formatDateTime(ts: string | null): string {
  if (!ts) return '--'
  const d = new Date(ts)
  if (isNaN(d.getTime())) return '--'
  const y = d.getFullYear()
  const mon = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  const ss = String(d.getSeconds()).padStart(2, '0')
  return `${y}年${mon}月${day}日 ${hh}:${mm}:${ss}`
}

/** 金额格式化 (亿/万, 带正负号) */
export function formatAmount(v: number | null | undefined): string {
  if (v == null || v === 0) return '--'
  const abs = Math.abs(v)
  const sign = v >= 0 ? '+' : '-'
  if (abs >= 1e8) return sign + (abs / 1e8).toFixed(2) + '亿'
  if (abs >= 1e4) return sign + (abs / 1e4).toFixed(0) + '万'
  return sign + abs.toFixed(0)
}

/** JSON 美化输出 */
export function formatJson(v: unknown): string {
  if (!v) return '--'
  try {
    return JSON.stringify(v, null, 2)
  } catch {
    return String(v)
  }
}

/** 置信度 → 百分比字符串 (0.78 → "78%") */
export function formatConfidence(v: number | null | undefined): string {
  if (v == null) return '--'
  return (v * 100).toFixed(0) + '%'
}

/** 置信度等级 (high / medium / low) */
export function confidenceClass(v: number | null | undefined): string {
  const score = v || 0
  if (score >= 0.7) return 'high'
  if (score >= 0.4) return 'medium'
  return 'low'
}
