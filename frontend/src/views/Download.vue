<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { Icon } from '@iconify/vue'
import { ElMessage } from 'element-plus'
import { startDownload, checkConnection } from '@/api/download'
import type { DownloadConfig, ConnectionCheck } from '@/api/download'
import { useThemeStore } from '@/stores/theme'

console.log('[Download] Component setup called at:', new Date().toISOString())

const themeStore = useThemeStore()

// 配置记忆功能
const STORAGE_KEY = 'citadel_download_config'

// 默认配置
const defaultConfig: DownloadConfig = {
  bos_path: 'bos:/citadel-bos/online_test_hdf5_v1/',
  local_path: './data/raw',
  concurrency: 10
}

// 从localStorage读取配置
const loadConfig = (): DownloadConfig => {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved) {
      const parsed = JSON.parse(saved)
      console.log('[Download] Loaded config from storage:', parsed)
      return { ...defaultConfig, ...parsed }
    }
  } catch (e) {
    console.error('[Download] Failed to load config:', e)
  }
  return { ...defaultConfig }
}

// 保存配置到localStorage
const saveConfig = (config: DownloadConfig) => {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(config))
    console.log('[Download] Saved config to storage:', config)
  } catch (e) {
    console.error('[Download] Failed to save config:', e)
  }
}

const loading = ref(false)
const checking = ref(false)
const connectionStatus = ref<ConnectionCheck | null>(null)

const form = reactive<DownloadConfig>(loadConfig())

onMounted(() => {
  console.log('[Download] onMounted called, config restored from previous session')
})

onUnmounted(() => {
  console.log('[Download] onUnmounted called')
})

const rules = {
  bos_path: [{ required: true, message: 'BOS path is required', trigger: 'blur' }],
  local_path: [{ required: true, message: 'Local path is required', trigger: 'blur' }]
}

const handleCheckConnection = async () => {
  checking.value = true
  try {
    connectionStatus.value = await checkConnection()
    if (connectionStatus.value.connected) {
      ElMessage.success('BOS connection OK')
    } else {
      ElMessage.error(connectionStatus.value.error || 'Connection failed')
    }
  } catch (e) {
    ElMessage.error((e as Error).message)
  } finally {
    checking.value = false
  }
}

const handleStartDownload = async () => {
  loading.value = true
  try {
    const task = await startDownload(form)
    ElMessage.success(`Download task created: ${task.id}`)
    // 保存配置到localStorage
    saveConfig(form)
    ElMessage.info('Configuration saved for next time')
  } catch (e) {
    ElMessage.error((e as Error).message)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="download-page" :class="themeStore.theme">
    <div class="page-card">
      <div class="card-header">
        <Icon icon="mdi:download" class="card-icon" />
        <div>
          <h2 class="card-title">Download from BOS</h2>
          <p class="card-desc">Download HDF5 files from Baidu Object Storage</p>
        </div>
      </div>

      <el-form :model="form" :rules="rules" label-position="top" class="download-form">
        <el-form-item label="BOS Path" prop="bos_path">
          <el-input
            v-model="form.bos_path"
            placeholder="bos:/bucket/path/"
            :prefix-icon="() => h(Icon, { icon: 'mdi:cloud' })"
          />
          <div class="form-hint">Remote path on Baidu Object Storage</div>
        </el-form-item>

        <el-form-item label="Local Path" prop="local_path">
          <el-input
            v-model="form.local_path"
            placeholder="./data/raw"
            :prefix-icon="() => h(Icon, { icon: 'mdi:folder' })"
          />
          <div class="form-hint">Local directory to save downloaded files</div>
        </el-form-item>

        <el-form-item label="Concurrency">
          <el-slider
            v-model="form.concurrency"
            :min="1"
            :max="20"
            :step="1"
            show-input
          />
          <div class="form-hint">Number of parallel download threads</div>
        </el-form-item>

        <!-- Connection Status -->
        <div v-if="connectionStatus" class="connection-status" :class="{ connected: connectionStatus.connected }">
          <Icon :icon="connectionStatus.connected ? 'mdi:check-circle' : 'mdi:close-circle'" />
          <span v-if="connectionStatus.connected">
            Connected (mc {{ connectionStatus.mc_version }})
          </span>
          <span v-else>{{ connectionStatus.error }}</span>
        </div>

        <div class="form-actions">
          <el-button @click="handleCheckConnection" :loading="checking">
            <Icon icon="mdi:connection" style="margin-right: 6px" />
            Check Connection
          </el-button>
          <el-button type="primary" @click="handleStartDownload" :loading="loading">
            <Icon icon="mdi:download" style="margin-right: 6px" />
            Start Download
          </el-button>
        </div>
      </el-form>
    </div>
  </div>
</template>

<script lang="ts">
import { h } from 'vue'
export default {}
</script>

<style scoped>
.download-page {
  max-width: 700px;
  margin: 0 auto;
}

.page-card {
  border-radius: 12px;
  padding: 32px;
  border: 1px solid;
  transition: all 0.3s ease;
}

/* Dark theme */
.download-page.dark .page-card {
  background-color: #1a1a2e;
  border-color: #2a2a4e;
}

.download-page.dark .card-title {
  color: #fff;
}

.download-page.dark .card-desc,
.download-page.dark .form-hint {
  color: #6a6a8a;
}

/* Light theme */
.download-page.light .page-card {
  background-color: #ffffff;
  border-color: #e4e7ed;
}

.download-page.light .card-title {
  color: #303133;
}

.download-page.light .card-desc,
.download-page.light .form-hint {
  color: #909399;
}

/* Common styles */
.card-header {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 32px;
}

.card-icon {
  font-size: 40px;
  color: #409eff;
}

.card-title {
  font-size: 20px;
  font-weight: 600;
  margin: 0 0 4px 0;
}

.card-desc {
  font-size: 14px;
  margin: 0;
}

.download-form {
  max-width: 500px;
}

.form-hint {
  font-size: 12px;
  margin-top: 4px;
}

.connection-status {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  border-radius: 8px;
  background-color: #f56c6c20;
  color: #f56c6c;
  margin-bottom: 24px;
}

.connection-status.connected {
  background-color: #67c23a20;
  color: #67c23a;
}

.form-actions {
  display: flex;
  gap: 12px;
  margin-top: 32px;
}
</style>
