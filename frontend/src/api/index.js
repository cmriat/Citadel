import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 配置相关
export const getConfig = () => api.get('/config')
export const updateConfig = (config) => api.put('/config', config)
export const testBosConnection = (config) => api.post('/config/test-bos', config)

// Scanner 相关
export const startScanner = (data) => api.post('/scanner/start', data)
export const stopScanner = () => api.post('/scanner/stop')
export const getScannerStatus = () => api.get('/scanner/status')

// Worker 相关
export const startWorkers = (data) => api.post('/worker/start', data)
export const stopWorkers = () => api.post('/worker/stop')
export const getWorkerStatus = () => api.get('/worker/status')

// 监控相关
export const getQueueStats = () => api.get('/stats')
export const getEpisodes = (limit = 20, offset = 0) =>
  api.get('/episodes', { params: { limit, offset } })
export const getSystemStats = () => api.get('/system')

export default api
