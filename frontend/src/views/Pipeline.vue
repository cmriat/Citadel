<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted, onUnmounted } from 'vue'
import { Icon } from '@iconify/vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useThemeStore } from '@/stores/theme'
import { useTaskStore } from '@/stores/tasks'
import {
  runStep, derivePaths, hasPathTemplate, resolvePath,
  checkDownloadReady, checkConvertReady, checkMergedReady,
  scanEpisodes, runMerge, getMergeProgress,
  saveQCResult, loadQCResult, uploadMerged
} from '@/api/pipeline'
import type { PipelineConfig, CheckResult, Episode, QCResult, MergeConfig, QCResultResponse } from '@/api/pipeline'
import ValidatedInput from '@/components/ValidatedInput.vue'
import TaskPreviewBar from '@/components/TaskPreviewBar.vue'
import QCInspector from '@/components/QCInspector.vue'

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
const loading = ref<'download' | 'convert' | 'upload' | 'qc' | 'merge' | null>(null)
const paths = computed(() => derivePaths(config))

// ============ QC + Merge State ============
const showQCInspector = ref(false)
const qcEpisodes = ref<Episode[]>([])
const qcLoading = ref(false)
const qcResult = ref<QCResult | null>(null)
const mergeTaskId = ref<string | null>(null)

// ============ Status Check ============
interface StepStatus {
  ready: boolean | null  // null = checking
  count: number
  message: string
}

const status = reactive({
  download: { ready: null, count: 0, message: 'Click to check' } as StepStatus,
  convert: { ready: null, count: 0, message: 'Click to check' } as StepStatus,
  merged: { ready: null, count: 0, message: 'Click to check' } as StepStatus
})

const statusTooltips: Record<string, string> = {
  download: '检测 BOS 源路径是否有 HDF5 文件',
  convert: '检测本地 raw 目录是否有已下载的文件',
  merged: '检测本地 merged 目录是否有合并后的数据'
}

const checking = ref<'download' | 'convert' | 'merged' | 'all' | null>(null)

const runCheck = async (step: 'download' | 'convert' | 'merged') => {
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
    case 'merged':
      result = await checkMergedReady(resolvedDir)
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
    runCheck('merged')
  ])
  checking.value = null
}

// ============ Actions ============

// 确认信息配置
const confirmMessages = {
  download: {
    title: '确认下载',
    message: (c: PipelineConfig) => `即将从 BOS 下载数据：\n\n源路径：${c.bos_source}\n本地目录：${resolvePath(c.local_dir)}/raw\n并发数：${c.concurrency}`,
  },
  convert: {
    title: '确认转换',
    message: (c: PipelineConfig) => `即将转换 HDF5 数据为 LeRobot 格式：\n\n输入目录：${resolvePath(c.local_dir)}/raw\n输出目录：${resolvePath(c.local_dir)}/lerobot\n机器人类型：${c.robot_type}\nFPS：${c.fps}`,
  },
  merge: {
    title: '确认合并',
    message: (c: PipelineConfig, passedCount: number) => `即将合并通过质检的 episode：\n\n通过数量：${passedCount} 个\n输出目录：${resolvePath(c.local_dir)}/merged\nFPS：${c.fps}`,
  },
  upload: {
    title: '确认上传',
    message: (c: PipelineConfig) => `即将上传合并后的数据集到 BOS：\n\n本地目录：${resolvePath(c.local_dir)}/merged\n目标路径：${c.bos_target}\n并发数：${c.concurrency}`,
  }
}

const handleRunStep = async (step: 'download' | 'convert') => {
  // 弹出确认对话框
  try {
    await ElMessageBox.confirm(
      confirmMessages[step].message(config),
      confirmMessages[step].title,
      {
        confirmButtonText: '开始',
        cancelButtonText: '取消',
        type: 'info',
        customStyle: { whiteSpace: 'pre-line' }
      }
    )
  } catch {
    return // 用户取消
  }

  loading.value = step
  try {
    const task = await runStep(step, config)
    ElMessage.success(`${step} task: ${task.id}`)
    saveConfig(config)
    // Refresh status after task created
    setTimeout(() => runCheck(step === 'download' ? 'convert' : 'merged'), 1000)
  } catch (e) { ElMessage.error((e as Error).message) }
  finally { loading.value = null }
}

