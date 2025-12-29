import axios from 'axios'
import type { AxiosInstance, AxiosResponse } from 'axios'

// API instance
const api: AxiosInstance = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// Response interceptor
api.interceptors.response.use(
  (response: AxiosResponse) => response.data,
  (error) => {
    const message = error.response?.data?.detail || error.message || 'Request failed'
    console.error('API Error:', message)
    return Promise.reject(new Error(message))
  }
)

export default api

// Types
export interface TaskProgress {
  percent: number
  current_file?: string
  total_files: number
  completed_files: number
  failed_files: number
  message?: string
  bytes_total: number
  bytes_transferred: number
  speed_bytes_per_sec: number
  eta_seconds: number
}

export interface Task {
  id: string
  type: 'download' | 'convert' | 'upload'
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
  progress: TaskProgress
  config: Record<string, unknown>
  result: Record<string, unknown> | null
  created_at: string
  updated_at: string
  started_at: string | null
  completed_at: string | null
}

export interface Stats {
  tasks: {
    total: number
    pending: number
    running: number
    completed: number
    failed: number
    cancelled: number
  }
  by_type: {
    download: number
    convert: number
    upload?: number
  }
}

export interface HealthCheck {
  status: 'healthy' | 'degraded'
  checks: {
    database: boolean
    mc_tool: boolean
    bos_connection: boolean
  }
}
