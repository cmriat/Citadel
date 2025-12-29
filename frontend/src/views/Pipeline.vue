<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted, onUnmounted } from 'vue'
import { Icon } from '@iconify/vue'
import { ElMessage } from 'element-plus'
import { useThemeStore } from '@/stores/theme'
import { useTaskStore } from '@/stores/tasks'
import {
  runStep, derivePaths, hasPathTemplate, resolvePath,
  checkDownloadReady, checkConvertReady, checkUploadReady,
  scanEpisodes, runUploadWithExclude
} from '@/api/pipeline'
import type { PipelineConfig, CheckResult, Episode } from '@/api/pipeline'
import ValidatedInput from '@/components/ValidatedInput.vue'
import EpisodeSelector from '@/components/EpisodeSelector.vue'
import TaskPreviewBar from '@/components/TaskPreviewBar.vue'

const themeStore = useThemeStore()
const taskStore = useTaskStore()
const STORAGE_KEY = 'citadel_pipeline_config'

const defaultConfig: PipelineConfig = {
  bos_source: 'bos:/citadel-bos/online_test_hdf5_v1/',
  bos_target: 'bos:/citadel-bos/lerobot_output/',
  local_dir: './data',
  robot_type: 'citadel',
  fps: 30,
  concurrency: 10,
  file_pattern: 'episode_*.h5',
  task_name: 'default_task'
}

const loadConfig = (): PipelineConfig => {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved) return { ...defaultConfig, ...JSON.parse(saved) }
  } catch (e) { console.error('[Pipeline] Failed to load config:', e) }
  return { ...defaultConfig }
}

const saveConfig = (config: PipelineConfig) => {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(config)) }
  catch (e) { console.error('[Pipeline] Failed to save config:', e) }
}

const config = reactive<PipelineConfig>(loadConfig())
const loading = ref<'download' | 'convert' | 'upload' | null>(null)
const paths = computed(() => derivePaths(config))

// ============ Status Check ============
interface StepStatus {
  ready: boolean | null  // null = checking
  count: number
  message: string
}

const status = reactive({
  download: { ready: null, count: 0, message: 'Click to check' } as StepStatus,
  convert: { ready: null, count: 0, message: 'Click to check' } as StepStatus,
  upload: { ready: null, count: 0, message: 'Click to check' } as StepStatus
})

const statusTooltips: Record<string, string> = {
  download: '检测 BOS 源路径是否有 HDF5 文件',
  convert: '检测本地 raw 目录是否有已下载的文件',
  upload: '检测本地 lerobot 目录是否有转换后的数据'
}

const checking = ref<'download' | 'convert' | 'upload' | 'all' | null>(null)

const runCheck = async (step: 'download' | 'convert' | 'upload') => {
  checking.value = step
  status[step] = { ready: null, count: 0, message: 'Checking...' }

  // 解析日期模板，确保状态检查使用正确的路径
  const resolvedDir = resolvePath(config.local_dir)

  let result: CheckResult
  switch (step) {
    case 'download':
      result = await checkDownloadReady(config.bos_source)
      break
    case 'convert':
      result = await checkConvertReady(resolvedDir)
      break
    case 'upload':
      result = await checkUploadReady(resolvedDir)
      break
  }

  status[step] = result
  checking.value = null
}

const runAllChecks = async () => {
  checking.value = 'all'
  await Promise.all([
    runCheck('download'),
    runCheck('convert'),
    runCheck('upload')
  ])
  checking.value = null
}

// ============ Actions ============
const handleRunStep = async (step: 'download' | 'convert' | 'upload') => {
  // Upload 步骤特殊处理：打开选择器
  if (step === 'upload') {
    await openEpisodeSelector()
    return
  }

  loading.value = step
  try {
    const task = await runStep(step, config)
    ElMessage.success(`${step} task: ${task.id}`)
    saveConfig(config)
    // Refresh status after task created
    setTimeout(() => runCheck(step === 'download' ? 'convert' : 'upload'), 1000)
  } catch (e) { ElMessage.error((e as Error).message) }
  finally { loading.value = null }
}


// ============ Episode Selector ============
const showEpisodeSelector = ref(false)
const episodes = ref<Episode[]>([])
const scanningEpisodes = ref(false)

