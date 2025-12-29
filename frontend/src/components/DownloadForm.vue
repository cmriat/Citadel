<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { Icon } from '@iconify/vue'
import { ElMessage } from 'element-plus'
import { startDownload, checkConnection } from '@/api/download'
import type { DownloadConfig, ConnectionCheck } from '@/api/download'
import ValidatedInput from '@/components/ValidatedInput.vue'
import TemplateSelector from '@/components/TemplateSelector.vue'

const emit = defineEmits<{
  'task-created': [taskId: string]
}>()

// Storage key for config persistence
const STORAGE_KEY = 'citadel_download_config'

// Default config
const defaultConfig: DownloadConfig = {
  bos_path: 'srgdata/robot/raw_data/',
  local_path: './data/raw',
  concurrency: 10
}

// Load config from localStorage
const loadConfig = (): DownloadConfig => {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved) {
      return { ...defaultConfig, ...JSON.parse(saved) }
    }
  } catch (e) {
    console.error('[DownloadForm] Failed to load config:', e)
  }
  return { ...defaultConfig }
}

// Save config to localStorage
const saveConfig = (config: DownloadConfig) => {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(config))
  } catch (e) {
    console.error('[DownloadForm] Failed to save config:', e)
  }
}

const loading = ref(false)
const checking = ref(false)
const connectionStatus = ref<ConnectionCheck | null>(null)
const form = reactive<DownloadConfig>(loadConfig())

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
    saveConfig(form)
    emit('task-created', task.id)
  } catch (e) {
    ElMessage.error((e as Error).message)
  } finally {
    loading.value = false
  }
}

const handleLoadTemplate = (config: Record<string, unknown>) => {
  Object.assign(form, config)
}
</script>

<template>
  <div class="download-form-container">
    <el-form :model="form" :rules="rules" label-position="top">
      <el-form-item label="BOS Path" prop="bos_path">
        <ValidatedInput
          v-model="form.bos_path"
          placeholder="srgdata/robot/raw_data/..."
          validation-type="bos-path"
          prefix-icon="mdi:cloud"
          :show-message="true"
        />
        <div class="form-hint">Remote path on Baidu Object Storage</div>
      </el-form-item>

      <el-form-item label="Local Path" prop="local_path">
        <ValidatedInput
          v-model="form.local_path"
          placeholder="./data/raw"
          validation-type="local-path"
          prefix-icon="mdi:folder"
          :show-message="true"
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
        <div class="actions-left">
          <TemplateSelector
            type="download"
            :current-config="form"
            @load-template="handleLoadTemplate"
          />
        </div>
        <div class="actions-right">
          <el-button @click="handleCheckConnection" :loading="checking">
            <Icon icon="mdi:connection" style="margin-right: 6px" />
            Check
          </el-button>
          <el-button type="primary" @click="handleStartDownload" :loading="loading">
            <Icon icon="mdi:download" style="margin-right: 6px" />
            Start Download
          </el-button>
        </div>
      </div>
    </el-form>
  </div>
</template>

<style scoped>
.download-form-container {
  max-width: 500px;
}

.form-hint {
  font-size: 12px;
  margin-top: 4px;
  color: var(--el-text-color-secondary);
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
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 32px;
}

.actions-left,
.actions-right {
  display: flex;
  gap: 8px;
}
</style>
