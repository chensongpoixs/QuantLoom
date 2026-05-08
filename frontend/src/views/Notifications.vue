<template>
  <div>
    <div class="page-header-row">
      <h1 class="page-title">通知日志</h1>
      <button class="btn-refresh" @click="fetchPage(1)">刷新</button>
    </div>

    <ErrorBanner :message="notifStore.error" @retry="fetchPage(notifStore.page)" />

    <!-- Push rules config -->
    <div class="section">
      <div class="section-title">推送规则</div>
      <div class="push-rules">
        <div v-for="level in ['P1', 'P2', 'P3']" :key="level" class="push-rule-row">
          <span class="push-level">{{ level }}</span>
          <label><input type="checkbox" v-model="pushRules[level].enabled" @change="savePushRules" /> 启用推送</label>
          <label v-if="pushRules[level].enabled">
            渠道:
            <select v-model="pushRules[level].channel" @change="savePushRules">
              <option value="wecom">企业微信</option>
              <option value="feishu">飞书</option>
              <option value="dingtalk">钉钉</option>
              <option value="email">邮件</option>
            </select>
          </label>
        </div>
      </div>
    </div>

    <!-- Push channel management -->
    <div class="section">
      <div class="section-title">推送渠道管理</div>
      <div class="channel-mgmt">
        <div v-for="ch in channels" :key="ch.key" class="channel-item">
          <div class="channel-info">
            <span class="channel-name">{{ ch.label }}</span>
            <span class="channel-status" :class="ch.enabled ? 'enabled' : 'disabled'">
              {{ ch.enabled ? '已启用' : '已禁用' }}
            </span>
          </div>
          <label class="toggle-switch">
            <input type="checkbox" v-model="ch.enabled" @change="saveChannels" />
            <span class="toggle-slider"></span>
          </label>
        </div>
        <div class="channel-hint">渠道配置在 .env 中管理，此处仅为前端开关状态缓存。</div>
      </div>
    </div>

    <!-- Channel filter -->
    <div class="filter-bar">
      <select v-model="filterChannel" @change="onFilterChange">
        <option value="">全部渠道</option>
        <option value="wecom">企业微信</option>
        <option value="feishu">飞书</option>
        <option value="dingtalk">钉钉</option>
        <option value="email">邮件</option>
      </select>
    </div>

    <div v-if="notifStore.loading" class="spinner">加载中...</div>

    <div v-else-if="filteredItems.length" class="notif-list">
      <div class="notif-item" v-for="n in filteredItems" :key="n.id">
        <div class="notif-header">
          <span class="notif-channel-badge">{{ n.channel }}</span>
          <span class="notif-status-badge" :class="n.status">{{ n.status === 'success' ? '成功' : '失败' }}</span>
          <span class="notif-time">{{ formatDateTime(n.sent_at) }}</span>
          <span v-if="n.recipient" class="notif-recipient">{{ n.recipient }}</span>
        </div>
        <div v-if="n.error_message" class="notif-error">{{ n.error_message }}</div>
        <div class="notif-actions" v-if="n.status === 'failed' || n.alert_id">
          <button v-if="n.status === 'failed'" class="btn-retry" @click="onRetry(n.id)">重推</button>
          <router-link v-if="n.alert_id" :to="`/alerts/${n.alert_id}`" class="notif-alert-link">查看告警 #{{ n.alert_id }}</router-link>
        </div>
      </div>

      <Pagination
        v-model="notifStore.page"
        :total="notifStore.total"
        :page-size="notifStore.pageSize"
        @update:model-value="fetchPage"
      />
    </div>

    <div v-else class="empty-state">
      <div class="empty-icon">📬</div>
      <div class="empty-text">暂无通知记录。</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, computed, reactive } from 'vue'
import { useNotificationsStore } from '@/stores/notifications'
import Pagination from '@/components/Pagination.vue'
import ErrorBanner from '@/components/ErrorBanner.vue'
import { formatDateTime } from '@/utils'
import api from '@/api'

const notifStore = useNotificationsStore()
const filterChannel = ref('')

interface PushRule { enabled: boolean; channel: string }
const defaultRules: Record<string, PushRule> = {
  P1: { enabled: true, channel: 'dingtalk' },
  P2: { enabled: true, channel: 'wecom' },
  P3: { enabled: false, channel: 'wecom' },
}

const pushRules = reactive<Record<string, PushRule>>(loadPushRules())

function loadPushRules(): Record<string, PushRule> {
  try {
    const saved = localStorage.getItem('ql_push_rules')
    return saved ? { ...defaultRules, ...JSON.parse(saved) } : { ...defaultRules }
  } catch { return { ...defaultRules } }
}

function savePushRules() {
  localStorage.setItem('ql_push_rules', JSON.stringify(pushRules))
}