const openEpisodeSelector = async () => {
  scanningEpisodes.value = true
  showEpisodeSelector.value = true
  try {
    // 解析日期模板，确保使用正确的路径
    const resolvedDir = resolvePath(config.local_dir)
    console.log('[openEpisodeSelector] config.local_dir:', config.local_dir)
    console.log('[openEpisodeSelector] resolvedDir:', resolvedDir)
    const result = await scanEpisodes(resolvedDir)
    console.log('[openEpisodeSelector] result:', result, 'length:', result?.length)
    episodes.value = result
  } finally {
    scanningEpisodes.value = false
  }
}

const handleUploadConfirm = async (excludeEpisodes: string[]) => {
  loading.value = 'upload'
  try {
    const task = await runUploadWithExclude(config, excludeEpisodes)
    const uploadCount = episodes.value.length - excludeEpisodes.length
    ElMessage.success(`Upload started: ${uploadCount} episodes (task: ${task.id})`)
    saveConfig(config)
    setTimeout(() => runCheck('upload'), 1000)
  } catch (e) {
    ElMessage.error((e as Error).message)
  } finally {
    loading.value = null
  }
}

// Auto-check on mount and start task polling
onMounted(() => {
  // Delay to allow backend to be ready
  setTimeout(runAllChecks, 500)
  // Start polling for task updates (for preview bar)
  taskStore.fetchTasks()
  taskStore.fetchStats()
  taskStore.startPolling(3000)
})

onUnmounted(() => {
  taskStore.stopPolling()
})
</script>

<template>
  <div class="pipeline-page" :class="themeStore.theme">
    <div class="pipeline-card">
      <!-- Compact Header -->
      <div class="header">
        <div class="header-icon"><Icon icon="mdi:pipe" /></div>
        <h1>Data Pipeline</h1>
        <el-button size="small" text @click="runAllChecks" :loading="checking === 'all'" title="Refresh all checks">
          <Icon icon="mdi:refresh" />
        </el-button>
      </div>

      <!-- Status Bar -->
      <div class="status-bar">
        <el-tooltip
          v-for="(step, key) in { download: 'Download', convert: 'Convert', upload: 'Upload' }"
          :key="key"
          :content="statusTooltips[key]"
          placement="top"
        >
          <div
            class="status-item"
            :class="{
              ready: status[key].ready === true,
              notready: status[key].ready === false,
              checking: status[key].ready === null
            }"
            @click="runCheck(key as 'download' | 'convert' | 'upload')"
          >
            <div class="status-icon">
              <Icon v-if="status[key].ready === null" icon="mdi:loading" class="spin" />
              <Icon v-else-if="status[key].ready" icon="mdi:check-circle" />
              <Icon v-else icon="mdi:close-circle" />
            </div>
            <div class="status-info">
              <span class="status-title">{{ step }}</span>
              <span class="status-msg">{{ status[key].message }}</span>
            </div>
          </div>
        </el-tooltip>
      </div>

      <!-- Compact Form -->
      <el-form label-position="top" class="compact-form">
        <!-- BOS Paths Row -->
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="BOS Source" class="compact-item">
              <ValidatedInput v-model="config.bos_source" placeholder="bos:/bucket/raw/" validation-type="bos-path" prefix-icon="mdi:cloud-download" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="BOS Target" class="compact-item">
              <ValidatedInput v-model="config.bos_target" placeholder="bos:/bucket/output/" validation-type="bos-path" prefix-icon="mdi:cloud-upload" />
            </el-form-item>
          </el-col>
        </el-row>

        <!-- Local Dir + Task Name -->
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="Local Directory" class="compact-item">
              <ValidatedInput v-model="config.local_dir" placeholder="./data/{date}" validation-type="local-path" prefix-icon="mdi:folder" />
              <div class="derived-paths">
                <span v-if="hasPathTemplate(config.local_dir)" class="template-hint">
                  <Icon icon="mdi:calendar-clock" />
                  运行时解析为:
                </span>
                <code>{{ paths.raw_dir }}</code> → <code>{{ paths.lerobot_dir }}</code>
              </div>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="Task Name" class="compact-item">
              <el-input v-model="config.task_name" placeholder="default_task" />
            </el-form-item>
          </el-col>
        </el-row>

        <!-- Settings Row -->
        <el-row :gutter="12">
          <el-col :span="6">
            <el-form-item label="Robot" class="compact-item">
              <el-input v-model="config.robot_type" placeholder="citadel" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="FPS" class="compact-item">
              <el-input-number v-model="config.fps" :min="1" :max="120" controls-position="right" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="Threads" class="compact-item">
              <el-input-number v-model="config.concurrency" :min="1" :max="20" controls-position="right" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="File Pattern" class="compact-item">
              <el-input v-model="config.file_pattern" placeholder="episode_*.h5" />
            </el-form-item>
          </el-col>
        </el-row>

        <!-- Action Buttons -->
        <div class="actions">
          <el-button type="primary" :loading="loading === 'download'" :disabled="loading !== null" @click="handleRunStep('download')" class="step-btn">
            <Icon icon="mdi:download" /> Download
          </el-button>
          <el-button type="success" :loading="loading === 'convert'" :disabled="loading !== null" @click="handleRunStep('convert')" class="step-btn">
            <Icon icon="mdi:swap-horizontal" /> Convert
          </el-button>
          <el-button type="warning" :loading="loading === 'upload'" :disabled="loading !== null" @click="handleRunStep('upload')" class="step-btn">
            <Icon icon="mdi:upload" /> Upload
          </el-button>
        </div>
      </el-form>
    </div>

    <!-- Task Status Card -->
    <TaskPreviewBar />

    <!-- Episode Selector Dialog -->
    <EpisodeSelector
      v-model="showEpisodeSelector"
      :episodes="episodes"
      :loading="scanningEpisodes"
      @confirm="handleUploadConfirm"
    />
  </div>
