/*
 * QuantLoom·量梭 前端配置
 *
 * 此文件独立于构建产物，部署后可直接修改，无需重新构建。
 * npm run build 时自动复制到 dist/ 目录。
 */
window.__QUANTLOOM_CONFIG__ = {
  // 后端 API 基地址 — 开发时 Vite 代理 /api，生产时可设为完整 URL
  apiBaseUrl: '',

  // 应用标题
  appTitle: 'QuantLoom·量梭',

  // 请求超时 (毫秒)
  timeout: 15000,

  // 默认每页条数
  pageSize: 20,

  // 趋势图默认天数
  trendDays: 7,
};
