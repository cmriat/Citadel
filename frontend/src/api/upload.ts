import api from './index'
import type { Task } from './index'

export interface UploadConfig {
  local_dir: string
  bos_path: string
  concurrency?: number
  include_videos?: boolean
  delete_after?: boolean
}

export interface UploadableDir {
  path: string
  name: string
  size: number
  file_count: number
}

// Start upload task
export const startUpload = (config: UploadConfig): Promise<Task> => {
  return api.post('/upload/start', config)
}

// Get upload progress
export const getUploadProgress = (taskId: string): Promise<Task> => {
  return api.get(`/upload/${taskId}/progress`)
}

// Scan uploadable directories
export const scanDirs = (baseDir: string): Promise<UploadableDir[]> => {
  return api.get('/upload/scan-dirs', {
    params: { base_dir: baseDir }
  })
}