// Push channel management
interface ChannelState { key: string; label: string; enabled: boolean }
const defaultChannels: ChannelState[] = [
  { key: 'wecom', label: '企业微信', enabled: false },
  { key: 'feishu', label: '飞书', enabled: false },
  { key: 'dingtalk', label: '钉钉', enabled: false },
  { key: 'email', label: '邮件', enabled: false },
]
const channels = reactive<ChannelState[]>(loadChannels())

function loadChannels(): ChannelState[] {
  try {
    const saved = localStorage.getItem('ql_channels')
    if (saved) {
      const map = JSON.parse(saved) as Record<string, boolean>
      return defaultChannels.map((c) => ({ ...c, enabled: !!map[c.key] }))
    }
  } catch { /* ignore */ }
  return [...defaultChannels]
}

function saveChannels() {
  const map: Record<string, boolean> = {}
  for (const ch of channels) map[ch.key] = ch.enabled
  localStorage.setItem('ql_channels', JSON.stringify(map))
}

const filteredItems = computed(() => {
  if (!filterChannel.value) return notifStore.items
  return notifStore.items.filter((n) => n.channel === filterChannel.value)
})

function onFilterChange() {
  notifStore.page = 1
  notifStore.fetchNotifications()
}

async function fetchPage(p: number) {
  notifStore.page = p
  await notifStore.fetchNotifications()
}

async function onRetry(logId: number) {
  try {
    await api.post(`/notifications/${logId}/retry`)
    await notifStore.fetchNotifications()
  } catch {
    // retry failed silently
  }
}

onMounted(() => notifStore.fetchNotifications())
</script>

<style scoped>
.notif-list {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  overflow: hidden;
}

.notif-item {
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-light);
}
.notif-item:last-child {
  border-bottom: none;
}

.notif-header {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.notif-channel-badge {
  padding: 2px 10px;
  border-radius: 12px;
  font-size: 0.75rem;
  font-weight: 600;
  background: var(--bg-secondary);
  color: var(--text-secondary);
}

.notif-status-badge {
  padding: 2px 10px;
  border-radius: 12px;
  font-size: 0.75rem;
  font-weight: 600;
}
.notif-status-badge.success {
  background: var(--accent-green-light);
  color: var(--accent-green);
}
.notif-status-badge.failed {
  background: var(--accent-red-light);
  color: var(--accent-red);
}

.notif-time {
  font-size: 0.8rem;
  color: var(--text-muted);
}

.notif-recipient {
  font-size: 0.8rem;
  color: var(--text-secondary);
  margin-left: auto;
}

.notif-error {
  margin-top: 6px;
  font-size: 0.8rem;
  color: var(--accent-red);
  padding: 6px 10px;
  background: var(--accent-red-light);
  border-radius: var(--radius-sm);
}

.notif-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 6px;
}

.btn-retry {
  padding: 3px 12px;
  border: 1px solid var(--accent-orange);
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--accent-orange);
  font-size: 0.75rem;
  cursor: pointer;
  transition: all var(--transition);
}
.btn-retry:hover {
  background: var(--accent-orange);
  color: #fff;
}

.notif-alert-link {
  font-size: 0.8rem;
}

.push-rules {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.push-rule-row {
  display: flex;
  align-items: center;
  gap: 20px;
  font-size: 0.85rem;
}

.push-rule-row label {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  color: var(--text-secondary);
}

.push-rule-row select {
  padding: 4px 8px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  font-size: 0.8rem;
  margin-left: 4px;
}

.push-level {
  font-weight: 700;
  font-family: var(--font-mono);
  min-width: 24px;
  color: var(--text-primary);
}

.channel-mgmt {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.channel-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid var(--border-light);
}
.channel-item:last-child { border-bottom: none; }
.channel-info {
  display: flex;
  align-items: center;
  gap: 10px;
}
.channel-name {
  font-size: 0.85rem;
  font-weight: 500;
}
.channel-status {
  font-size: 0.75rem;
  padding: 2px 8px;
  border-radius: 10px;
}
.channel-status.enabled { background: var(--accent-green-light); color: var(--accent-green); }
.channel-status.disabled { background: var(--bg-secondary); color: var(--text-muted); }

.toggle-switch {
  position: relative;
  display: inline-block;
  width: 44px;
  height: 24px;
}
.toggle-switch input { display: none; }
.toggle-slider {
  position: absolute;
  inset: 0;
  background: var(--border-color);
  border-radius: 12px;
  cursor: pointer;
  transition: background var(--transition);
}
.toggle-slider::before {
  content: '';
  position: absolute;
  width: 18px;
  height: 18px;
  left: 3px;
  top: 3px;
  background: #fff;
  border-radius: 50%;
  transition: transform var(--transition);
}
.toggle-switch input:checked + .toggle-slider { background: var(--accent-blue); }
.toggle-switch input:checked + .toggle-slider::before { transform: translateX(20px); }

.channel-hint {
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-top: 8px;
  font-style: italic;
}
</style>
