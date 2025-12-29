import api from './index'
import type { Task, Stats, HealthCheck } from './index'

// Get all tasks
export const getTasks = (params?: {
  status?: string
  type?: string
  limit?: number
  offset?: number
}): Promise<Task[]> => {
  return api.get('/tasks', { params }).then((data: any) => {
    // 后端返回 {tasks: [...], total: n} 格式
    return data.tasks || []
  })
}

// Get single task
export const getTask = (taskId: string): Promise<Task> => {
  return api.get(`/tasks/${taskId}`)
}

// Cancel task
export const cancelTask = (taskId: string): Promise<Task> => {
  return api.post(`/tasks/${taskId}/cancel`)
}

// Delete task
export const deleteTask = (taskId: string): Promise<void> => {
  return api.delete(`/tasks/${taskId}`)
}

// Get stats
export const getStats = (): Promise<Stats> => {
  return api.get('/stats')
}

// Health check
export const getHealth = (): Promise<HealthCheck> => {
  return api.get('/health', { baseURL: '' })
}
