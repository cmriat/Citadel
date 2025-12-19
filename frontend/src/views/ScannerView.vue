<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  startScanner, stopScanner, getScannerStatus,
  startWorkers, stopWorkers, getWorkerStatus,
  getConfig, updateConfig, testBosConnection,
  getSystemStats
} from '../api'

// ============ 配置相关 ============
const configLoading = ref(false)
const testLoading = ref(false)
const testResult = ref(null)
const showSecretKey = ref(false)
const showAccessKey = ref(false)

const form = reactive({
  bos: {
    endpoint: 'https://s3.bj.bcebos.com',
    bucket: 'srgdata',
    region: 'bj',
    access_key: '',
    secret_key: ''
  },
  paths: {
    raw_data: '',
    converted: '',
    task_name: ''
  },
  conversion: {
    strategy: 'nearest',
    tolerance_ms: 20,
    chunk_size: 10,
    fps: 25
  },
  scanner: {
    interval: 120,
    stable_time: 10,
    min_file_count: 1
  },
  redis: {
    host: 'localhost',
    port: 6379,
    db: 0,
    password: null
  },
  worker: {
    num_workers: 4,
    download_concurrent: 4,
    upload_concurrent: 4
  }
})

const strategyOptions = [
  { label: 'Nearest (最近邻)', value: 'nearest' },
  { label: 'Chunking (动作分块)', value: 'chunking' },
  { label: 'Window (时间窗口)', value: 'window' }
]

// ============ Scanner 相关 ============
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
  },
  progress: {
    scanning: false,
    phase: '',
    current: 0,
    total: 0,
    message: '',
    eta_seconds: null
  }
})

// ============ Worker 相关 ============
const workerStatus = reactive({
  running: false,
  num_workers: 4,
  active_workers: 0,
  started_at: null
})

// ============ 系统监控相关 ============
const systemStats = reactive({
  cpu_percent: 0,
  cpu_count: 1,
  memory_total: 0,
  memory_used: 0,
  memory_percent: 0,
  disk_total: 0,
  disk_used: 0,
  disk_percent: 0
})

// 计算 Worker 线程说明
const workerThreadInfo = computed(() => {
  const workers = form.worker.num_workers
  const download = form.worker.download_concurrent
  const upload = form.worker.upload_concurrent
  const maxConn = workers * Math.max(download, upload)
  return {
    workers,
    download,
    upload,
    maxConn
  }
})

// 计算扫描进度百分比
const scanProgressPercent = computed(() => {
  const progress = scannerStatus.progress
  if (!progress.scanning && progress.phase !== 'publishing') {
    return progress.phase === 'done' ? 100 : 0
  }
  if (progress.phase === 'listing' || progress.phase === 'validating') {
    // 列出和验证阶段显示不确定进度
    return -1 // -1 表示 indeterminate
  }
  if (progress.total === 0) return 0
  return Math.round((progress.current / progress.total) * 100)
})

// 格式化预估剩余时间
const formatEta = (seconds) => {
  if (!seconds || seconds <= 0) return ''
  if (seconds < 60) return `约 ${seconds} 秒`
  if (seconds < 3600) {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return secs > 0 ? `约 ${mins} 分 ${secs} 秒` : `约 ${mins} 分钟`
  }
  const hours = Math.floor(seconds / 3600)
  const mins = Math.floor((seconds % 3600) / 60)
  return mins > 0 ? `约 ${hours} 小时 ${mins} 分` : `约 ${hours} 小时`
}

// 进度条 tooltip 内容
const progressTooltip = computed(() => {
  const progress = scannerStatus.progress
  let text = progress.message || ''

  // 添加进度百分比
  if (progress.phase === 'publishing' && progress.total > 0) {
    const percent = Math.round((progress.current / progress.total) * 100)
    text = `${progress.message} (${percent}%)`
  }

  // 添加 ETA
  if (progress.eta_seconds && progress.eta_seconds > 0) {
    text += ` - 预计剩余 ${formatEta(progress.eta_seconds)}`
  }

  return text
})

// 格式化字节
const formatBytes = (bytes) => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}

const scannerLoading = ref(false)
const workerLoading = ref(false)

let statusInterval = null

// ============ 配置方法 ============
const loadConfig = async () => {
  configLoading.value = true
  try {
    const { data } = await getConfig()
    Object.assign(form, data)
  } catch (error) {
    console.error('Failed to load config:', error)
    ElMessage.error('加载配置失败')
  } finally {
    configLoading.value = false
  }
}

