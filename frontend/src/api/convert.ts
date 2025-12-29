import api from './index'
import type { Task } from './index'

export interface ConvertConfig {
  input_dir: string
  output_dir: string
  robot_type?: string
  fps?: number
  task?: string
  parallel_jobs?: number
  file_pattern?: string
}

// Start convert task
export const startConvert = (config: ConvertConfig): Promise<Task> => {
  return api.post('/convert/start', config)
}

// Get convert progress
export const getConvertProgress = (taskId: string): Promise<Task> => {
  return api.get(`/convert/${taskId}/progress`)
}

// Scan files in directory
export const scanFiles = (inputDir: string, filePattern?: string): Promise<string[]> => {
  return api.get('/convert/scan-files', {
    params: {
      input_dir: inputDir,
      file_pattern: filePattern || 'episode_*.h5'
    }
  })
}
