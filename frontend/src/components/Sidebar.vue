<script setup lang="ts">
import { computed, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import { useThemeStore } from '@/stores/theme'

const route = useRoute()
const router = useRouter()
const themeStore = useThemeStore()

const menuItems = [
  { path: '/', title: 'Dashboard', icon: 'mdi:view-dashboard', group: 'main' },
  { path: '/download', title: 'Download', icon: 'mdi:download', group: 'tasks' },
  { path: '/convert', title: 'Convert', icon: 'mdi:swap-horizontal', group: 'tasks' },
  { path: '/upload', title: 'Upload', icon: 'mdi:upload', group: 'tasks' },
  { path: '/status', title: 'Status', icon: 'mdi:chart-line', group: 'system' }
]

const currentPath = computed(() => route.path)

// Debug: 检查 router 实例
onMounted(() => {
  console.log('[Sidebar] Mounted, current path:', route.path)
})

// Debug: 监听路由变化
watch(() => route.path, (newPath, oldPath) => {
  console.log('[Sidebar] Path changed:', oldPath, '->', newPath)
}, { immediate: true })

// 正确的导航函数 - 使用 Vue Router
const forceNavigate = (path: string) => {
  console.log('=== NAVIGATION ===')
  console.log('Target:', path)
  console.log('Current:', route.path)

  if (path !== route.path) {
    console.log('Using router.push')
    router.push(path)
  }
}
</script>

<template>
  <aside class="sidebar" :class="themeStore.theme">
    <div class="logo">
      <Icon icon="mdi:robot" class="logo-icon" />
      <span class="logo-text">Citadel</span>
    </div>

    <nav class="nav">
      <div class="nav-group">
        <div class="nav-group-title">Overview</div>
        <template v-for="item in menuItems.filter(i => i.group === 'main')" :key="item.path">
          <div
            class="nav-item"
            :class="{ active: currentPath === item.path }"
            @click="forceNavigate(item.path)"
            :data-path="item.path"
          >
            <Icon :icon="item.icon" class="nav-icon" />
            <span>{{ item.title }}</span>
          </div>
        </template>
      </div>

      <div class="nav-group">
        <div class="nav-group-title">Tasks</div>
        <template v-for="item in menuItems.filter(i => i.group === 'tasks')" :key="item.path">
          <div
            class="nav-item"
            :class="{ active: currentPath === item.path }"
            @click="forceNavigate(item.path)"
            :data-path="item.path"
          >
            <Icon :icon="item.icon" class="nav-icon" />
            <span>{{ item.title }}</span>
          </div>
        </template>
      </div>

      <div class="nav-group">
        <div class="nav-group-title">System</div>
        <template v-for="item in menuItems.filter(i => i.group === 'system')" :key="item.path">
          <div
            class="nav-item"
            :class="{ active: currentPath === item.path }"
            @click="forceNavigate(item.path)"
            :data-path="item.path"
          >
            <Icon :icon="item.icon" class="nav-icon" />
            <span>{{ item.title }}</span>
          </div>
        </template>
      </div>
    </nav>

    <div class="sidebar-footer">
      <div class="version">v0.2.0</div>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  position: fixed;
  left: 0;
  top: 0;
  width: 220px;
  height: 100vh;
  display: flex;
  flex-direction: column;
  transition: all 0.3s ease;
  z-index: 100;
}

/* Dark theme */
.sidebar.dark {
  background-color: #16162a;
  border-right: 1px solid #2a2a4e;
}

.sidebar.dark .logo {
  border-bottom: 1px solid #2a2a4e;
}

.sidebar.dark .logo-text {
  color: #fff;
}

.sidebar.dark .nav-group-title {
  color: #6a6a8a;
}

.sidebar.dark .nav-item {
  color: #a0a0c0;
}

.sidebar.dark .nav-item:hover {
  background-color: #252545;
  color: #fff;
}

.sidebar.dark .nav-item.active {
  background-color: #409eff20;
  color: #409eff;
}

.sidebar.dark .sidebar-footer {
  border-top: 1px solid #2a2a4e;
}

.sidebar.dark .version {
  color: #6a6a8a;
}

/* Light theme */
.sidebar.light {
  background-color: #ffffff;
  border-right: 1px solid #e4e7ed;
}

.sidebar.light .logo {
  border-bottom: 1px solid #e4e7ed;
}

.sidebar.light .logo-text {
  color: #303133;
}

.sidebar.light .nav-group-title {
  color: #909399;
}

.sidebar.light .nav-item {
  color: #606266;
}

.sidebar.light .nav-item:hover {
  background-color: #f0f2f5;
  color: #303133;
}

.sidebar.light .nav-item.active {
  background-color: #409eff15;
  color: #409eff;
}

.sidebar.light .sidebar-footer {
  border-top: 1px solid #e4e7ed;
}

.sidebar.light .version {
  color: #909399;
}

/* Common styles */
.logo {
  height: 60px;
  padding: 0 20px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.logo-icon {
  font-size: 28px;
  color: #409eff;
}

.logo-text {
  font-size: 20px;
  font-weight: 700;
}

.nav {
  flex: 1;
  padding: 16px 12px;
  overflow-y: auto;
}

.nav-group {
  margin-bottom: 24px;
}

.nav-group-title {
  padding: 8px 12px;
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  margin: 4px 0;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
  text-decoration: none;
}

.nav-icon {
  font-size: 20px;
}

.sidebar-footer {
  padding: 16px;
}

.version {
  text-align: center;
  font-size: 12px;
}
</style>
