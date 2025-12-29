import api from './index'
import type { Task } from './index'

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

  // YYYY-MM-DD
  const date = now.toISOString().split('T')[0]

  // YYYY-MM-DD_HH-mm
  const hours = now.getHours().toString().padStart(2, '0')
  const minutes = now.getMinutes().toString().padStart(2, '0')
  const datetime = `${date}_${hours}-${minutes}`

  return template
    .replace(/{date}/g, date)
    .replace(/{datetime}/g, datetime)
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
    lerobot_dir: `${resolvedDir}/lerobot`
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
        local_dir: paths.lerobot_dir,
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
    const result = await api.get('/download/scan-bos', { params: { bos_path: bosPath } })
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
    const files: string[] = await api.get('/convert/scan-files', {
      params: { input_dir: rawDir, file_pattern: 'episode_*.h5' }
    })
    return {
      ready: files.length > 0,
      count: files.length,
      message: files.length > 0 ? `${files.length} files` : 'No files'
    }
  } catch (e) {
    return { ready: false, count: 0, message: (e as Error).message }
  }
}

// Check if local lerobot directory has converted data (for upload step)
export const checkUploadReady = async (localDir: string): Promise<CheckResult> => {
  try {
    const lerobotDir = `${localDir}/lerobot`
    const dirs: Array<{ name: string }> = await api.get('/upload/scan-dirs', {
      params: { base_dir: lerobotDir }
    })
    return {
      ready: dirs.length > 0,
      count: dirs.length,
      message: dirs.length > 0 ? `${dirs.length} dirs` : 'No data'
    }
  } catch (e) {
    return { ready: false, count: 0, message: (e as Error).message }
  }
}

// ============ Episode Scan API ============

export interface Episode {
  name: string
  path: string
  frame_count: number
  size: number
  thumbnails: string[]  // 4 帧 base64 缩略图
}

// Scan episodes with thumbnails for upload selection
export const scanEpisodes = async (localDir: string): Promise<Episode[]> => {
  try {
    const lerobotDir = `${localDir}/lerobot`
    console.log('[scanEpisodes] localDir:', localDir)
    console.log('[scanEpisodes] lerobotDir:', lerobotDir)
    // 使用更长的超时时间（120秒），因为生成缩略图可能较慢
    const episodes: Episode[] = await api.get('/upload/scan-episodes', {
      params: { base_dir: lerobotDir },
      timeout: 120000  // 2 分钟超时
    })
    console.log('[scanEpisodes] episodes count:', episodes?.length, 'type:', typeof episodes)
    return episodes
  } catch (e) {
    console.error('[Pipeline] Failed to scan episodes:', e)
    return []
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