const saveConfig = async () => {
  configLoading.value = true
  try {
    const { data } = await updateConfig(form)
    if (data.success) {
      ElMessage.success(data.message || '配置已保存')
    } else {
      ElMessage.error(data.message || '保存失败')
    }
  } catch (error) {
    console.error('Failed to save config:', error)
    ElMessage.error('保存配置失败')
  } finally {
    configLoading.value = false
  }
}

const testBos = async () => {
  testLoading.value = true
  testResult.value = null
  try {
    const { data } = await testBosConnection(form)
    testResult.value = data
    if (data.success) {
      ElMessage.success(data.message)
    } else {
      ElMessage.warning(data.message)
    }
  } catch (error) {
    console.error('Failed to test BOS:', error)
    ElMessage.error('测试连接失败')
    testResult.value = { success: false, message: '测试连接失败' }
  } finally {
    testLoading.value = false
  }
}

const resetForm = () => {
  loadConfig()
}

// ============ Scanner/Worker 方法 ============
const refreshStatus = async () => {
  try {
    const [scannerRes, workerRes, systemRes] = await Promise.all([
      getScannerStatus(),
      getWorkerStatus(),
      getSystemStats()
    ])
    Object.assign(scannerStatus, scannerRes.data)
    Object.assign(workerStatus, workerRes.data)
    Object.assign(systemStats, systemRes.data)
  } catch (error) {
    console.error('Failed to refresh status:', error)
  }
}

