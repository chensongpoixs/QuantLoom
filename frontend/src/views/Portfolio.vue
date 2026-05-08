<template>
  <div>
    <div class="page-header-row">
      <h1 class="page-title">我的持仓</h1>
      <button class="btn-refresh" @click="store.fetchHoldings()">刷新</button>
    </div>

    <ErrorBanner :message="store.error" @retry="store.fetchHoldings()" />

    <!-- Add form -->
    <div class="section">
      <div class="section-title">添加持仓</div>
      <form class="add-form" @submit.prevent="onAdd">
        <div class="search-wrap">
          <input
            v-model="searchQuery"
            type="text"
            placeholder="搜索股票代码或名称..."
            style="width:220px"
            @input="onSearch"
            @focus="showDropdown = searchResults.length > 0"
            @blur="hideDropdown"
          />
          <ul v-if="showDropdown && searchResults.length" class="search-dropdown">
            <li
              v-for="s in searchResults"
              :key="s.code"
              @mousedown.prevent="selectStock(s)"
            >
              <span class="search-code">{{ s.code }}</span>
              <span class="search-name">{{ s.name }}</span>
              <span class="search-industry">{{ s.industry || '' }}</span>
            </li>
          </ul>
        </div>
        <input v-model="form.shares" type="number" placeholder="持仓股数" required style="width:120px" min="0" />
        <input v-model="form.cost_price" type="number" placeholder="成本价 (选填)" style="width:120px" step="0.01" min="0" />
        <button type="submit" class="btn-submit" :disabled="adding || !form.code">添加</button>
      </form>
    </div>

    <!-- Holdings list -->
    <div v-if="store.loading" class="spinner">加载中...</div>

    <table v-else-if="store.holdings.length" class="holdings-table">
      <thead>
        <tr>
          <th>代码</th>
          <th>名称</th>
          <th>持仓股数</th>
          <th>成本价</th>
          <th>最新价</th>
          <th>涨跌幅</th>
          <th>浮动盈亏</th>
          <th>异动</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <template v-for="h in store.holdings" :key="h.id">
          <tr
            :class="{ 'has-alert': alertCodes.has(h.code), 'expanded': expandedCode === h.code }"
            @click="toggleExpand(h.code)"
            style="cursor:pointer"
          >
            <td class="col-code">{{ h.code }}</td>
            <td>{{ h.name }}</td>
            <td class="col-num">{{ h.shares.toLocaleString() }}</td>
            <td class="col-num">{{ h.cost_price ? h.cost_price.toFixed(2) : '--' }}</td>
            <td class="col-num">{{ quotePrice(h.code) }}</td>
            <td class="col-num" :class="quoteChgClass(h.code)">{{ quoteChg(h.code) }}</td>
            <td class="col-num" :class="pnlClass(h)">{{ fmtPnl(h) }}</td>
            <td>
              <span v-if="alertCodes.has(h.code)" class="alert-dot" title="今日有异动">🔴</span>
              <span v-else class="no-alert">--</span>
            </td>
            <td>
              <button class="btn-delete" @click.stop="onDelete(h.id, h.name || h.code)">删除</button>
            </td>
          </tr>
          <tr v-if="expandedCode === h.code && alertSummaries[h.code]" class="expand-row">
            <td :colspan="9">
              <div class="expand-content">
                <div class="expand-title">AI 异动分析</div>
                <p>{{ alertSummaries[h.code] }}</p>
                <router-link :to="`/alerts/${alertIds[h.code]}`" class="expand-link">查看详情 →</router-link>
              </div>
            </td>
          </tr>
        </template>
      </tbody>
    </table>

    <div v-else class="empty-state">
      <div class="empty-icon">📂</div>
      <div class="empty-text">暂无持仓记录，请添加股票。</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { usePortfolioStore } from '@/stores/portfolio'
import ErrorBanner from '@/components/ErrorBanner.vue'
import api from '@/api'

interface StockSearchItem {
  code: string
  name: string
  exchange: string
  industry: string | null
}

const store = usePortfolioStore()
const adding = ref(false)

// Stock search
const searchQuery = ref('')
const searchResults = ref<StockSearchItem[]>([])
const showDropdown = ref(false)
let searchTimer: ReturnType<typeof setTimeout> | null = null

// Alert association
const alertCodes = ref<Set<string>>(new Set())
const alertSummaries = ref<Record<string, string>>({})
const alertIds = ref<Record<string, number>>({})
const expandedCode = ref<string | null>(null)

const form = reactive({
  code: '',
  name: '',
  shares: 0,
  cost_price: undefined as number | undefined,
})

function onSearch() {
  if (searchTimer) clearTimeout(searchTimer)
  const q = searchQuery.value.trim()
  if (!q) {
    searchResults.value = []
    showDropdown.value = false
    return
  }
  searchTimer = setTimeout(async () => {
    try {
      const data = (await api.get('/stocks/search', { params: { q, limit: 8 } })) as { results: StockSearchItem[] }
      searchResults.value = data.results
      showDropdown.value = data.results.length > 0
    } catch {
      searchResults.value = []
    }
  }, 200)
}

function selectStock(s: StockSearchItem) {
  form.code = s.code
  form.name = s.name
  searchQuery.value = `${s.code} ${s.name}`
  showDropdown.value = false
  searchResults.value = []
}

function hideDropdown() {
  setTimeout(() => { showDropdown.value = false }, 150)
}

