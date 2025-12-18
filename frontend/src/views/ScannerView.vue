<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  startScanner, stopScanner, getScannerStatus,
  startWorkers, stopWorkers, getWorkerStatus
} from '../api'

// Scanner 状态
const scannerStatus = reactive({
  running: false,
  mode: null,
  interval: 120,
  started_at: null,
  last_scan_at: null,
  next_scan_at: null,
  stats: {
    found: 0,
    ready: 0,
    published: 0,
    skipped: 0
  }
})

// Worker 状态
const workerStatus = reactive({
  running: false,
  num_workers: 4,
  active_workers: 0,
  started_at: null
})

// 表单
const scannerForm = reactive({
  interval: 120
})

const workerForm = reactive({
  num_workers: 4
})

const scannerLoading = ref(false)
const workerLoading = ref(false)

let statusInterval = null

// 刷新状态
const refreshStatus = async () => {
  try {
    const [scannerRes, workerRes] = await Promise.all([
      getScannerStatus(),
      getWorkerStatus()
    ])
    Object.assign(scannerStatus, scannerRes.data)
    Object.assign(workerStatus, workerRes.data)
  } catch (error) {
    console.error('Failed to refresh status:', error)
  }
}

// 启动持续扫描
const startContinuousScan = async () => {
  scannerLoading.value = true
  try {
    const { data } = await startScanner({
      mode: 'continuous',
      interval: scannerForm.interval
    })
    if (data.success) {
      ElMessage.success(data.message)
      await refreshStatus()
    } else {
      ElMessage.warning(data.message)
    }
  } catch (error) {
    console.error('Failed to start scanner:', error)
    ElMessage.error(error.response?.data?.detail || '启动失败')
  } finally {
    scannerLoading.value = false
  }
}

// 启动全量扫描
const startFullScan = async () => {
  scannerLoading.value = true
  try {
    const { data } = await startScanner({
      mode: 'once',
      interval: 0
    })
    if (data.success) {
      ElMessage.success(data.message)
      await refreshStatus()
    } else {
      ElMessage.warning(data.message)
    }
  } catch (error) {
    console.error('Failed to start scanner:', error)
    ElMessage.error(error.response?.data?.detail || '启动失败')
  } finally {
    scannerLoading.value = false
  }
}

// 停止扫描
const stopScan = async () => {
  scannerLoading.value = true
  try {
    const { data } = await stopScanner()
    if (data.success) {
      ElMessage.success(data.message)
      await refreshStatus()
    } else {
      ElMessage.warning(data.message)
    }
  } catch (error) {
    console.error('Failed to stop scanner:', error)
    ElMessage.error('停止失败')
  } finally {
    scannerLoading.value = false
  }
}

// 启动 Workers
const startWork = async () => {
  workerLoading.value = true
  try {
    const { data } = await startWorkers({
      num_workers: workerForm.num_workers
    })
    if (data.success) {
      ElMessage.success(data.message)
      await refreshStatus()
    } else {
      ElMessage.warning(data.message)
    }
  } catch (error) {
    console.error('Failed to start workers:', error)
    ElMessage.error(error.response?.data?.detail || '启动失败')
  } finally {
    workerLoading.value = false
  }
}

// 停止 Workers
const stopWork = async () => {
  workerLoading.value = true
  try {
    const { data } = await stopWorkers()
    if (data.success) {
      ElMessage.success(data.message)
      await refreshStatus()
    } else {
      ElMessage.warning(data.message)
    }
  } catch (error) {
    console.error('Failed to stop workers:', error)
    ElMessage.error('停止失败')
  } finally {
    workerLoading.value = false
  }
}

// 格式化时间
const formatTime = (isoString) => {
  if (!isoString) return '-'
  const date = new Date(isoString)
  return date.toLocaleString('zh-CN')
}

onMounted(() => {
  refreshStatus()
  // 每 3 秒刷新一次状态
  statusInterval = setInterval(refreshStatus, 3000)
})

onUnmounted(() => {
  if (statusInterval) {
    clearInterval(statusInterval)
  }
})
</script>

