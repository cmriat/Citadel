<script setup>
import { onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAppStore } from './stores/app'
import LogPanel from './components/LogPanel.vue'

const router = useRouter()
const appStore = useAppStore()

const menuItems = [
  { index: '/control', title: '控制面板', icon: 'Setting' },
  { index: '/monitor', title: '监控', icon: 'DataLine' }
]

const handleMenuSelect = (index) => {
  router.push(index)
}

onMounted(() => {
  appStore.connectWebSocket()
})

onUnmounted(() => {
  appStore.disconnectWebSocket()
})
</script>

<template>
  <el-container class="app-container">
    <!-- 侧边栏 -->
    <el-aside width="200px" class="app-aside">
      <div class="logo">
        <el-icon size="24"><Monitor /></el-icon>
        <span>LeRobot Converter</span>
      </div>
      <el-menu
        :default-active="$route.path"
        class="app-menu"
        @select="handleMenuSelect"
      >
        <el-menu-item
          v-for="item in menuItems"
          :key="item.index"
          :index="item.index"
        >
          <el-icon><component :is="item.icon" /></el-icon>
          <span>{{ item.title }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <!-- 主内容区 -->
    <el-container>
      <el-main class="app-main">
        <router-view />
      </el-main>

      <!-- 底部日志面板 -->
      <el-footer height="200px" class="app-footer">
        <LogPanel />
      </el-footer>
    </el-container>
  </el-container>
</template>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html, body, #app {
  height: 100%;
  width: 100%;
}

.app-container {
  height: 100%;
  background: linear-gradient(135deg, #e0e5ec 0%, #f5f7fa 100%);
  padding: 12px;
  gap: 12px;
}

.app-aside {
  background-color: var(--bg-primary);
  color: var(--text-primary);
  border-radius: 16px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
  overflow: hidden;
}

.logo {
  height: 70px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.logo .el-icon {
  color: #667eea;
  -webkit-text-fill-color: #667eea;
}

.app-menu {
  border-right: none;
  background-color: transparent;
  padding: 8px;
}

.app-menu .el-menu-item {
  color: var(--text-regular);
  border-radius: 10px;
  margin: 4px 0;
  transition: all 0.3s ease;
}

.app-menu .el-menu-item:hover {
  background-color: #f0f2ff;
  color: #667eea;
}

.app-menu .el-menu-item.is-active {
  color: #fff;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

.el-container.is-vertical {
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
}

.app-main {
  background-color: var(--bg-primary);
  padding: 20px 24px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.app-main > * {
  width: 100%;
  flex: 1;
  display: flex;
  flex-direction: column;
}

.app-footer {
  background-color: var(--bg-primary);
  padding: 0;
  border-top: 1px solid var(--border-lighter);
}
</style>
