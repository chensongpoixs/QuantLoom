<template>
  <div class="timeline">
    <div
      v-for="e in events"
      :key="e.id"
      class="timeline-item"
    >
      <div
        class="timeline-dot"
        :class="dotClass(e.sentiment_score)"
      ></div>
      <div class="timeline-content">
        <div class="timeline-title">{{ e.title }}</div>
        <div class="timeline-meta">
          <span class="timeline-type">{{ e.event_type }}</span>
          <span>·</span>
          <span>{{ e.source }}</span>
          <span>·</span>
          <span>{{ formatDateTime(e.published_at) }}</span>
          <span
            v-if="e.sentiment_score != null"
            class="timeline-sentiment"
            :class="sentimentClass(e.sentiment_score)"
          >
            {{ e.sentiment_score > 0 ? '+' : '' }}{{ e.sentiment_score.toFixed(2) }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { EventItem } from '@/types'
import { formatDateTime } from '@/utils'

defineProps<{ events: EventItem[] }>()

function dotClass(score: number | null): string {
  if (score == null) return 'neutral'
  if (score > 0.2) return 'positive'
  if (score < -0.2) return 'negative'
  return 'neutral'
}

function sentimentClass(score: number): string {
  if (score > 0) return 'positive'
  if (score < 0) return 'negative'
  return 'neutral'
}
</script>

<style scoped>
.timeline {
  position: relative;
  padding-left: 24px;
}

.timeline::before {
  content: '';
  position: absolute;
  left: 5px;
  top: 4px;
  bottom: 0;
  width: 2px;
  background: var(--border-color);
}

.timeline-item {
  position: relative;
  padding-bottom: 16px;
}
.timeline-item:last-child {
  padding-bottom: 0;
}

.timeline-dot {
  position: absolute;
  left: -19px;
  top: 4px;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  border: 2px solid var(--border-color);
  background: var(--bg-primary);
}
.timeline-dot.positive { border-color: var(--accent-green); background: var(--accent-green-light); }
.timeline-dot.negative { border-color: var(--accent-red); background: var(--accent-red-light); }
.timeline-dot.neutral { border-color: var(--text-muted); background: var(--bg-secondary); }

.timeline-content {
  font-size: 0.85rem;
}

.timeline-title {
  font-weight: 500;
  color: var(--text-primary);
}

.timeline-meta {
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-top: 2px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.timeline-sentiment.positive { color: var(--accent-green); font-weight: 600; }
.timeline-sentiment.negative { color: var(--accent-red); font-weight: 600; }
</style>
