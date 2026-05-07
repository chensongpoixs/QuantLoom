<template>
  <header class="app-header">
    <div class="header-inner">
      <router-link to="/" class="header-brand">
        <span class="brand-icon">Q</span>
        <span>QuantLoom·量梭</span>
      </router-link>
      <button class="menu-toggle" @click="open = !open" aria-label="Menu">
        {{ open ? '✕' : '☰' }}
      </button>
      <nav class="header-nav" :class="{ open }">
        <router-link to="/" @click="open = false">Dashboard</router-link>
        <router-link to="/alerts" @click="open = false">Alerts</router-link>
      </nav>
    </div>
  </header>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const open = ref(false)
</script>
