<script setup lang="ts">
import { ref, reactive } from 'vue'
import { Icon } from '@iconify/vue'
import { ElMessage } from 'element-plus'
import { startConvert, scanFiles } from '@/api/convert'
import type { ConvertConfig } from '@/api/convert'
import ValidatedInput from '@/components/ValidatedInput.vue'
import TemplateSelector from '@/components/TemplateSelector.vue'

const emit = defineEmits<{
  'task-created': [taskId: string]
}>()

const STORAGE_KEY = 'citadel_convert_config'

const defaultConfig: ConvertConfig = {
  input_dir: './data/raw',
  output_dir: './data/lerobot',
  robot_type: 'citadel',
  fps: 30,
  task: 'default_task',
  parallel_jobs: 4,
  file_pattern: 'episode_*.h5'
}

const loadConfig = (): ConvertConfig => {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved) {
      return { ...defaultConfig, ...JSON.parse(saved) }
    }
  } catch (e) {
    console.error('[ConvertForm] Failed to load config:', e)
  }
  return { ...defaultConfig }
}

const saveConfig = (config: ConvertConfig) => {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(config))
  } catch (e) {
    console.error('[ConvertForm] Failed to save config:', e)
  }
}

const loading = ref(false)
const scanning = ref(false)
const scannedFiles = ref<string[]>([])
const form = reactive<ConvertConfig>(loadConfig())

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
  <div class="convert-form-container">
    <el-form :model="form" :rules="rules" label-position="top">
      <el-row :gutter="20">
        <el-col :span="12">
          <el-form-item label="Input Directory" prop="input_dir">
            <ValidatedInput
              v-model="form.input_dir"
              placeholder="./data/raw"
              validation-type="local-path"
              prefix-icon="mdi:folder-open"
            />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="Output Directory" prop="output_dir">
            <ValidatedInput
              v-model="form.output_dir"
              placeholder="./data/lerobot"
              validation-type="local-path"
              :check-writable="true"
              prefix-icon="mdi:folder"
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
        <div class="actions-left">
          <TemplateSelector
            type="convert"
            :current-config="form"
            @load-template="handleLoadTemplate"
          />
        </div>
        <div class="actions-right">
          <el-button type="primary" @click="handleStartConvert" :loading="loading" :disabled="scannedFiles.length === 0">
            <Icon icon="mdi:play" style="margin-right: 6px" />
            Start Convert
          </el-button>
        </div>
      </div>
    </el-form>
  </div>
</template>

<style scoped>
.convert-form-container {
  max-width: 700px;
}

.files-preview {
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
  color: var(--el-text-color-regular);
}

.file-item.more {
  font-style: italic;
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
