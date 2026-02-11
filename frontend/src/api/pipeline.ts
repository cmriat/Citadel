import api from './index'
import type { Task } from './index'

// ============ API Response Types ============

/** BOS 扫描响应 */
interface ScanBosResponse {
  ready: boolean
  file_count: number
  error?: string
}

/** 目录扫描响应 */
interface ScanDirsResponse {
  name: string
}

// ============ Pipeline Configuration ============

// Unified pipeline configuration
export interface PipelineConfig {
  bos_source: string      // BOS source path (download from)
  bos_target: string      // BOS target path (upload to)
  local_dir: string       // Local root directory
  robot_type: string      // Robot type for conversion
  fps: number             // FPS for conversion
  concurrency: number     // Parallel threads
  file_pattern?: string   // File pattern for scanning (optional)
  task_name?: string      // Task name for conversion (optional)
}

// Pipeline execution result
export interface PipelineResult {
  pipeline_id: string
  tasks: {
    download?: Task
    convert?: Task
    upload?: Task
  }
}

// ============ Path Template Resolution ============

/**
 * 解析路径模板中的日期占位符
 * 支持的占位符：
 * - {date} -> YYYY-MM-DD (如 2025-12-29)
 * - {datetime} -> YYYY-MM-DD_HH-mm (如 2025-12-29_17-30)
 */
export const resolvePath = (template: string): string => {
  const now = new Date()

  const date = now.toISOString().split('T')[0]

  const hours = now.getHours().toString().padStart(2, '0')
  const minutes = now.getMinutes().toString().padStart(2, '0')
  const datetime = `${date}_${hours}-${minutes}`

  if (!template) return ''

  let result = template
  result = result.split('{date}').join(date)
  result = result.split('{datetime}').join(datetime)
  return result
}

/**
 * 检查路径是否包含模板占位符
 */
export const hasPathTemplate = (path: string): boolean => {
  return /{date}|{datetime}/.test(path)
}

// Derived paths helper (resolves templates at call time)
export const derivePaths = (config: PipelineConfig) => {
  const resolvedDir = resolvePath(config.local_dir)
  return {
    raw_dir: `${resolvedDir}/raw`,
    lerobot_dir: `${resolvedDir}/lerobot`,
    merged_dir: `${resolvedDir}/merged`
  }
}

// Run full pipeline (download → convert → upload)
export const runFullPipeline = (config: PipelineConfig): Promise<PipelineResult> => {
  return api.post('/pipeline/run', config)
}

// Run single step
export const runStep = (step: 'download' | 'convert' | 'upload', config: PipelineConfig): Promise<Task> => {
  const paths = derivePaths(config)

  switch (step) {
    case 'download':
      return api.post('/download/start', {
        bos_path: config.bos_source,
        local_path: paths.raw_dir,
        concurrency: config.concurrency
      })
    case 'convert':
      return api.post('/convert/start', {
        input_dir: paths.raw_dir,
        output_dir: paths.lerobot_dir,
        robot_type: config.robot_type,
        fps: config.fps,
        parallel_jobs: config.concurrency,
        file_pattern: config.file_pattern || 'episode_*.h5',
        task: config.task_name || 'default_task'
      })
    case 'upload':
      return api.post('/upload/start', {
        local_dir: paths.merged_dir,
        bos_path: config.bos_target,
        concurrency: config.concurrency,
        include_videos: true
      })
  }
}

// Get pipeline status
export const getPipelineStatus = (pipelineId: string): Promise<PipelineResult> => {
  return api.get(`/pipeline/${pipelineId}/status`)
}

// ============ Pre-check APIs ============

export interface CheckResult {
  ready: boolean
  count: number
  message: string
}

// Check if BOS source has HDF5 files (for download step)
export const checkDownloadReady = async (bosPath: string): Promise<CheckResult> => {
  try {
    const result = await api.get<ScanBosResponse>('/download/scan-bos', { params: { bos_path: bosPath } })
    return {
      ready: result.ready,
      count: result.file_count,
      message: result.ready ? `${result.file_count} files` : (result.error || 'No files')
    }
  } catch (e) {
    return { ready: false, count: 0, message: (e as Error).message }
  }
}

// Check if local raw directory has HDF5 files (for convert step)
export const checkConvertReady = async (localDir: string): Promise<CheckResult> => {
  try {
    const rawDir = `${localDir}/raw`
    const files = await api.get<string[]>('/convert/scan-files', {
      params: { input_dir: rawDir, file_pattern: 'episode_*.h5' }
    })
    const fileList = Array.isArray(files) ? files : []
    return {
      ready: fileList.length > 0,
      count: fileList.length,
      message: fileList.length > 0 ? `${fileList.length} files` : 'No files'
    }
  } catch (e) {
    return { ready: false, count: 0, message: (e as Error).message }
  }
}