<template>
  <div class="scanner-view">
    <!-- Scanner 控制 -->
    <el-card class="control-card">
      <template #header>
        <div class="card-header">
          <span><el-icon><Search /></el-icon> Scanner 控制</span>
          <el-tag
            :type="scannerStatus.running ? 'success' : 'info'"
            effect="dark"
          >
            {{ scannerStatus.running ? '运行中' : '已停止' }}
          </el-tag>
        </div>
      </template>

      <el-row :gutter="20">
        <!-- 持续扫描 -->
        <el-col :span="12">
          <div class="scan-mode-card">
            <div class="mode-header">
              <el-icon size="24" color="#409eff"><Refresh /></el-icon>
              <span>持续扫描</span>
            </div>
            <p class="mode-desc">实时监控 BOS，新 episode 上传后自动发布到队列</p>
            <el-form-item label="扫描间隔" label-width="80px">
              <el-input-number
                v-model="scannerForm.interval"
                :min="10"
                :max="3600"
                :disabled="scannerStatus.running"
              />
              <span style="margin-left: 8px">秒</span>
            </el-form-item>
            <el-button
              type="primary"
              :loading="scannerLoading"
              :disabled="scannerStatus.running"
              @click="startContinuousScan"
            >
              <el-icon><CaretRight /></el-icon>
              启动持续扫描
            </el-button>
          </div>
        </el-col>

        <!-- 全量扫描 -->
        <el-col :span="12">
          <div class="scan-mode-card">
            <div class="mode-header">
              <el-icon size="24" color="#67c23a"><List /></el-icon>
              <span>全量扫描</span>
            </div>
            <p class="mode-desc">清除增量位置，一次性扫描所有 episode 并发布</p>
            <div style="height: 32px"></div>
            <el-button
              type="success"
              :loading="scannerLoading"
              :disabled="scannerStatus.running"
              @click="startFullScan"
            >
              <el-icon><CaretRight /></el-icon>
              启动全量扫描
            </el-button>
          </div>
        </el-col>
      </el-row>

      <!-- Scanner 状态信息 -->
      <el-divider />

      <div class="status-info">
        <el-row :gutter="20">
          <el-col :span="6">
            <div class="stat-item">
              <div class="stat-label">模式</div>
              <div class="stat-value">
                {{ scannerStatus.mode === 'continuous' ? '持续' :
                   scannerStatus.mode === 'once' ? '全量' : '-' }}
              </div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="stat-item">
              <div class="stat-label">发现</div>
              <div class="stat-value">{{ scannerStatus.stats.found }}</div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="stat-item">
              <div class="stat-label">就绪</div>
              <div class="stat-value">{{ scannerStatus.stats.ready }}</div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="stat-item">
              <div class="stat-label">已发布</div>
              <div class="stat-value">{{ scannerStatus.stats.published }}</div>
            </div>
          </el-col>
        </el-row>

        <div v-if="scannerStatus.running" class="time-info">
          <span>启动时间: {{ formatTime(scannerStatus.started_at) }}</span>
          <span>上次扫描: {{ formatTime(scannerStatus.last_scan_at) }}</span>
        </div>

        <div class="action-buttons" v-if="scannerStatus.running">
          <el-button
            type="danger"
            :loading="scannerLoading"
            @click="stopScan"
          >
            <el-icon><VideoPause /></el-icon>
            停止扫描
          </el-button>
        </div>
      </div>
    </el-card>

    <!-- Worker 控制 -->
    <el-card class="control-card">
      <template #header>
        <div class="card-header">
          <span><el-icon><Cpu /></el-icon> Worker 控制</span>
          <el-tag
            :type="workerStatus.running ? 'success' : 'info'"
            effect="dark"
          >
            {{ workerStatus.running ?
               `运行中 (${workerStatus.active_workers}/${workerStatus.num_workers})` :
               '已停止' }}
          </el-tag>
        </div>
      </template>

      <el-form inline>
        <el-form-item label="Worker 数量">
          <el-input-number
            v-model="workerForm.num_workers"
            :min="1"
            :max="16"
            :disabled="workerStatus.running"
          />
        </el-form-item>

        <el-form-item>
          <el-button
            v-if="!workerStatus.running"
            type="primary"
            :loading="workerLoading"
            @click="startWork"
          >
            <el-icon><CaretRight /></el-icon>
            启动 Workers
          </el-button>
          <el-button
            v-else
            type="danger"
            :loading="workerLoading"
            @click="stopWork"
          >
            <el-icon><VideoPause /></el-icon>
            停止 Workers
          </el-button>
        </el-form-item>
      </el-form>

      <div v-if="workerStatus.running" class="time-info">
        <span>启动时间: {{ formatTime(workerStatus.started_at) }}</span>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.scanner-view {
  max-width: 900px;
}

.control-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header span {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 500;
}

.scan-mode-card {
  padding: 20px;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  background-color: #fafafa;
}

.mode-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 500;
  margin-bottom: 8px;
}

.mode-desc {
  color: #909399;
  font-size: 13px;
  margin-bottom: 16px;
}

.status-info {
  margin-top: 16px;
}

.stat-item {
  text-align: center;
  padding: 12px;
  background-color: #f5f7fa;
  border-radius: 8px;
}

.stat-label {
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
}

.stat-value {
  font-size: 24px;
  font-weight: 600;
  color: #303133;
}

.time-info {
  display: flex;
  gap: 20px;
  margin-top: 16px;
  font-size: 13px;
  color: #909399;
}

.action-buttons {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
