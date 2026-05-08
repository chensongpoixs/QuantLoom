/**
 * QuantLoom 共享常量
 * 集中管理告警类型、风险等级、图表颜色等映射
 */

/** 告警类型英文 → 中文标签 */
export const ALERT_TYPE_LABELS: Record<string, string> = {
  breakout: '放量上攻',
  accumulation: '底部吸筹',
  tail_chasing: '尾盘抢筹',
  event_driven: '事件驱动',
  sector_linked: '板块联动',
}

/** 告警类型下拉选项 (value/label 对) */
export const ALERT_TYPE_OPTIONS = Object.entries(ALERT_TYPE_LABELS).map(
  ([value, label]) => ({ value, label })
)

/** 风险等级列表 */
export const RISK_LEVELS = ['P1', 'P2', 'P3'] as const

/** ECharts 图表颜色映射 (alert_type → hex) */
export const CHART_COLOR_MAP: Record<string, string> = {
  breakout: '#2563eb',
  accumulation: '#16a34a',
  tail_chasing: '#f57c00',
  event_driven: '#8b5cf6',
  sector_linked: '#ec4899',
  unknown: '#6c757d',
}