// Check if local lerobot directory has converted data (for upload step)
export const checkUploadReady = async (localDir: string): Promise<CheckResult> => {
  try {
    // 检查 merged 目录是否存在
    const mergedDir = `${localDir}/merged`
    const dirs = await api.get<ScanDirsResponse[]>('/upload/scan-dirs', {
      params: { base_dir: mergedDir }
    })
    const dirList = Array.isArray(dirs) ? dirs : []
    // merged 目录本身就是一个数据集，检查是否有 meta 目录
    return {
      ready: dirList.length > 0,
      count: dirList.length,
      message: dirList.length > 0 ? 'Upload ready' : 'No merged data'
    }
  } catch (e) {
    return { ready: false, count: 0, message: (e as Error).message }
  }
}

// Check if merged directory exists
export const checkMergedReady = async (localDir: string): Promise<CheckResult> => {
  try {
    const mergedDir = `${localDir}/merged`
    const result = await api.get<string[]>('/convert/scan-files', {
      params: { input_dir: `${mergedDir}/meta`, file_pattern: '*.json' }
    })
    const files = Array.isArray(result) ? result : []
    return {
      ready: files.length > 0,
      count: files.length,
      message: files.length > 0 ? 'merged ready' : 'No merged data'
    }
  } catch (e) {
    return { ready: false, count: 0, message: 'No merged data' }
  }
}

// Upload merged dataset directly
export const uploadMerged = (config: PipelineConfig): Promise<Task> => {
  const resolvedDir = resolvePath(config.local_dir)
  const mergedDir = `${resolvedDir}/merged`
  return api.post('/upload/start', {
    local_dir: mergedDir,
    bos_path: config.bos_target,
    concurrency: config.concurrency,
    include_videos: true
  })
}

// ============ Episode Scan API ============

export interface Episode {
  name: string
  path: string
  frame_count: number
  size: number
  thumbnails: string[]  // 4 帧 base64 缩略图
}

export interface ScanEpisodesResult {
  base_dir: string
  episodes: Episode[]
}

const _trimTrailingSlashes = (s: string): string => s.replace(/\/+$/, '')

// Scan episodes with thumbnails for QC / merge selection.
// Compatibility: prefer <localDir>/lerobot, fallback to <localDir>.
export const scanEpisodes = async (localDir: string): Promise<ScanEpisodesResult> => {
  try {
    const local = _trimTrailingSlashes(localDir)
    const lerobotDir = local.endsWith('/lerobot') ? local : `${local}/lerobot`

    const candidates = local.endsWith('/lerobot')
      ? [local, local.slice(0, -'/lerobot'.length)]
      : [lerobotDir, local]

    console.log('[scanEpisodes] localDir:', local)
    console.log('[scanEpisodes] candidates:', candidates)

    for (const baseDir of candidates) {
      // 使用更长的超时时间（120秒），因为生成缩略图可能较慢
      const episodes: Episode[] = await api.get('/upload/scan-episodes', {
        params: { base_dir: baseDir },
        timeout: 120000  // 2 分钟超时
      })
      const list = Array.isArray(episodes) ? episodes : []
      console.log('[scanEpisodes] baseDir:', baseDir, 'episodes:', list.length)
      if (list.length > 0) {
        return { base_dir: baseDir, episodes: list }
      }
    }

    // 两次都为空时，默认回到首选候选目录。
    return { base_dir: candidates[0] || local, episodes: [] }
  } catch (e) {
    console.error('[Pipeline] Failed to scan episodes:', e)
    const local = _trimTrailingSlashes(localDir)
    const lerobotDir = local.endsWith('/lerobot') ? local : `${local}/lerobot`
    return { base_dir: lerobotDir, episodes: [] }
  }
}

// Run upload with exclude list
export const runUploadWithExclude = (
  config: PipelineConfig,
  excludeEpisodes: string[]
): Promise<Task> => {
  const paths = derivePaths(config)
  return api.post('/upload/start', {
    local_dir: paths.lerobot_dir,
    bos_path: config.bos_target,
    concurrency: config.concurrency,
    include_videos: true,
    exclude_episodes: excludeEpisodes.length > 0 ? excludeEpisodes : undefined
  })
}

// ============ QC Quality Check ============

