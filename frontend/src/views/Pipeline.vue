<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted, onUnmounted } from 'vue'
import { Icon } from '@iconify/vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useThemeStore } from '@/stores/theme'
import { useTaskStore } from '@/stores/tasks'
import { getDefaults, type DefaultConfig, ApiError } from '@/api'
import {
  runStep, derivePaths, hasPathTemplate, resolvePath,
  checkDownloadReady, checkConvertReady, checkMergedReady,
  scanEpisodes, runMerge, getMergeProgress,
  loadQCResult, uploadMerged, updateQCEpisode
} from '@/api/pipeline'
import type { PipelineConfig, CheckResult, Episode, QCResult, MergeConfig, QCResultResponse } from '@/api/pipeline'
import ValidatedInput from '@/components/ValidatedInput.vue'
import TaskPreviewBar from '@/components/TaskPreviewBar.vue'
import QCInspector from '@/components/QCInspector.vue'
import MergeEpisodeSelector from '@/components/MergeEpisodeSelector.vue'

const themeStore = useThemeStore()
const taskStore = useTaskStore()
const STORAGE_KEY = 'citadel_pipeline_config'

// 后端配置（启动时获取）
const backendDefaults = ref<DefaultConfig | null>(null)

// 本地回退默认值（后端不可用时使用）
const fallbackConfig: PipelineConfig = {
  bos_source: '',
  bos_target: '',
  local_dir: './data',
  robot_type: 'airbot_play',
  fps: 25,
  concurrency: 10,
  file_pattern: 'episode_*.h5',
  task_name: 'default_task'
}

// 获取当前默认配置（优先使用后端配置）
const getDefaultConfig = (): PipelineConfig => {
  if (backendDefaults.value) {
    return {
      bos_source: '',  // 用户必须提供
      bos_target: '',  // 用户必须提供
      local_dir: './data',
      robot_type: backendDefaults.value.default_robot_type,
      fps: backendDefaults.value.default_fps,
      concurrency: backendDefaults.value.default_concurrency,
      file_pattern: backendDefaults.value.default_file_pattern,
      task_name: backendDefaults.value.default_task_name
    }
  }
  return { ...fallbackConfig }
}

const loadConfig = (): PipelineConfig => {
  const defaults = getDefaultConfig()
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved) return { ...defaults, ...JSON.parse(saved) }
  } catch (e) { console.error('[Pipeline] Failed to load config:', e) }
  return { ...defaults }
}

const saveConfig = (config: PipelineConfig) => {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(config)) }
  catch (e) { console.error('[Pipeline] Failed to save config:', e) }
}

const config = reactive<PipelineConfig>(loadConfig())
const loading = ref<'download' | 'convert' | 'upload' | 'qc' | 'merge' | null>(null)
const paths = computed(() => derivePaths(config))

// 解析本地目录模板（用于 QC/merge 等需要实际路径的场景）
const resolvedLocalDir = computed(() => resolvePath(config.local_dir))
const currentLerobotDir = computed(() => `${resolvedLocalDir.value}/lerobot`)

// ============ QC + Merge State ============
const showQCInspector = ref(false)
const qcEpisodes = ref<Episode[]>([])
const qcLoading = ref(false)
const qcResult = ref<QCResult | null>(null)
const qcResultTimestamp = ref<string | null>(null)
const mergeTaskId = ref<string | null>(null)

const qcClientId = (() => {
  // 注意：不要用 sessionStorage 持久化 client_id。
  // 浏览器“复制标签页”会复制 sessionStorage，导致两个窗口 client_id 一样，
  // 进而把对方的 ws 消息误判为“自己发的”并忽略，表现为不同用户无法实时同步。
  const globalKey = '__citadel_qc_client_id__'
  const existing = (globalThis as any)[globalKey]
  if (typeof existing === 'string' && existing) return existing

  const created =
    typeof crypto !== 'undefined' && typeof (crypto as any).randomUUID === 'function'
      ? `web-${(crypto as any).randomUUID()}`
      : `web-${Date.now()}-${Math.random().toString(16).slice(2)}`

  ;(globalThis as any)[globalKey] = created
  return created
})()

let qcWs: WebSocket | null = null
let qcWsHeartbeatTimer: ReturnType<typeof setInterval> | null = null
let qcWsReconnectTimer: ReturnType<typeof setTimeout> | null = null
let qcWsOpenTimer: ReturnType<typeof setTimeout> | null = null
let qcWsReconnectAttempts = 0
let qcWsBaseDir: string | null = null