</template>

<style scoped>
.pipeline-page {
  max-width: 1200px;
  margin: 0 auto;
}

.pipeline-card {
  border-radius: 12px;
  padding: 20px 24px;
  border: 1px solid;
}

/* Compact Header */
.header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.header-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  background: linear-gradient(135deg, #409eff, #67c23a);
  color: white;
}

.header h1 {
  font-size: 18px;
  font-weight: 600;
  margin: 0;
  flex: 1;
}

/* Status Bar */
.status-bar {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}

.status-item {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  background: var(--el-fill-color-light);
  border: 1px solid transparent;
}

.status-item:hover {
  border-color: var(--el-border-color);
}

.status-item.ready {
  background: #67c23a15;
  border-color: #67c23a40;
}

.status-item.ready .status-icon {
  color: #67c23a;
}

.status-item.notready {
  background: #f56c6c15;
  border-color: #f56c6c40;
}

.status-item.notready .status-icon {
  color: #f56c6c;
}

.status-item.checking .status-icon {
  color: var(--el-text-color-secondary);
}

.status-icon {
  font-size: 18px;
  display: flex;
}

.status-info {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.status-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.status-msg {
  font-size: 11px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* Compact Form */
.compact-form :deep(.el-form-item) {
  margin-bottom: 14px;
}

.compact-form :deep(.el-form-item__label) {
  font-size: 12px;
  padding-bottom: 4px;
  color: var(--el-text-color-regular);
}

.compact-item {
  margin-bottom: 14px !important;
}

/* Derived Paths */
.derived-paths {
  font-size: 11px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
}

.derived-paths code {
  background: var(--el-fill-color-light);
  padding: 1px 4px;
  border-radius: 3px;
}

.template-hint {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--el-color-primary);
  font-size: 11px;
}

.template-hint .iconify {
  font-size: 12px;
}

/* Actions */
.actions {
  display: flex;
  justify-content: center;
  gap: 16px;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--el-border-color-lighter);
}

.step-btn {
  flex: 1;
  height: 40px;
  font-weight: 600;
}

.step-btn .iconify {
  margin-right: 6px;
}

/* Theme */
.pipeline-page.dark .pipeline-card {
  background-color: #1a1a2e;
  border-color: #2a2a4e;
}

.pipeline-page.dark .header h1 {
  color: #fff;
}

.pipeline-page.light .pipeline-card {
  background-color: #fff;
  border-color: #e4e7ed;
}

.pipeline-page.light .header h1 {
  color: #303133;
}
</style>
