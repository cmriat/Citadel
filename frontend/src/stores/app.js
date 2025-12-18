import { defineStore } from 'pinia'
import { ref, reactive } from 'vue'

export const useAppStore = defineStore('app', () => {
  // 日志
  const logs = ref([])
  const maxLogs = 100

  // WebSocket 连接
  const ws = ref(null)
  const wsConnected = ref(false)

  // 添加日志
  const addLog = (message) => {
    logs.value.push(message)
    if (logs.value.length > maxLogs) {
      logs.value.shift()
    }
  }

  // 清除日志
  const clearLogs = () => {
    logs.value = []
  }

  // 连接 WebSocket
  const connectWebSocket = () => {
    if (ws.value && ws.value.readyState === WebSocket.OPEN) {
      return
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/api/ws/logs`

    ws.value = new WebSocket(wsUrl)

    ws.value.onopen = () => {
      wsConnected.value = true
      console.log('WebSocket connected')
    }

    ws.value.onmessage = (event) => {
      const message = event.data
      if (message !== 'pong' && message !== 'heartbeat') {
        addLog(message)
      }
    }

    ws.value.onclose = () => {
      wsConnected.value = false
      console.log('WebSocket disconnected')
      // 自动重连
      setTimeout(connectWebSocket, 3000)
    }

    ws.value.onerror = (error) => {
      console.error('WebSocket error:', error)
    }
  }

  // 断开 WebSocket
  const disconnectWebSocket = () => {
    if (ws.value) {
      ws.value.close()
      ws.value = null
    }
  }

  return {
    logs,
    wsConnected,
    addLog,
    clearLogs,
    connectWebSocket,
    disconnectWebSocket
  }
})