// Upload merged dataset
const handleUpload = async () => {
  // 弹出确认对话框
  try {
    await ElMessageBox.confirm(
      confirmMessages.upload.message(config),
      confirmMessages.upload.title,
      {
        confirmButtonText: '开始上传',
        cancelButtonText: '取消',
        type: 'info',
        customStyle: { whiteSpace: 'pre-line' }
      }
    )
  } catch {
    return // 用户取消
  }

  loading.value = 'upload'
  try {
    const task = await uploadMerged(config)
    ElMessage.success(`Upload started: merged dataset (task: ${task.id})`)
    saveConfig(config)
    setTimeout(() => runCheck('merged'), 1000)
  } catch (e) {
    ElMessage.error((e as Error).message)
  } finally {
    loading.value = null
  }
}

// ============ QC Inspector ============
const openQCInspector = async () => {
  qcLoading.value = true
  showQCInspector.value = true
  try {
    const resolvedDir = resolvePath(config.local_dir)
    console.log('[openQCInspector] resolvedDir:', resolvedDir)
    const result = await scanEpisodes(resolvedDir)
    console.log('[openQCInspector] episodes count:', result?.length)
    qcEpisodes.value = result
  } catch (e) {
    ElMessage.error(`扫描 episode 失败: ${(e as Error).message}`)
  } finally {
    qcLoading.value = false
  }
}

const handleQCConfirm = async (result: QCResult) => {
  qcResult.value = result
  ElMessage.success(`质检完成: ${result.passed.length} 通过, ${result.failed.length} 不通过`)
  showQCInspector.value = false

  // 保存 QC 结果到文件
  try {
    const resolvedDir = resolvePath(config.local_dir)
    const lerobotDir = `${resolvedDir}/lerobot`
    await saveQCResult(lerobotDir, result)
    console.log('[handleQCConfirm] QC result saved to file')
  } catch (e) {
    console.error('[handleQCConfirm] Failed to save QC result:', e)
  }
}

// ============ Merge ============
const handleMerge = async () => {
  if (!qcResult.value || qcResult.value.passed.length === 0) {
    ElMessage.warning('没有通过质检的 episode，无法执行合并')
    return
  }

  // 弹出确认对话框
  try {
    await ElMessageBox.confirm(
      confirmMessages.merge.message(config, qcResult.value.passed.length),
      confirmMessages.merge.title,
      {
        confirmButtonText: '开始合并',
        cancelButtonText: '取消',
        type: 'info',
        customStyle: { whiteSpace: 'pre-line' }
      }
    )
  } catch {
    return // 用户取消
  }

  loading.value = 'merge'
  try {
    const resolvedDir = resolvePath(config.local_dir)
    const lerobotDir = `${resolvedDir}/lerobot`

    // 构建 merge 配置：将通过的 episode 合并
    // output_dir 与 raw/lerobot 同级
    const mergeConfig: MergeConfig = {
      source_dirs: qcResult.value.passed.map(ep => `${lerobotDir}/${ep}`),
      output_dir: `${resolvedDir}/merged`,
      fps: config.fps,
      copy_images: false
    }

    console.log('[handleMerge] mergeConfig:', mergeConfig)
    const task = await runMerge(mergeConfig)
    mergeTaskId.value = task.id
    ElMessage.success(`Merge 任务已启动: ${task.id}`)
    saveConfig(config)

    // 更新任务列表
    taskStore.fetchTasks()
  } catch (e) {
    ElMessage.error(`Merge 失败: ${(e as Error).message}`)
  } finally {
    loading.value = null
  }
}

