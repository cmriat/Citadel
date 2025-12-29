<script setup lang="ts">
import { ref, reactive } from 'vue'
import { Icon } from '@iconify/vue'
import { ElMessage } from 'element-plus'
import { startUpload, scanDirs } from '@/api/upload'
import type { UploadConfig, UploadableDir } from '@/api/upload'
import ValidatedInput from '@/components/ValidatedInput.vue'
import TemplateSelector from '@/components/TemplateSelector.vue'

const emit = defineEmits<{
  'task-created': [taskId: string]
}>()

const STORAGE_KEY = 'citadel_upload_config'

const defaultConfig: UploadConfig = {
  local_dir: './data/lerobot',
  bos_path: 'bos:/citadel-bos/lerobot_output/',
  concurrency: 10,
  include_videos: true,
  delete_after: false
}

const loadConfig = (): UploadConfig => {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved) {
      return { ...defaultConfig, ...JSON.parse(saved) }
    }
  } catch (e) {
    console.error('[UploadForm] Failed to load config:', e)
  }
  return { ...defaultConfig }
}

const saveConfig = (config: UploadConfig) => {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(config))
  } catch (e) {
    console.error('[UploadForm] Failed to save config:', e)
  }
}

const loading = ref(false)
const scanning = ref(false)
const scannedDirs = ref<UploadableDir[]>([])
const form = reactive<UploadConfig>(loadConfig())

const rules = {
  local_dir: [{ required: true, message: 'Local directory is required', trigger: 'blur' }],
  bos_path: [{ required: true, message: 'BOS path is required', trigger: 'blur' }]
}

const formatSize = (bytes: number) => {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  if (bytes < 1024 * 1024 * 1024) return (bytes / 1024 / 1024).toFixed(1) + ' MB'
  return (bytes / 1024 / 1024 / 1024).toFixed(2) + ' GB'
}

const handleScanDirs = async () => {
  scanning.value = true
  try {
    scannedDirs.value = await scanDirs(form.local_dir)
    if (scannedDirs.value.length === 0) {
      ElMessage.warning('No uploadable directories found')
    } else {
      ElMessage.success(`Found ${scannedDirs.value.length} directories`)
    }
  } catch (e) {
    ElMessage.error((e as Error).message)
  } finally {
    scanning.value = false
  }
}

const handleStartUpload = async () => {
  loading.value = true
  try {
    const task = await startUpload(form)
    ElMessage.success(`Upload task created: ${task.id}`)
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
  <div class="upload-form-container">
    <el-form :model="form" :rules="rules" label-position="top">
      <el-form-item label="Local Directory" prop="local_dir">
        <ValidatedInput
          v-model="form.local_dir"
          placeholder="./data/lerobot"
          validation-type="local-path"
          prefix-icon="mdi:folder"
        >
          <template #append>
            <el-button @click="handleScanDirs" :loading="scanning">
              Scan
            </el-button>
          </template>
        </ValidatedInput>
        <div class="form-hint">Local LeRobot format directory</div>
      </el-form-item>

      <el-form-item label="BOS Target Path" prop="bos_path">
        <ValidatedInput
          v-model="form.bos_path"
          placeholder="bos:/bucket/path/"
          validation-type="bos-path"
          prefix-icon="mdi:cloud-upload"
        />
        <div class="form-hint">Remote path on Baidu Object Storage</div>
      </el-form-item>

      <el-form-item label="Concurrency">
        <el-slider
          v-model="form.concurrency"
          :min="1"
          :max="20"
          :step="1"
          show-input
        />
      </el-form-item>

      <el-row :gutter="20">
        <el-col :span="12">
          <el-form-item>
            <el-checkbox v-model="form.include_videos">
              Include video files
            </el-checkbox>
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item>
            <el-checkbox v-model="form.delete_after" class="danger-checkbox">
              Delete local files after upload
            </el-checkbox>
          </el-form-item>
        </el-col>
      </el-row>

      <!-- Scanned Dirs Preview -->
      <div v-if="scannedDirs.length > 0" class="dirs-preview">
        <div class="preview-header">
          <Icon icon="mdi:folder-multiple" />
          <span>{{ scannedDirs.length }} directories to upload</span>
        </div>
        <div class="dirs-list">
          <div v-for="dir in scannedDirs" :key="dir.path" class="dir-item">
            <div class="dir-info">
              <Icon icon="mdi:folder" />
              <span class="dir-name">{{ dir.name }}</span>
            </div>
            <div class="dir-meta">
              <span>{{ dir.file_count }} files</span>
              <span>{{ formatSize(dir.size) }}</span>
            </div>
          </div>
        </div>
      </div>

      <div class="form-actions">
        <div class="actions-left">
          <TemplateSelector
            type="upload"
            :current-config="form"
            @load-template="handleLoadTemplate"
          />
        </div>
        <div class="actions-right">
          <el-button type="primary" @click="handleStartUpload" :loading="loading">
            <Icon icon="mdi:upload" style="margin-right: 6px" />
            Start Upload
          </el-button>
        </div>
      </div>
    </el-form>
  </div>
</template>

<style scoped>
.upload-form-container {
  max-width: 500px;
}

.form-hint {
  font-size: 12px;
  margin-top: 4px;
  color: var(--el-text-color-secondary);
}

.danger-checkbox :deep(.el-checkbox__label) {
  color: #f56c6c;
}

.dirs-preview {
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 24px;
  background-color: var(--el-fill-color-light);
}

.preview-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  color: #67c23a;
  margin-bottom: 12px;
}

.dirs-list {
  max-height: 200px;
  overflow-y: auto;
}

.dir-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.dir-item:last-child {
  border-bottom: none;
}

.dir-info {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--el-text-color-regular);
}

.dir-name {
  font-size: 13px;
}

.dir-meta {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
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