export interface QCResult {
  passed: string[]    // 通过的 episode 名称列表
  failed: string[]    // 不通过的 episode 名称列表
}

export interface QCResultResponse {
  passed: string[]
  failed: string[]
  timestamp?: string
  exists: boolean
}

export type QCEpisodeStatus = 'passed' | 'failed' | 'pending'

export interface SaveQCResultOptions {
  client_id?: string
  base_timestamp?: string
  force?: boolean
}

export interface SaveQCResultResponse {
  success: boolean
  file_path: string
  dataset_key?: string
  timestamp?: string
  passed_count?: number
  failed_count?: number
}

export const saveQCResult = async (
  baseDir: string,
  result: QCResult,
  opts?: SaveQCResultOptions
): Promise<SaveQCResultResponse> => {
  return api.post('/upload/save-qc-result', {
    base_dir: baseDir,
    passed: result.passed,
    failed: result.failed,
    client_id: opts?.client_id,
    base_timestamp: opts?.base_timestamp,
    force: opts?.force ?? false,
  })
}

export interface UpdateQCEpisodeResponse {
  success: boolean
  dataset_key?: string
  timestamp?: string
  passed_count?: number
  failed_count?: number
}

export const updateQCEpisode = async (
  baseDir: string,
  episodeName: string,
  status: QCEpisodeStatus,
  opts?: { client_id?: string; base_timestamp?: string; base_status?: QCEpisodeStatus; force?: boolean }
): Promise<UpdateQCEpisodeResponse> => {
  return api.post('/upload/update-qc-episode', {
    base_dir: baseDir,
    episode_name: episodeName,
    status,
    client_id: opts?.client_id,
    base_timestamp: opts?.base_timestamp,
    base_status: opts?.base_status,
    force: opts?.force ?? false,
  })
}

export const loadQCResult = async (baseDir: string): Promise<QCResultResponse> => {
  return api.get('/upload/load-qc-result', { params: { base_dir: baseDir } })
}

export type QCSyncMode = 'none' | 'validity' | 'manual'

export interface SyncQCToDbResponse {
  success: boolean
  dry_run: boolean
  mode: QCSyncMode
  statement_count: number
  episode_count?: number
  episode_update_count?: number
  updated_count?: number
  statements?: { query: string; params?: any; description?: string }[]
  exists_check?: {
    checked: boolean
    checked_count: number
    missing_count: number
    missing_examples?: { episode_name: string; generated_from?: string; data_format?: string; id: string }[]
    message?: string
    column?: string
    non_null_count?: number
    non_null_episode_count?: number
    non_null_examples?: {
      episode_name?: string
      generated_from?: string
      data_format?: string
      id: string
      value?: any
    }[]
  }
}

export const syncQCToDb = async (
  baseDir: string,
  result: QCResult,
  mode: QCSyncMode,
  opts?: {
    dry_run?: boolean
    check_exists?: boolean
    device_id?: string
    collect_date?: string
    task_name?: string
  }
): Promise<SyncQCToDbResponse> => {
  return api.post('/upload/sync-qc-to-db', {
    base_dir: baseDir,
    passed: result.passed,
    failed: result.failed,
    mode,
    dry_run: opts?.dry_run ?? true,
    check_exists: opts?.check_exists ?? false,
    device_id: opts?.device_id,
    collect_date: opts?.collect_date,
    task_name: opts?.task_name,
  })
}

// ============ Merge API ============

export interface MergeConfig {
  source_dirs: string[]
  output_dir: string
  state_max_dim?: number
  action_max_dim?: number
  fps?: number
  copy_images?: boolean
}

// Run merge task
export const runMerge = (config: MergeConfig): Promise<Task> => {
  return api.post('/merge/start', {
    source_dirs: config.source_dirs,
    output_dir: config.output_dir,
    state_max_dim: config.state_max_dim ?? 14,
    action_max_dim: config.action_max_dim ?? 14,
    fps: config.fps ?? 25,
    copy_images: config.copy_images ?? false
  })
}

// Get merge task progress
export const getMergeProgress = (taskId: string): Promise<Task> => {
  return api.get(`/merge/${taskId}/progress`)
}

// Get video stream URL for QC playback
export const getVideoStreamUrl = (baseDir: string, episodeName: string, camera = 'cam_env'): string => {
  const encodedBaseDir = encodeURIComponent(baseDir)
  const encodedEpisode = encodeURIComponent(episodeName)
  return `/api/upload/video-stream?base_dir=${encodedBaseDir}&episode_name=${encodedEpisode}&camera=${camera}`
}
