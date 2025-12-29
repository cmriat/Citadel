<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { Icon } from '@iconify/vue'
import { ElMessage } from 'element-plus'
import { startConvert, scanFiles } from '@/api/convert'
import type { ConvertConfig } from '@/api/convert'
import { useThemeStore } from '@/stores/theme'

const themeStore = useThemeStore()
const loading = ref(false)
const scanning = ref(false)
const scannedFiles = ref<string[]>([])

// 配置记忆功能
const STORAGE_KEY = 'citadel_convert_config'

// 默认配置
const defaultConfig: ConvertConfig = {
  input_dir: './data/raw',
  output_dir: './data/lerobot',
  robot_type: 'citadel',
  fps: 30,
  task: 'default_task',
  parallel_jobs: 4,
  file_pattern: 'episode_*.h5'
}

// 从localStorage读取配置
const loadConfig = (): ConvertConfig => {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved) {
      const parsed = JSON.parse(saved)
      console.log('[Convert] Loaded config from storage:', parsed)
      return { ...defaultConfig, ...parsed }
    }
  } catch (e) {
    console.error('[Convert] Failed to load config:', e)
  }
  return { ...defaultConfig }
}

// 保存配置到localStorage
const saveConfig = (config: ConvertConfig) => {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(config))
    console.log('[Convert] Saved config to storage:', config)
  } catch (e) {
    console.error('[Convert] Failed to save config:', e)
  }
}

const form = reactive<ConvertConfig>(loadConfig())

// 页面加载时恢复配置
onMounted(() => {
  console.log('[Convert] Page mounted, config restored from previous session')
})

const rules = {
  input_dir: [{ required: true, message: 'Input directory is required', trigger: 'blur' }],
  output_dir: [{ required: true, message: 'Output directory is required', trigger: 'blur' }]
}

const handleScanFiles = async () => {
  scanning.value = true
  try {
    scannedFiles.value = await scanFiles(form.input_dir, form.file_pattern)
    if (scannedFiles.value.length === 0) {
      ElMessage.warning('No files found matching the pattern')
    } else {
      ElMessage.success(`Found ${scannedFiles.value.length} files`)
    }
  } catch (e) {
    ElMessage.error((e as Error).message)
  } finally {
    scanning.value = false
  }
}

const handleStartConvert = async () => {
  loading.value = true
  try {
    const task = await startConvert(form)
    ElMessage.success(`Convert task created: ${task.id}`)
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
  <div class="convert-page" :class="themeStore.theme">
    <div class="page-card">
      <div class="card-header">
        <Icon icon="mdi:swap-horizontal" class="card-icon" />
        <div>
          <h2 class="card-title">Convert HDF5 to LeRobot</h2>
          <p class="card-desc">Transform raw HDF5 data to LeRobot v2.1 format</p>
        </div>
      </div>

      <el-form :model="form" :rules="rules" label-position="top" class="convert-form">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="Input Directory" prop="input_dir">
              <el-input
                v-model="form.input_dir"
                placeholder="./data/raw"
                :prefix-icon="() => h(Icon, { icon: 'mdi:folder-open' })"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="Output Directory" prop="output_dir">
              <el-input
                v-model="form.output_dir"
                placeholder="./data/lerobot"
                :prefix-icon="() => h(Icon, { icon: 'mdi:folder' })"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="Robot Type">
              <el-input v-model="form.robot_type" placeholder="citadel" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="FPS">
              <el-input-number v-model="form.fps" :min="1" :max="120" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="Parallel Jobs">
              <el-input-number v-model="form.parallel_jobs" :min="1" :max="16" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="Task Name">
          <el-input v-model="form.task" placeholder="default_task" />
        </el-form-item>

        <el-form-item label="File Pattern">
          <el-input v-model="form.file_pattern" placeholder="episode_*.h5">
            <template #append>
              <el-button @click="handleScanFiles" :loading="scanning">
                Scan
              </el-button>
            </template>
          </el-input>
        </el-form-item>

        <!-- Scanned Files Preview -->
        <div v-if="scannedFiles.length > 0" class="files-preview">
          <div class="preview-header">
            <Icon icon="mdi:file-multiple" />
            <span>{{ scannedFiles.length }} files to convert</span>
          </div>
          <div class="files-list">
            <div v-for="file in scannedFiles.slice(0, 10)" :key="file" class="file-item">
              <Icon icon="mdi:file" />
              {{ file }}
            </div>
            <div v-if="scannedFiles.length > 10" class="file-item more">
              ... and {{ scannedFiles.length - 10 }} more files
            </div>
          </div>
        </div>

        <div class="form-actions">
          <el-button type="primary" @click="handleStartConvert" :loading="loading" :disabled="scannedFiles.length === 0">
            <Icon icon="mdi:play" style="margin-right: 6px" />
            Start Convert
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
.convert-page {
  max-width: 800px;
  margin: 0 auto;
}

.page-card {
  border-radius: 12px;
  padding: 32px;
  border: 1px solid;
  transition: all 0.3s ease;
}

/* Dark theme */
.convert-page.dark .page-card {
  background-color: #1a1a2e;
  border-color: #2a2a4e;
}

.convert-page.dark .card-title {
  color: #fff;
}

.convert-page.dark .card-desc {
  color: #6a6a8a;
}

.convert-page.dark .files-preview {
  background-color: #252545;
}

.convert-page.dark .file-item {
  color: #a0a0c0;
}

.convert-page.dark .file-item.more {
  color: #6a6a8a;
}

/* Light theme */
.convert-page.light .page-card {
  background-color: #ffffff;
  border-color: #e4e7ed;
}

.convert-page.light .card-title {
  color: #303133;
}

.convert-page.light .card-desc {
  color: #909399;
}

.convert-page.light .files-preview {
  background-color: #f5f7fa;
}

.convert-page.light .file-item {
  color: #606266;
}

.convert-page.light .file-item.more {
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
  color: #e6a23c;
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

.convert-form {
  max-width: 700px;
}

.files-preview {
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

.files-list {
  max-height: 200px;
  overflow-y: auto;
}

.file-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
  font-size: 13px;
}

.file-item.more {
  font-style: italic;
}

.form-actions {
  margin-top: 32px;
}
</style>