// 当前已同步过 QC 结果的目录（用于避免重复 toast）
const lastSyncedQCLerobotDir = ref<string | null>(null)
let qcResultSyncTimer: ReturnType<typeof setTimeout> | null = null

// Merge episode selection
const showMergeSelector = ref(false)
const mergeEpisodes = ref<Episode[]>([])
const mergeSelectorLoading = ref(false)

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

const runCheck = async (step: 'download' | 'convert' | 'merged', skipCheckingState = false) => {
  if (!skipCheckingState) {
    checking.value = step
  }
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
  if (!skipCheckingState) {
    checking.value = null
  }
}

const runAllChecks = async () => {
  checking.value = 'all'
  await Promise.all([
    runCheck('download', true),
    runCheck('convert', true),
    runCheck('merged', true)
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
  qcEpisodes.value = []
  showQCInspector.value = true
  try {
    const resolvedDir = resolvedLocalDir.value
    console.log('[openQCInspector] resolvedDir:', resolvedDir)

    await syncQCResultForCurrentDir({ showToast: false, force: true })

    const result = await scanEpisodes(resolvedDir)
    console.log('[openQCInspector] episodes count:', result?.length)
    qcEpisodes.value = result
  } catch (e) {
    ElMessage.error(`扫描 episode 失败: ${(e as Error).message}`)
    showQCInspector.value = false
  } finally {
    qcLoading.value = false
  }
}

const updateLocalEpisodeStatus = (episodeName: string, status: 'passed' | 'failed' | 'pending') => {
  if (!qcResult.value) {
    qcResult.value = { passed: [], failed: [] }
  }

  const passed = new Set(qcResult.value.passed)
  const failed = new Set(qcResult.value.failed)

  passed.delete(episodeName)
  failed.delete(episodeName)

  if (status === 'passed') passed.add(episodeName)
  if (status === 'failed') failed.add(episodeName)

  qcResult.value = { passed: Array.from(passed), failed: Array.from(failed) }
}

const getLocalEpisodeStatus = (episodeName: string): 'passed' | 'failed' | 'pending' => {
  if (!qcResult.value) return 'pending'
  if (qcResult.value.passed.includes(episodeName)) return 'passed'
  if (qcResult.value.failed.includes(episodeName)) return 'failed'
  return 'pending'
}

const handleEpisodeUpdate = async (payload: { episodeName: string; status: 'passed' | 'failed' | 'pending' }) => {
  const baseStatus = getLocalEpisodeStatus(payload.episodeName)
  updateLocalEpisodeStatus(payload.episodeName, payload.status)

  try {
    const lerobotDir = currentLerobotDir.value
    const res = await updateQCEpisode(lerobotDir, payload.episodeName, payload.status, {
      client_id: qcClientId,
      base_timestamp: qcResultTimestamp.value ?? undefined,
      base_status: baseStatus,
    })
    qcResultTimestamp.value = res.timestamp ?? qcResultTimestamp.value
  } catch (e) {
    if (e instanceof ApiError && e.status === 409) {
      const current = (e.data as any)?.current
      const episode = (e.data as any)?.episode
      const time = current?.timestamp ? new Date(current.timestamp).toLocaleString() : ''
      const currentStatus = episode?.current_status
      const statusText: Record<string, string> = { passed: '通过', failed: '不通过', pending: '未标记' }
      const currentStatusLabel = currentStatus ? (statusText[currentStatus] ?? String(currentStatus)) : ''
      try {
        await ElMessageBox.confirm(
          `该 episode 已被其他人标记为「${currentStatusLabel || '已更新'}」${time ? ` (${time})` : ''}，是否覆盖为你的标记？`,
          '覆盖确认',
          {
            confirmButtonText: '覆盖',
            cancelButtonText: '取消',
            type: 'warning',
          }
        )
      } catch {
        await syncQCResultForCurrentDir({ showToast: true, force: true })
        return
      }

      try {
        const lerobotDir = currentLerobotDir.value
        const res = await updateQCEpisode(lerobotDir, payload.episodeName, payload.status, {
          client_id: qcClientId,
          base_timestamp: qcResultTimestamp.value ?? undefined,
          base_status: baseStatus,
          force: true,
        })
        qcResultTimestamp.value = res.timestamp ?? qcResultTimestamp.value
        ElMessage.success('已覆盖更新')
        return
      } catch (e2) {
        ElMessage.error(`覆盖更新失败: ${(e2 as Error).message}`)
        return
      }
    }

    ElMessage.warning(`更新质检状态失败: ${(e as Error).message}`)
    await syncQCResultForCurrentDir({ showToast: false, force: true })
  }
}

const handleBulkEpisodeUpdate = async (
  updates: { episodeName: string; status: 'passed' | 'failed' | 'pending'; baseStatus: 'passed' | 'failed' | 'pending' }[]
) => {
  if (!updates || updates.length === 0) return

  // 先更新本地状态，保持 UI 及时反馈；失败/冲突时再强制同步。
  updates.forEach(u => updateLocalEpisodeStatus(u.episodeName, u.status))

  const lerobotDir = currentLerobotDir.value
  let hasConflict = false

  for (const u of updates) {
    try {
      const res = await updateQCEpisode(lerobotDir, u.episodeName, u.status, {
        client_id: qcClientId,
        base_timestamp: qcResultTimestamp.value ?? undefined,
        base_status: u.baseStatus,
      })
      qcResultTimestamp.value = res.timestamp ?? qcResultTimestamp.value
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        hasConflict = true
        // 批量操作冲突时默认跳过该条，避免弹窗轰炸。
        await syncQCResultForCurrentDir({ showToast: false, force: true })
        continue
      }
      ElMessage.warning(`批量更新失败: ${(e as Error).message}`)
      await syncQCResultForCurrentDir({ showToast: false, force: true })
    }
  }

  if (hasConflict) {
    ElMessage.warning('批量更新中发现冲突，已同步最新结果')
  }
}

const handleQCConfirm = async (result: QCResult) => {
  qcResult.value = result
  ElMessage.success(`质检完成: ${result.passed.length} 通过, ${result.failed.length} 不通过`)
  showQCInspector.value = false

  // 多人协作下，避免用全量覆盖保存（容易覆盖他人刚写入的结果）。
  // 以每次 episode 更新为准，这里仅做一次强制同步，确保本地与全局一致。
  await syncQCResultForCurrentDir({ showToast: false, force: true })
}

// ============ Merge ============
const handleMerge = async () => {
  if (!qcResult.value || qcResult.value.passed.length === 0) {
    ElMessage.warning('没有通过质检的 episode，无法执行合并')
    return
  }

  // 打开 merge 选择器，显示通过质检的 episode
  mergeSelectorLoading.value = true
  showMergeSelector.value = true

  try {
    const resolvedDir = resolvePath(config.local_dir)

    // 扫描所有 episode（scanEpisodes 内部会自动拼接 /lerobot）
    console.log('[handleMerge] resolvedDir:', resolvedDir)
    console.log('[handleMerge] qcResult.passed:', qcResult.value.passed)
    const episodes = await scanEpisodes(resolvedDir)
    console.log('[handleMerge] scanned episodes:', episodes.map(ep => ep.name))

    // 只显示通过质检的 episode
    mergeEpisodes.value = episodes.filter(ep => {
      const included = qcResult.value?.passed?.includes(ep.name) ?? false
      console.log(`[handleMerge] episode ${ep.name}: ${included ? 'included' : 'excluded'}`)
      return included
    })
    console.log('[handleMerge] filtered episodes:', mergeEpisodes.value.map(ep => ep.name))

    if (mergeEpisodes.value.length === 0) {
      ElMessage.warning('扫描到的 episode 与质检结果不匹配，请检查数据')
      showMergeSelector.value = false
    }
  } catch (e) {
    ElMessage.error(`扫描 episode 失败: ${(e as Error).message}`)
    showMergeSelector.value = false
  } finally {
    mergeSelectorLoading.value = false
  }
}

const handleMergeConfirm = async (selectedEpisodes: string[]) => {
  if (selectedEpisodes.length === 0) {
    ElMessage.warning('请至少选择一个 episode 进行合并')
    return
  }

  loading.value = 'merge'
  try {
    const resolvedDir = resolvePath(config.local_dir)
    const lerobotDir = `${resolvedDir}/lerobot`

    // 构建 merge 配置：将选中的 episode 合并
    const mergeConfig: MergeConfig = {
      source_dirs: selectedEpisodes.map(ep => `${lerobotDir}/${ep}`),
      output_dir: `${resolvedDir}/merged`,
      fps: config.fps,
      copy_images: false
    }

    console.log('[handleMergeConfirm] mergeConfig:', mergeConfig)
    const task = await runMerge(mergeConfig)
    mergeTaskId.value = task.id
    ElMessage.success(`Merge 任务已启动: ${task.id} (合并 ${selectedEpisodes.length} 个 episode)`)
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

const syncQCResultForCurrentDir = async (opts?: { showToast?: boolean; force?: boolean }) => {
  const showToast = opts?.showToast ?? false
  const force = opts?.force ?? false
  const lerobotDir = currentLerobotDir.value

  if (lastSyncedQCLerobotDir.value && lastSyncedQCLerobotDir.value !== lerobotDir) {
    qcResult.value = null
    qcResultTimestamp.value = null
    lastSyncedQCLerobotDir.value = null
  }

  try {
    if (!force) {
      if (lastSyncedQCLerobotDir.value === lerobotDir && qcResult.value) {
        return
      }
    }

    const result = await loadQCResult(lerobotDir)

    if (result.exists && (result.passed.length > 0 || result.failed.length > 0)) {
      qcResult.value = {
        passed: result.passed,
        failed: result.failed
      }
      qcResultTimestamp.value = result.timestamp ?? null
      lastSyncedQCLerobotDir.value = lerobotDir
      console.log('[syncQCResultForCurrentDir] Loaded QC result:', result)

      if (showToast) {
        if (result.timestamp) {
          const time = new Date(result.timestamp).toLocaleString()
          ElMessage.info(`已同步质检结果 (${time}): ${result.passed.length} 通过, ${result.failed.length} 不通过`)
        } else {
          ElMessage.info(`已同步质检结果: ${result.passed.length} 通过, ${result.failed.length} 不通过`)
        }
      }
    } else {
      qcResult.value = null
      qcResultTimestamp.value = null
      lastSyncedQCLerobotDir.value = null
    }
  } catch (e) {
    console.error('[syncQCResultForCurrentDir] Failed to load QC result:', e)
  }
}

// 加载上次的 QC 结果（兼容旧命名）
const loadPreviousQCResult = async () => {
  await syncQCResultForCurrentDir({ showToast: true })
}

const closeQCWebSocket = () => {
  if (qcWsOpenTimer) {
    clearTimeout(qcWsOpenTimer)
    qcWsOpenTimer = null
  }
  if (qcWsReconnectTimer) {
    clearTimeout(qcWsReconnectTimer)
    qcWsReconnectTimer = null
  }
  if (qcWsHeartbeatTimer) {
    clearInterval(qcWsHeartbeatTimer)
    qcWsHeartbeatTimer = null
  }

  qcWsReconnectAttempts = 0
  qcWsBaseDir = null

  if (qcWs) {
    try {
      qcWs.onclose = null
      qcWs.onerror = null
      qcWs.onmessage = null
      qcWs.onopen = null
      qcWs.close()
    } catch {
      // ignore
    }
    qcWs = null
  }
}

const scheduleQCWebSocketReconnect = (baseDir: string) => {
  if (!baseDir) return
  if (qcWsReconnectTimer) return

  qcWsReconnectAttempts += 1
  const delay = Math.min(1000 * 2 ** (qcWsReconnectAttempts - 1), 15000)

  qcWsReconnectTimer = setTimeout(() => {
    qcWsReconnectTimer = null
    openQCWebSocket(baseDir)
  }, delay)
}

const openQCWebSocket = (baseDir: string) => {
  if (!baseDir) return

  if (qcWsOpenTimer) {
    clearTimeout(qcWsOpenTimer)
    qcWsOpenTimer = null
  }

  // Debounce rapid directory changes to avoid hammering Vite ws proxy.
  qcWsOpenTimer = setTimeout(() => {
    qcWsOpenTimer = null

    if (!baseDir) return

    if (qcWs && qcWsBaseDir === baseDir && qcWs.readyState <= 1) {
      return
    }

    closeQCWebSocket()
    qcWsBaseDir = baseDir

    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const query = new URLSearchParams({ base_dir: baseDir, client_id: qcClientId }).toString()

    // Dev: connect directly to backend to avoid Vite ws proxy instability.
    // Prod: same-origin (behind reverse proxy) is fine.
    const apiPort = import.meta.env.VITE_API_PORT || '8000'
    const apiHostEnv = import.meta.env.VITE_API_HOST || '127.0.0.1'

    const isLocalApiHost = apiHostEnv === '127.0.0.1' || apiHostEnv === 'localhost'

    // Dev: 直连后端（避免 Vite ws proxy 在跨机器/长连接下不稳定）。
    // 若 VITE_API_HOST=localhost/127.0.0.1，则使用当前页面的 hostname（也就是提供前端的那台机器）。
    // Prod: 同源（behind reverse proxy）。
    const wsHost = import.meta.env.DEV
      ? `${isLocalApiHost ? window.location.hostname : apiHostEnv}:${apiPort}`
      : window.location.host

    const url = `${protocol}://${wsHost}/api/upload/qc/ws?${query}`

    try {
      qcWs = new WebSocket(url)
    } catch (e) {
      console.warn('[QC WS] Failed to create WebSocket:', e)
      scheduleQCWebSocketReconnect(baseDir)
      return
    }

    qcWs.onopen = () => {
      qcWsReconnectAttempts = 0

      if (qcWsHeartbeatTimer) {
        clearInterval(qcWsHeartbeatTimer)
      }

      qcWsHeartbeatTimer = setInterval(() => {
        if (!qcWs || qcWs.readyState !== WebSocket.OPEN) return
        try {
          qcWs.send(JSON.stringify({ type: 'ping' }))
        } catch {
          // ignore
        }
      }, 10000)
    }

    qcWs.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data)
        if (!msg || typeof msg !== 'object') return

        if (msg.type === 'qc_result_updated') {
          // qc_result_updated 代表“全量结果发生变化”（可能来自旧客户端）。
          // 这里无法增量更新，只能拉全量。
          const showToast = !msg.source_client_id || msg.source_client_id !== qcClientId
          syncQCResultForCurrentDir({ showToast, force: true })
          return
        }

        if (msg.type === 'qc_episode_updated') {
          // 对单条 episode 的更新：先就地更新本地状态，保证 UI 立刻响应。
          // 如果消息字段缺失，再回退到拉全量。
          const episodeName = msg.episode_name
          const status = msg.status
          if (
            typeof episodeName === 'string' &&
            (status === 'passed' || status === 'failed' || status === 'pending')
          ) {
            updateLocalEpisodeStatus(episodeName, status)
            if (typeof msg.timestamp === 'string') {
              qcResultTimestamp.value = msg.timestamp
            }
          } else {
            syncQCResultForCurrentDir({ showToast: false, force: true })
          }
          return
        }

        if (msg.type === 'qc_ws_connected') {
          return
        }
      } catch (e) {
        console.warn('[QC WS] Failed to parse message:', e)
      }
    }

    qcWs.onclose = () => {
      if (qcWsBaseDir === baseDir) {
        scheduleQCWebSocketReconnect(baseDir)
      }
    }

    qcWs.onerror = () => {
      if (qcWsBaseDir === baseDir) {
        scheduleQCWebSocketReconnect(baseDir)
      }
    }
  }, 300)
}


