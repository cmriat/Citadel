<script setup>
import { ref, computed, nextTick } from 'vue'
import { useAppStore } from '../stores/app'

const appStore = useAppStore()

const logContainer = ref(null)

const logs = computed(() => appStore.logs)
const wsConnected = computed(() => appStore.wsConnected)

const clearLogs = () => {
  appStore.clearLogs()
}

// 自动滚动到底部
const scrollToBottom = () => {
  nextTick(() => {
    if (logContainer.value) {
      logContainer.value.scrollTop = logContainer.value.scrollHeight
    }
  })
}

// 监听日志变化
import { watch } from 'vue'
watch(logs, scrollToBottom, { deep: true })
</script>

<template>
  <div class="log-panel">
    <div class="log-header">
      <div class="log-title">
        <el-icon><Document /></el-icon>
        <span>实时日志</span>
        <el-tag
          :type="wsConnected ? 'success' : 'danger'"
          size="small"
          effect="dark"
        >
          {{ wsConnected ? '已连接' : '未连接' }}
        </el-tag>
      </div>
      <el-button size="small" @click="clearLogs">
        <el-icon><Delete /></el-icon>
        清除
      </el-button>
    </div>
    <div ref="logContainer" class="log-content">
      <div
        v-for="(log, index) in logs"
        :key="index"
        class="log-item"
        :class="{
          'log-error': log.includes('✗') || log.includes('error'),
          'log-success': log.includes('✓'),
          'log-info': log.includes('⟳') || log.includes('▶')
        }"
      >
        {{ log }}
      </div>
      <div v-if="logs.length === 0" class="log-empty">
        暂无日志
      </div>
    </div>
  </div>
</template>

<style scoped>
.log-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: #1e1e1e;
  color: #d4d4d4;
}

.log-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  border-bottom: 1px solid #333;
  background-color: #252526;
}

.log-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
}

.log-content {
  flex: 1;
  overflow-y: auto;
  padding: 8px 12px;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 13px;
  line-height: 1.6;
}

.log-item {
  white-space: pre-wrap;
  word-break: break-all;
}

.log-error {
  color: #f48771;
}

.log-success {
  color: #89d185;
}

.log-info {
  color: #6a9955;
}

.log-empty {
  color: #6a6a6a;
  text-align: center;
  padding: 20px;
}

/* 滚动条样式 */
.log-content::-webkit-scrollbar {
  width: 8px;
}

.log-content::-webkit-scrollbar-track {
  background: #1e1e1e;
}

.log-content::-webkit-scrollbar-thumb {
  background: #424242;
  border-radius: 4px;
}

.log-content::-webkit-scrollbar-thumb:hover {
  background: #555;
}
</style>