const startContinuousScan = async () => {
  scannerLoading.value = true
  try {
    const { data } = await startScanner({
      mode: 'continuous',
      interval: form.scanner.interval
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

const startWork = async () => {
  workerLoading.value = true
  try {
    const { data } = await startWorkers({
      num_workers: form.worker.num_workers
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

const formatTime = (isoString) => {
  if (!isoString) return '-'
  const date = new Date(isoString)
  return date.toLocaleString('zh-CN')
}

onMounted(() => {
  loadConfig()
  refreshStatus()
  statusInterval = setInterval(refreshStatus, 3000)
})

onUnmounted(() => {
  if (statusInterval) {
    clearInterval(statusInterval)
  }
})
</script>

<template>
  <div class="control-panel" v-loading="configLoading">
    <el-form :model="form" label-position="top" size="small">
      <!-- 第一行：BOS 连接 + 数据路径 -->
      <el-row :gutter="16" class="panel-row">
        <el-col :span="12">
          <el-card class="panel-card">
            <template #header>
              <div class="card-header">
                <span><el-icon><Connection /></el-icon> BOS 连接</span>
                <div class="header-actions">
                  <span v-if="testResult" class="test-result" :class="testResult.success ? 'success' : 'warning'">
                    <el-icon v-if="testResult.success"><CircleCheck /></el-icon>
                    <el-icon v-else><Warning /></el-icon>
                    {{ testResult.message }}
                  </span>
                  <el-button type="primary" size="small" :loading="testLoading" @click="testBos">
                    测试连接
                  </el-button>
                </div>
              </div>
            </template>

            <el-row :gutter="12">
              <el-col :span="16">
                <el-form-item label="Endpoint">
                  <el-input v-model="form.bos.endpoint" placeholder="https://s3.bj.bcebos.com" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="Region">
                  <el-input v-model="form.bos.region" placeholder="bj" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-form-item label="Bucket">
              <el-input v-model="form.bos.bucket" placeholder="srgdata" />
            </el-form-item>
            <el-row :gutter="12">
              <el-col :span="12">
                <el-form-item label="Access Key">
                  <el-input
                    v-model="form.bos.access_key"
                    :type="showAccessKey ? 'text' : 'password'"
                    placeholder="AK"
                  >
                    <template #suffix>
                      <el-icon class="cursor-pointer" @click="showAccessKey = !showAccessKey">
                        <View v-if="showAccessKey" /><Hide v-else />
                      </el-icon>
                    </template>
                  </el-input>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="Secret Key">
                  <el-input
                    v-model="form.bos.secret_key"
                    :type="showSecretKey ? 'text' : 'password'"
                    placeholder="SK"
                  >
                    <template #suffix>
                      <el-icon class="cursor-pointer" @click="showSecretKey = !showSecretKey">
                        <View v-if="showSecretKey" /><Hide v-else />
                      </el-icon>
                    </template>
                  </el-input>
                </el-form-item>
              </el-col>
            </el-row>

          </el-card>
        </el-col>

        <el-col :span="12">
          <el-card class="panel-card">
            <template #header>
              <span><el-icon><FolderOpened /></el-icon> 数据路径</span>
            </template>

            <el-form-item label="原始数据路径 (Raw Data)">
              <el-input v-model="form.paths.raw_data" placeholder="robot/raw_data/upload_test/fold_laundry" />
            </el-form-item>
            <el-form-item label="输出路径 (Converted)">
              <el-input v-model="form.paths.converted" placeholder="robot/raw_data/upload_test/converted_test" />
            </el-form-item>
            <el-form-item label="任务名称 (Task Name)">
              <el-input v-model="form.paths.task_name" placeholder="fold_laundry" />
            </el-form-item>
          </el-card>
        </el-col>
      </el-row>

      <!-- 第二行：Scanner 控制 + Worker 控制 -->
      <el-row :gutter="16" class="panel-row control-row">
        <el-col :span="12">
          <el-card class="panel-card scanner-card">
            <template #header>
              <div class="card-header">
                <span><el-icon><Search /></el-icon> Scanner 控制</span>
                <el-tag :type="scannerStatus.running ? 'success' : 'info'" effect="dark" size="small">
                  {{ scannerStatus.running ? '运行中' : '已停止' }}
                </el-tag>
              </div>
            </template>

            <div class="card-body-content">
              <el-row :gutter="12">
                <el-col :span="12">
                  <div class="scan-mode-box">
                    <div class="mode-title">
                      <el-icon color="#409eff"><Refresh /></el-icon>
                      <span>持续扫描</span>
                    </div>
                    <el-form-item label="扫描间隔(秒)">
                      <el-input-number
                        v-model="form.scanner.interval"
                        :min="10"
                        :max="3600"
                        :controls="false"
                        :disabled="scannerStatus.running"
                        style="width: 100%"
                      />
                    </el-form-item>
                    <el-button
                      type="primary"
                      :loading="scannerLoading"
                      :disabled="scannerStatus.running"
                      @click="startContinuousScan"
                      style="width: 100%"
                    >
                      <el-icon><CaretRight /></el-icon> 启动
                    </el-button>
                  </div>
                </el-col>
                <el-col :span="12">
                  <div class="scan-mode-box">
                    <div class="mode-title">
                      <el-icon color="#67c23a"><List /></el-icon>
                      <span>全量扫描</span>
                    </div>
                    <el-form-item label="稳定时间(秒)">
                      <el-input-number
                        v-model="form.scanner.stable_time"
                        :min="0"
                        :max="600"
                        :controls="false"
                        :disabled="scannerStatus.running"
                        style="width: 100%"
                      />
                    </el-form-item>
                    <el-button
                      type="success"
                      :loading="scannerLoading"
                      :disabled="scannerStatus.running"
                      @click="startFullScan"
                      style="width: 100%"
                    >
                      <el-icon><CaretRight /></el-icon> 启动
                    </el-button>
                  </div>
                </el-col>
              </el-row>

              <div class="status-row">
                <div class="stat-item">
                  <span class="stat-label">模式</span>
                  <span class="stat-value">{{ scannerStatus.mode === 'continuous' ? '持续' : scannerStatus.mode === 'once' ? '全量' : '-' }}</span>
                </div>
                <div class="stat-item">
                  <span class="stat-label">发现</span>
                  <span class="stat-value">{{ scannerStatus.stats.found }}</span>
                </div>
                <div class="stat-item">
                  <span class="stat-label">就绪</span>
                  <span class="stat-value">{{ scannerStatus.stats.ready }}</span>
                </div>
                <div class="stat-item">
                  <span class="stat-label">已发布</span>
                  <span class="stat-value">{{ scannerStatus.stats.published }}</span>
                </div>
              </div>
            </div>

            <div v-if="scannerStatus.running" class="card-footer-action">
              <span class="time-text">上次扫描: {{ formatTime(scannerStatus.last_scan_at) }}</span>
              <el-button type="danger" size="small" :loading="scannerLoading" @click="stopScan">
                <el-icon><VideoPause /></el-icon> 停止
              </el-button>
            </div>

            <!-- 底部进度条 -->
            <div v-if="scannerStatus.progress.scanning || scannerStatus.progress.phase === 'done'" class="scan-progress-bar">
              <el-tooltip :content="progressTooltip" placement="top">
                <el-progress
                  :percentage="scanProgressPercent >= 0 ? scanProgressPercent : 50"
                  :indeterminate="scanProgressPercent < 0"
                  :stroke-width="4"
                  :show-text="false"
                  :status="scannerStatus.progress.phase === 'error' ? 'exception' : scannerStatus.progress.phase === 'done' ? 'success' : ''"
                />
              </el-tooltip>
            </div>
          </el-card>
        </el-col>

        <el-col :span="12">
          <el-card class="panel-card">
            <template #header>
              <div class="card-header">
                <span><el-icon><Cpu /></el-icon> Worker 控制</span>
                <el-tag :type="workerStatus.running ? 'success' : 'info'" effect="dark" size="small">
                  {{ workerStatus.running ? `运行中 (${workerStatus.active_workers}/${workerStatus.num_workers})` : '已停止' }}
                </el-tag>
              </div>
            </template>

            <el-row :gutter="12">
              <el-col :span="8">
                <el-form-item label="Worker 数量">
                  <el-input-number
                    v-model="form.worker.num_workers"
                    :min="1"
                    :max="16"
                    :controls="false"
                    :disabled="workerStatus.running"
                    style="width: 100%"
                  />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="下载并发">
                  <el-input-number
                    v-model="form.worker.download_concurrent"
                    :min="1"
                    :max="16"
                    :controls="false"
                    :disabled="workerStatus.running"
                    style="width: 100%"
                  />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="上传并发">
                  <el-input-number
                    v-model="form.worker.upload_concurrent"
                    :min="1"
                    :max="16"
                    :controls="false"
                    :disabled="workerStatus.running"
                    style="width: 100%"
                  />
                </el-form-item>
              </el-col>
            </el-row>

            <!-- Worker 线程说明 -->
            <div class="thread-info">
              <el-icon><InfoFilled /></el-icon>
              <span>
                {{ workerThreadInfo.workers }} 个 Worker 线程并行处理任务
                (系统共 {{ systemStats.cpu_count }} 核)，
                每个 Worker 下载/上传最多 {{ Math.max(workerThreadInfo.download, workerThreadInfo.upload) }} 个文件并发，
                最大 BOS 连接数: {{ workerThreadInfo.maxConn }}
              </span>
            </div>

            <el-divider content-position="left">转换参数</el-divider>

            <el-row :gutter="12">
              <el-col :span="12">
                <el-form-item label="对齐策略">
                  <el-select v-model="form.conversion.strategy" style="width: 100%" :disabled="workerStatus.running">
                    <el-option v-for="opt in strategyOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="6">
                <el-form-item label="容差(ms)">
                  <el-input-number v-model="form.conversion.tolerance_ms" :min="1" :max="1000" :controls="false" :disabled="workerStatus.running" style="width: 100%" />
                </el-form-item>
              </el-col>
              <el-col :span="6">
                <el-form-item label="FPS">
                  <el-input-number v-model="form.conversion.fps" :min="1" :max="120" :controls="false" :disabled="workerStatus.running" style="width: 100%" />
                </el-form-item>
              </el-col>
            </el-row>

            <div class="worker-actions">
              <el-button
                v-if="!workerStatus.running"
                type="primary"
                :loading="workerLoading"
                @click="startWork"
                style="width: 100%"
              >
                <el-icon><CaretRight /></el-icon> 启动 Workers
              </el-button>
              <el-button
                v-else
                type="danger"
                :loading="workerLoading"
                @click="stopWork"
                style="width: 100%"
              >
                <el-icon><VideoPause /></el-icon> 停止 Workers
              </el-button>
            </div>

            <div v-if="workerStatus.running" class="time-text" style="margin-top: 8px;">
              启动时间: {{ formatTime(workerStatus.started_at) }}
            </div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 第三行：Redis + 性能监控 -->
      <el-row :gutter="16" class="panel-row">
        <el-col :span="12">
          <el-card class="panel-card">
            <template #header>
              <span><el-icon><Coin /></el-icon> Redis</span>
            </template>

            <el-row :gutter="12">
              <el-col :span="12">
                <el-form-item label="Host">
                  <el-input v-model="form.redis.host" placeholder="localhost" />
                </el-form-item>
              </el-col>
              <el-col :span="6">
                <el-form-item label="Port">
                  <el-input-number v-model="form.redis.port" :min="1" :max="65535" :controls="false" style="width: 100%" />
                </el-form-item>
              </el-col>
              <el-col :span="6">
                <el-form-item label="DB">
                  <el-input-number v-model="form.redis.db" :min="0" :max="15" :controls="false" style="width: 100%" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-form-item label="Password (可选)">
              <el-input v-model="form.redis.password" type="password" placeholder="无密码留空" show-password />
            </el-form-item>
          </el-card>
        </el-col>

        <!-- 性能监控 -->
        <el-col :span="12">
          <el-card class="panel-card">
            <template #header>
              <span><el-icon><Monitor /></el-icon> 系统监控</span>
            </template>

            <div class="system-stats">
              <div class="stat-row">
                <div class="stat-item-sys">
                  <div class="stat-header">
                    <span class="stat-label-sys">CPU</span>
                    <span class="stat-value-sys">{{ systemStats.cpu_percent.toFixed(1) }}%</span>
                  </div>
                  <el-progress
                    :percentage="systemStats.cpu_percent"
                    :stroke-width="8"
                    :show-text="false"
                    :color="systemStats.cpu_percent > 80 ? '#f56c6c' : systemStats.cpu_percent > 50 ? '#e6a23c' : '#67c23a'"
                  />
                  <div class="stat-detail">{{ systemStats.cpu_count }} 核心</div>
                </div>
                <div class="stat-item-sys">
                  <div class="stat-header">
                    <span class="stat-label-sys">内存</span>
                    <span class="stat-value-sys">{{ systemStats.memory_percent.toFixed(1) }}%</span>
                  </div>
                  <el-progress
                    :percentage="systemStats.memory_percent"
                    :stroke-width="8"
                    :show-text="false"
                    :color="systemStats.memory_percent > 80 ? '#f56c6c' : systemStats.memory_percent > 50 ? '#e6a23c' : '#67c23a'"
                  />
                  <div class="stat-detail">{{ formatBytes(systemStats.memory_used) }} / {{ formatBytes(systemStats.memory_total) }}</div>
                </div>
                <div class="stat-item-sys">
                  <div class="stat-header">
                    <span class="stat-label-sys">磁盘</span>
                    <span class="stat-value-sys">{{ systemStats.disk_percent.toFixed(1) }}%</span>
                  </div>
                  <el-progress
                    :percentage="systemStats.disk_percent"
                    :stroke-width="8"
                    :show-text="false"
                    :color="systemStats.disk_percent > 90 ? '#f56c6c' : systemStats.disk_percent > 70 ? '#e6a23c' : '#67c23a'"
                  />
                  <div class="stat-detail">{{ formatBytes(systemStats.disk_used) }} / {{ formatBytes(systemStats.disk_total) }}</div>
                </div>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 操作按钮 -->
      <div class="form-actions">
        <el-button size="large" @click="resetForm">重置</el-button>
        <el-button size="large" type="primary" @click="saveConfig">保存配置</el-button>
      </div>
    </el-form>
  </div>
</template>

<style scoped>
.control-panel {
  width: 100%;
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: auto;
}

.control-panel > .el-form {
  flex: 1;
}

.panel-row {
  margin-bottom: 20px;
}

.panel-row > .el-col {
  display: flex;
  padding-left: 10px !important;
  padding-right: 10px !important;
}

.panel-card {
  flex: 1;
  border-radius: 12px;
  border: 1px solid rgba(102, 126, 234, 0.1);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
  transition: all 0.3s ease;
  display: flex;
  flex-direction: column;
  background: linear-gradient(180deg, #ffffff 0%, #fafbfc 100%);
}

.panel-card:hover {
  box-shadow: 0 8px 24px rgba(102, 126, 234, 0.12);
  border-color: rgba(102, 126, 234, 0.2);
  transform: translateY(-2px);
}

.panel-card :deep(.el-card__header) {
  background: linear-gradient(135deg, #f8f9ff 0%, #f0f4ff 100%);
  border-bottom: 1px solid rgba(102, 126, 234, 0.1);
  padding: 12px 18px;
  border-radius: 12px 12px 0 0;
}

.panel-card :deep(.el-card__body) {
  padding: 18px;
  flex: 1;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header span,
.panel-card :deep(.el-card__header) > span {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 14px;
  color: #303133;
}

.card-header span .el-icon,
.panel-card :deep(.el-card__header) > span .el-icon {
  color: #667eea;
  font-size: 16px;
}

.panel-card :deep(.el-form-item) {
  margin-bottom: 14px;
}

.panel-card :deep(.el-form-item:last-child) {
  margin-bottom: 0;
}

.panel-card :deep(.el-form-item__label) {
  font-size: 12px;
  color: #606266;
  font-weight: 500;
  padding-bottom: 4px;
}

/* 控制行 - 让两个卡片高度一致 */
.control-row {
  align-items: stretch;
}

.control-row > .el-col {
  display: flex;
}

.control-row .panel-card {
  display: flex;
  flex-direction: column;
  width: 100%;
}

.control-row .panel-card :deep(.el-card__body) {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.card-body-content {
  flex: 1;
}

.card-footer-action {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #f0f2f5;
}

/* Scanner 模式框 */
.scan-mode-box {
  padding: 12px;
  border: 1px solid #f0f2f5;
  border-radius: 8px;
  background: #fafafa;
}

.mode-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
  font-size: 13px;
  margin-bottom: 10px;
  color: #303133;
}

.scan-mode-box .el-button--primary {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
}

.scan-mode-box .el-button--success {
  background: linear-gradient(135deg, #67c23a 0%, #95d475 100%);
  border: none;
}

/* Scanner 卡片 - 为底部进度条预留空间 */
.scanner-card {
  position: relative;
}

.scanner-card :deep(.el-card__body) {
  padding-bottom: 24px;
}

/* Header 右侧操作区 */
.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.test-result {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  font-weight: 500;
}

.test-result.success {
  color: #16a34a;
}

.test-result.warning {
  color: #d97706;
}

.test-result .el-icon {
  font-size: 14px;
}

/* Scanner 底部进度条 */
.scan-progress-bar {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 0 12px 8px;
}

.scan-progress-bar :deep(.el-progress-bar__outer) {
  background: rgba(102, 126, 234, 0.15);
  border-radius: 2px;
}

.scan-progress-bar :deep(.el-progress-bar__inner) {
  background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
  border-radius: 2px;
}

/* Scanner 状态行 */
.status-row {
  display: flex;
  justify-content: space-between;
  margin-top: 12px;
  padding: 10px;
  background: #f8f9fa;
  border-radius: 6px;
}

.stat-item {
  text-align: center;
}

.stat-label {
  font-size: 11px;
  color: #909399;
  display: block;
}

.stat-value {
  font-size: 16px;
  font-weight: 700;
  color: #667eea;
}

.action-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 10px;
}

.time-text {
  font-size: 12px;
  color: #909399;
}

/* Worker 卡片 */
.panel-card :deep(.el-divider__text) {
  font-size: 12px;
  color: #909399;
}

.worker-actions {
  margin-top: 12px;
}

.worker-actions .el-button--primary {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
}

/* 操作按钮 - 居中显示 */
.form-actions {
  display: flex;
  justify-content: center;
  gap: 24px;
  padding: 16px 0;
}

.form-actions .el-button {
  min-width: 140px;
  font-size: 15px;
}

.form-actions .el-button--primary {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
}

.form-actions .el-button--primary:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(102, 126, 234, 0.4);
}

.cursor-pointer {
  cursor: pointer;
}

/* 测试连接按钮 */
.card-header .el-button--primary {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
  border-radius: 6px;
  font-size: 12px;
}

/* Worker 线程说明 */
.thread-info {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  padding: 8px 10px;
  background: linear-gradient(135deg, #f0f5ff 0%, #e8f4f8 100%);
  border-radius: 6px;
  margin-top: 8px;
  font-size: 12px;
  color: #606266;
  line-height: 1.5;
}

.thread-info .el-icon {
  color: #409eff;
  flex-shrink: 0;
  margin-top: 2px;
}

/* 系统监控 */
.system-stats {
  padding: 4px 0;
}

.system-stats .stat-row {
  display: flex;
  gap: 16px;
}

.stat-item-sys {
  flex: 1;
  padding: 10px;
  background: #f8f9fa;
  border-radius: 8px;
}

.stat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.stat-label-sys {
  font-size: 12px;
  color: #909399;
  font-weight: 500;
}

.stat-value-sys {
  font-size: 14px;
  font-weight: 700;
  color: #303133;
}

.stat-detail {
  font-size: 11px;
  color: #909399;
  margin-top: 6px;
  text-align: center;
}
</style>