// Auto-check on mount and start task polling
onMounted(async () => {
  // 1. 先获取后端默认配置
  try {
    backendDefaults.value = await getDefaults()
    console.log('[Pipeline] Loaded backend defaults:', backendDefaults.value)
    // 如果当前配置是空的，用后端默认值更新
    const defaults = getDefaultConfig()
    if (!config.task_name || config.task_name === 'default_task') {
      config.task_name = defaults.task_name
    }
    if (!config.robot_type) config.robot_type = defaults.robot_type
    if (!config.fps) config.fps = defaults.fps
    if (!config.concurrency) config.concurrency = defaults.concurrency
    if (!config.file_pattern) config.file_pattern = defaults.file_pattern
  } catch (e) {
    console.warn('[Pipeline] Failed to load backend defaults, using fallback:', e)
  }

  // 2. Delay to allow backend to be ready
  setTimeout(runAllChecks, 500)
  // 3. Start polling for task updates (for preview bar)
  taskStore.fetchTasks()
  taskStore.fetchStats()
  taskStore.startPolling(3000)
  // 4. Load previous QC result (for current local_dir)
  setTimeout(loadPreviousQCResult, 600)
})

// local_dir 变化时自动同步 qc_result.json（支持跨机器/重复打开同一数据集）
watch(
  () => currentLerobotDir.value,
  (lerobotDir) => {
    if (qcResultSyncTimer) {
      clearTimeout(qcResultSyncTimer)
      qcResultSyncTimer = null
    }
    qcResultSyncTimer = setTimeout(() => {
      syncQCResultForCurrentDir({ showToast: true })
    }, 300)

    openQCWebSocket(lerobotDir)
  },
  { immediate: true }
)

onUnmounted(() => {
  taskStore.stopPolling()
  closeQCWebSocket()
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
          <el-button type="info" :loading="qcLoading" :disabled="loading !== null || qcLoading" @click="openQCInspector" class="step-btn">
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
        @episode-update="handleEpisodeUpdate"
        @bulk-episode-update="handleBulkEpisodeUpdate"
      />


    <!-- Merge Episode Selector -->
    <MergeEpisodeSelector
      v-model="showMergeSelector"
      :episodes="mergeEpisodes"
      :base-dir="`${resolvePath(config.local_dir)}/lerobot`"
      :loading="mergeSelectorLoading"
      @confirm="handleMergeConfirm"
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
