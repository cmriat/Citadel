import api from './index'
import type { Task } from './index'

export interface DownloadConfig {
  bos_path: string
  local_path: string
  concurrency?: number
}

export interface ConnectionCheck {
  connected: boolean
  mc_available: boolean
  mc_version?: string
  error?: string
}

// Start download task
export const startDownload = (config: DownloadConfig): Promise<Task> => {
  return api.post('/download/start', config)
}

// Get download progress
export const getDownloadProgress = (taskId: string): Promise<Task> => {
  return api.get(`/download/${taskId}/progress`)
}

// Check BOS connection
export const checkConnection = (): Promise<ConnectionCheck> => {
  return api.get('/download/check-connection')
}