// QC 状态计算
const qcStats = computed(() => {
  if (!qcResult.value) return null
  return {
    passed: qcResult.value.passed.length,
    failed: qcResult.value.failed.length
  }
})

// 加载上次的 QC 结果
const loadPreviousQCResult = async () => {
  try {
    const resolvedDir = resolvePath(config.local_dir)
    const lerobotDir = `${resolvedDir}/lerobot`
    const result = await loadQCResult(lerobotDir)

    if (result.exists && (result.passed.length > 0 || result.failed.length > 0)) {
      qcResult.value = {
        passed: result.passed,
        failed: result.failed
      }
      console.log('[loadPreviousQCResult] Loaded QC result:', result)
      if (result.timestamp) {
        const time = new Date(result.timestamp).toLocaleString()
        ElMessage.info(`已加载上次质检结果 (${time}): ${result.passed.length} 通过, ${result.failed.length} 不通过`)
      }
    }
  } catch (e) {
    console.error('[loadPreviousQCResult] Failed to load QC result:', e)
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
  // Load previous QC result
  setTimeout(loadPreviousQCResult, 600)
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
          v-for="(step, key) in { download: 'BOS下载前检查', convert: '数据转换前检查', merged: '数据上传前检查' }"
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
            @click="runCheck(key as 'download' | 'convert' | 'merged')"
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
                <div class="path-list">
                  <div class="path-item">
                    <span class="path-label">H5原始文件:</span>
                    <code>{{ paths.raw_dir }}</code>
                  </div>
                  <div class="path-item">
                    <span class="path-label">LeRobot转换后:</span>
                    <code>{{ paths.lerobot_dir }}</code>
                  </div>
                  <div class="path-item">
                    <span class="path-label">合并后数据集:</span>
                    <code>{{ paths.merged_dir }}</code>
                  </div>
                </div>
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
          <el-button type="info" :loading="loading === 'qc'" :disabled="loading !== null" @click="openQCInspector" class="step-btn">
            <Icon icon="mdi:check-decagram" /> QC
            <el-badge v-if="qcStats" :value="qcStats.passed" type="success" class="qc-badge" />
          </el-button>
          <el-button
            type="primary"
            :loading="loading === 'merge'"
            :disabled="loading !== null || !qcStats || qcStats.passed === 0"
            @click="handleMerge"
            class="step-btn merge-btn"
          >
            <Icon icon="mdi:merge" /> Merge
            <span v-if="qcStats" class="merge-count">({{ qcStats.passed }})</span>
          </el-button>
          <el-button
            type="warning"
            :loading="loading === 'upload'"
            :disabled="loading !== null || !status.merged.ready"
            @click="handleUpload"
            class="step-btn"
          >
            <Icon icon="mdi:upload" /> Upload
          </el-button>
        </div>
      </el-form>
    </div>

    <!-- Task Status Card -->
    <TaskPreviewBar />

    <!-- QC Inspector Dialog -->
    <QCInspector
      v-model="showQCInspector"
      :episodes="qcEpisodes"
      :base-dir="`${resolvePath(config.local_dir)}/lerobot`"
      :loading="qcLoading"
      :initial-result="qcResult || undefined"
      @confirm="handleQCConfirm"
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
  margin-top: 6px;
}

.derived-paths code {
  background: var(--el-fill-color-light);
  padding: 1px 4px;
  border-radius: 3px;
  font-size: 10px;
}

.path-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-top: 4px;
}

.path-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.path-label {
  color: var(--el-text-color-regular);
  font-weight: 500;
  white-space: nowrap;
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

/* QC Badge */
.qc-badge {
  margin-left: 6px;
}

/* Merge button */
.merge-btn {
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  border: none;
}

.merge-btn:hover {
  background: linear-gradient(135deg, #4f46e5, #7c3aed);
}

.merge-btn:disabled {
  background: var(--el-button-disabled-bg-color);
}

.merge-count {
  margin-left: 4px;
  font-size: 12px;
  opacity: 0.9;
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
