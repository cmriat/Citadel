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

// 解析日志类型
const getLogClass = (log) => {
  if (log.includes('✗') || log.includes('ERROR') || log.includes('error') || log.includes('failed') || log.includes('Failed')) {
    return 'log-error'
  }
  if (log.includes('✓') || log.includes('completed') || log.includes('success')) {
    return 'log-success'
  }
  if (log.includes('⚠') || log.includes('WARNING') || log.includes('skipped')) {
    return 'log-warning'
  }
  if (log.includes('[Scanner]')) {
    return 'log-scanner'
  }
  if (log.includes('[Worker]')) {
    return 'log-worker'
  }
  if (log.includes('[System]')) {
    return 'log-system'
  }
  return ''
}

// 监听日志变化
import { watch } from 'vue'
watch(logs, scrollToBottom, { deep: true })
</script>

<template>
  <div class="log-panel">
    <div class="log-header">
      <div class="log-title">
        <el-icon><Monitor /></el-icon>
        <span>实时日志</span>
        <el-tag
          :type="wsConnected ? 'success' : 'danger'"
          size="small"
          effect="dark"
          class="status-tag"
        >
          {{ wsConnected ? '已连接' : '未连接' }}
        </el-tag>
      </div>
      <el-button size="small" text @click="clearLogs">
        <el-icon><Delete /></el-icon>
        清除
      </el-button>
    </div>
    <div ref="logContainer" class="log-content">
      <div
        v-for="(log, index) in logs"
        :key="index"
        class="log-item"
        :class="getLogClass(log)"
      >
        {{ log }}
      </div>
      <div v-if="logs.length === 0" class="log-empty">
        <el-icon :size="32"><DocumentCopy /></el-icon>
        <span>等待日志输出...</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.log-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: linear-gradient(180deg, #1e1e2e 0%, #181825 100%);
  border-radius: 8px 8px 0 0;
  overflow: hidden;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.05);
}

.log-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  background: linear-gradient(180deg, #2a2a3c 0%, #252536 100%);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.log-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  color: #cdd6f4;
}

.log-title .el-icon {
  color: #89b4fa;
}

.status-tag {
  font-size: 11px;
}

.log-header .el-button {
  color: #a6adc8;
  font-size: 12px;
}

.log-header .el-button:hover {
  color: #f38ba8;
  background: rgba(243, 139, 168, 0.1);
}

.log-content {
  flex: 1;
  overflow-y: auto;
  padding: 12px 16px;
  font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', 'Monaco', monospace;
  font-size: 12px;
  line-height: 1.8;
}

.log-item {
  white-space: pre-wrap;
  word-break: break-all;
  color: #a6adc8;
  padding: 2px 0;
  border-left: 2px solid transparent;
  padding-left: 8px;
  margin-left: -8px;
  transition: all 0.15s ease;
}

.log-item:hover {
  background: rgba(255, 255, 255, 0.03);
}

/* 错误日志 - 红色 */
.log-error {
  color: #f38ba8;
  border-left-color: #f38ba8;
  background: rgba(243, 139, 168, 0.08);
}

/* 成功日志 - 绿色 */
.log-success {
  color: #a6e3a1;
  border-left-color: #a6e3a1;
}

/* 警告日志 - 黄色 */
.log-warning {
  color: #f9e2af;
  border-left-color: #f9e2af;
}

/* Scanner 日志 - 蓝色 */
.log-scanner {
  color: #89b4fa;
}

/* Worker 日志 - 紫色 */
.log-worker {
  color: #cba6f7;
}

/* System 日志 - 青色 */
.log-system {
  color: #94e2d5;
}

.log-empty {
  color: #585b70;
  text-align: center;
  padding: 40px 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.log-empty .el-icon {
  opacity: 0.5;
}

/* 滚动条样式 */
.log-content::-webkit-scrollbar {
  width: 6px;
}

.log-content::-webkit-scrollbar-track {
  background: transparent;
}

.log-content::-webkit-scrollbar-thumb {
  background: #45475a;
  border-radius: 3px;
}

.log-content::-webkit-scrollbar-thumb:hover {
  background: #585b70;
}
</style>