async function fetchAlertCodes() {
  try {
    const data = (await api.get('/alerts', { params: { page: 1, page_size: 200 } })) as {
      items: { id: number; code: string; ai_summary: string | null }[]
    }
    alertCodes.value = new Set(data.items.map((a) => a.code))
    for (const a of data.items) {
      if (a.ai_summary) {
        alertSummaries.value[a.code] = a.ai_summary
        alertIds.value[a.code] = a.id
      }
    }
  } catch {
    // optional
  }
}

function toggleExpand(code: string) {
  if (!alertSummaries.value[code]) return
  expandedCode.value = expandedCode.value === code ? null : code
}

async function onAdd() {
  if (!form.code || form.shares <= 0) return
  adding.value = true
  try {
    await store.addHolding({
      code: form.code,
      name: form.name || undefined,
      shares: form.shares,
      cost_price: form.cost_price,
    })
    form.code = ''
    form.name = ''
    form.shares = 0
    form.cost_price = undefined
    searchQuery.value = ''
  } finally {
    adding.value = false
  }
}

async function onDelete(id: number, label: string) {
  if (!confirm(`确认删除 ${label} 吗？`)) return
  await store.removeHolding(id)
}

function quotePrice(code: string): string {
  const q = store.quotes[code]
  return q?.last_price != null ? q.last_price.toFixed(2) : '--'
}

function quoteChg(code: string): string {
  const q = store.quotes[code]
  return q?.pct_change != null ? (q.pct_change > 0 ? '+' : '') + q.pct_change.toFixed(2) + '%' : '--'
}

function quoteChgClass(code: string): string {
  const q = store.quotes[code]
  if (!q?.pct_change) return ''
  return q.pct_change >= 0 ? 'up' : 'down'
}

function fmtPnl(h: { code: string; shares: number; cost_price?: number }): string {
  const q = store.quotes[h.code]
  if (!q?.last_price || !h.cost_price) return '--'
  const pnl = (q.last_price - h.cost_price) * h.shares
  const sign = pnl >= 0 ? '+' : ''
  return sign + pnl.toFixed(2)
}

function pnlClass(h: { code: string; cost_price?: number }): string {
  const q = store.quotes[h.code]
  if (!q?.last_price || !h.cost_price) return ''
  return q.last_price >= h.cost_price ? 'up' : 'down'
}

onMounted(() => {
  store.fetchHoldings()
  fetchAlertCodes()
})
</script>

<style scoped>
.add-form {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.add-form input {
  padding: 8px 12px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  font-size: 0.85rem;
  outline: none;
}
.add-form input:focus {
  border-color: var(--accent-blue);
}

.btn-submit {
  padding: 8px 20px;
  background: var(--accent-blue);
  color: #fff;
  border: none;
  border-radius: var(--radius-sm);
  font-size: 0.85rem;
  cursor: pointer;
}
.btn-submit:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.holdings-table {
  width: 100%;
  border-collapse: collapse;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  overflow: hidden;
}

.holdings-table th,
.holdings-table td {
  padding: 10px 12px;
  text-align: left;
  border-bottom: 1px solid var(--border-light);
  font-size: 0.85rem;
}

.holdings-table th {
  color: var(--text-secondary);
  font-weight: 600;
  background: var(--bg-secondary);
}

.col-code {
  font-weight: 700;
  font-family: var(--font-mono);
}

.col-num {
  font-family: var(--font-mono);
  text-align: right;
}

.btn-delete {
  padding: 4px 12px;
  border: 1px solid var(--accent-red);
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--accent-red);
  font-size: 0.8rem;
  cursor: pointer;
  transition: all var(--transition);
}
.btn-delete:hover {
  background: var(--accent-red);
  color: #fff;
}

.search-wrap {
  position: relative;
}

.search-dropdown {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  z-index: 50;
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  box-shadow: var(--shadow-md);
  list-style: none;
  max-height: 240px;
  overflow-y: auto;
}

.search-dropdown li {
  padding: 8px 12px;
  cursor: pointer;
  display: flex;
  gap: 10px;
  font-size: 0.85rem;
  transition: background var(--transition);
}
.search-dropdown li:hover {
  background: var(--bg-hover);
}

.search-code {
  font-weight: 700;
  font-family: var(--font-mono);
  min-width: 64px;
}

.search-name {
  color: var(--text-primary);
}

.search-industry {
  color: var(--text-muted);
  font-size: 0.75rem;
  margin-left: auto;
}

.has-alert {
  background: var(--accent-red-light) !important;
}

.alert-dot {
  font-size: 0.7rem;
}

.col-num.up { color: var(--accent-red); }
.col-num.down { color: var(--accent-green); }

.no-alert {
  color: var(--text-muted);
  font-size: 0.8rem;
}

.expand-row td {
  padding: 0 !important;
  border-bottom: 2px solid var(--accent-blue);
}
.expand-content {
  padding: 12px 16px;
  background: var(--accent-blue-light);
  border-left: 3px solid var(--accent-blue);
}
.expand-title {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--accent-blue);
  margin-bottom: 6px;
  text-transform: uppercase;
}
.expand-content p {
  font-size: 0.85rem;
  color: var(--text-primary);
  line-height: 1.6;
  margin-bottom: 8px;
}
.expand-link {
  font-size: 0.8rem;
}


@media (max-width: 767px) {
  .add-form {
    flex-direction: column;
    align-items: stretch;
  }
  .add-form input {
    width: 100% !important;
  }
}
</style>
