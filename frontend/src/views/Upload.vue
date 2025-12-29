<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { Icon } from '@iconify/vue'
import { ElMessage } from 'element-plus'
import { startUpload, scanDirs } from '@/api/upload'
import type { UploadConfig, UploadableDir } from '@/api/upload'
import { useThemeStore } from '@/stores/theme'

const themeStore = useThemeStore()
const loading = ref(false)
const scanning = ref(false)
const scannedDirs = ref<UploadableDir[]>([])

// 配置记忆功能
const STORAGE_KEY = 'citadel_upload_config'

// 默认配置
const defaultConfig: UploadConfig = {
  local_dir: './data/lerobot',
  bos_path: 'bos:/citadel-bos/lerobot_output/',
  concurrency: 10,
  include_videos: true,
  delete_after: false
}

// 从localStorage读取配置
const loadConfig = (): UploadConfig => {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved) {
      const parsed = JSON.parse(saved)
      console.log('[Upload] Loaded config from storage:', parsed)
      return { ...defaultConfig, ...parsed }
    }
  } catch (e) {
    console.error('[Upload] Failed to load config:', e)
  }
  return { ...defaultConfig }
}

// 保存配置到localStorage
const saveConfig = (config: UploadConfig) => {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(config))
    console.log('[Upload] Saved config to storage:', config)
  } catch (e) {
    console.error('[Upload] Failed to save config:', e)
  }
}

const form = reactive<UploadConfig>(loadConfig())

// 页面加载时恢复配置
onMounted(() => {
  console.log('[Upload] Page mounted, config restored from previous session')
})

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
  <div class="upload-page" :class="themeStore.theme">
    <div class="page-card">
      <div class="card-header">
        <Icon icon="mdi:upload" class="card-icon" />
        <div>
          <h2 class="card-title">Upload to BOS</h2>
          <p class="card-desc">Upload converted LeRobot data to Baidu Object Storage</p>
        </div>
      </div>

      <el-form :model="form" :rules="rules" label-position="top" class="upload-form">
        <el-form-item label="Local Directory" prop="local_dir">
          <el-input
            v-model="form.local_dir"
            placeholder="./data/lerobot"
            :prefix-icon="() => h(Icon, { icon: 'mdi:folder' })"
          >
            <template #append>
              <el-button @click="handleScanDirs" :loading="scanning">
                Scan
              </el-button>
            </template>
          </el-input>
          <div class="form-hint">Local LeRobot format directory</div>
        </el-form-item>

        <el-form-item label="BOS Target Path" prop="bos_path">
          <el-input
            v-model="form.bos_path"
            placeholder="bos:/bucket/path/"
            :prefix-icon="() => h(Icon, { icon: 'mdi:cloud-upload' })"
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
          <el-button type="primary" @click="handleStartUpload" :loading="loading">
            <Icon icon="mdi:upload" style="margin-right: 6px" />
            Start Upload
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
.upload-page {
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
.upload-page.dark .page-card {
  background-color: #1a1a2e;
  border-color: #2a2a4e;
}

.upload-page.dark .card-title {
  color: #fff;
}

.upload-page.dark .card-desc,
.upload-page.dark .form-hint {
  color: #6a6a8a;
}

.upload-page.dark .dirs-preview {
  background-color: #252545;
}

.upload-page.dark .dir-info {
  color: #a0a0c0;
}

.upload-page.dark .dir-meta {
  color: #6a6a8a;
}

.upload-page.dark .dir-item {
  border-bottom-color: #3a3a5e;
}

/* Light theme */
.upload-page.light .page-card {
  background-color: #ffffff;
  border-color: #e4e7ed;
}

.upload-page.light .card-title {
  color: #303133;
}

.upload-page.light .card-desc,
.upload-page.light .form-hint {
  color: #909399;
}

.upload-page.light .dirs-preview {
  background-color: #f5f7fa;
}

.upload-page.light .dir-info {
  color: #606266;
}

.upload-page.light .dir-meta {
  color: #909399;
}

.upload-page.light .dir-item {
  border-bottom-color: #e4e7ed;
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
  color: #67c23a;
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

.upload-form {
  max-width: 500px;
}

.form-hint {
  font-size: 12px;
  margin-top: 4px;
}

.danger-checkbox :deep(.el-checkbox__label) {
  color: #f56c6c;
}

.dirs-preview {
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 24px;
  transition: background-color 0.3s ease;
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
  border-bottom: 1px solid;
}

.dir-item:last-child {
  border-bottom: none;
}

.dir-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.dir-name {
  font-size: 13px;
}

.dir-meta {
  display: flex;
  gap: 16px;
  font-size: 12px;
}

.form-actions {
  margin-top: 32px;
}
</style>
