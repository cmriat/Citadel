<script setup lang="ts">
import { computed, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { Icon } from '@iconify/vue'
import { useThemeStore } from '@/stores/theme'
import Sidebar from './Sidebar.vue'

const route = useRoute()
const themeStore = useThemeStore()

const pageTitle = computed(() => {
  return route.meta.title as string || 'Citadel'
})

const themeIcon = computed(() => {
  return themeStore.theme === 'dark' ? 'mdi:weather-sunny' : 'mdi:weather-night'
})

const handleToggleTheme = () => {
  themeStore.toggleTheme()
}

onMounted(() => {
  console.log('[Layout] Mounted at:', route.fullPath)
})

watch(() => route.fullPath, (newPath, oldPath) => {
  console.log('[Layout] Route change detected:', oldPath, '->', newPath)
})
</script>

<template>
  <div class="layout" :class="themeStore.theme">
    <Sidebar />
    <div class="main-content">
      <header class="header">
        <div class="header-left">
          <h1 class="page-title">{{ pageTitle }}</h1>
        </div>
        <div class="header-right">
          <el-tooltip :content="themeStore.theme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode'">
            <el-button circle @click="handleToggleTheme">
              <Icon :icon="themeIcon" />
            </el-button>
          </el-tooltip>
          <el-button circle>
            <Icon icon="mdi:github" />
          </el-button>
        </div>
      </header>
      <main class="content">
        <router-view />
      </main>
    </div>
  </div>
</template>

<style scoped>
.layout {
  display: flex;
  min-height: 100vh;
  transition: background-color 0.3s ease;
}

/* Dark theme */
.layout.dark {
  background-color: #0f0f0f;
}

.layout.dark .header {
  background-color: #16162a;
  border-bottom-color: #2a2a4e;
}

.layout.dark .page-title {
  color: #fff;
}

/* Light theme */
.layout.light {
  background-color: #f5f7fa;
}

.layout.light .header {
  background-color: #ffffff;
  border-bottom-color: #e4e7ed;
}

.layout.light .page-title {
  color: #303133;
}

.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  margin-left: 220px;
}

.header {
  height: 60px;
  padding: 0 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid;
  transition: all 0.3s ease;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.page-title {
  font-size: 18px;
  font-weight: 600;
  margin: 0;
  transition: color 0.3s ease;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.content {
  flex: 1;
  padding: 24px;
  overflow-y: auto;
}
</style>
