<script setup>
import { onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAppStore } from './stores/app'
import LogPanel from './components/LogPanel.vue'

const router = useRouter()
const appStore = useAppStore()

const menuItems = [
  { index: '/config', title: '配置', icon: 'Setting' },
  { index: '/scanner', title: '扫描', icon: 'Search' },
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
}

.app-aside {
  background-color: #304156;
  color: #fff;
}

.logo {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-size: 16px;
  font-weight: bold;
  border-bottom: 1px solid #3d4a5a;
}

.app-menu {
  border-right: none;
  background-color: transparent;
}

.app-menu .el-menu-item {
  color: #bfcbd9;
}

.app-menu .el-menu-item:hover {
  background-color: #263445;
}

.app-menu .el-menu-item.is-active {
  color: #409eff;
  background-color: #263445;
}

.app-main {
  background-color: #f5f7fa;
  padding: 20px;
  overflow-y: auto;
}

.app-footer {
  background-color: #1e1e1e;
  padding: 0;
  border-top: 1px solid #333;
}
</style>
