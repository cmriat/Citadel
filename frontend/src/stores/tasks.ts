import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Task, Stats } from '@/api/index'
import * as tasksApi from '@/api/tasks'

export const useTaskStore = defineStore('tasks', () => {
  // State
  const tasks = ref<Task[]>([])
  const stats = ref<Stats | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const pollingInterval = ref<ReturnType<typeof setInterval> | null>(null)
  const isPolling = ref(false)

  // Getters
  const runningTasks = computed(() =>
    tasks.value.filter(t => t.status === 'running')
  )

  const pendingTasks = computed(() =>
    tasks.value.filter(t => t.status === 'pending')
  )

  const completedTasks = computed(() =>
    tasks.value.filter(t => t.status === 'completed')
  )

  const failedTasks = computed(() =>
    tasks.value.filter(t => t.status === 'failed')
  )

  // Actions
  const fetchTasks = async (params?: { status?: string; type?: string }) => {
    // 检查是否应该继续获取数据
    if (!isPolling.value && loading.value) {
      console.log('[TasksStore] Skipping fetch - polling stopped')
      return
    }

    try {
      loading.value = true
      error.value = null
      console.log('[TasksStore] Fetching tasks...')
      const newTasks = await tasksApi.getTasks(params)

      // 确保组件仍存在时再更新状态
      if (isPolling.value || !loading.value) {
        tasks.value = newTasks
        console.log('[TasksStore] Tasks updated:', newTasks.length)
      }
    } catch (e) {
      error.value = (e as Error).message
      console.error('[TasksStore] Fetch tasks error:', e)
      // 不抛出错误，避免中断轮询
    } finally {
      loading.value = false
    }
  }

  const fetchStats = async () => {
    try {
      stats.value = await tasksApi.getStats()
    } catch (e) {
      console.error('Failed to fetch stats:', e)
    }
  }

  const cancelTask = async (taskId: string) => {
    try {
      await tasksApi.cancelTask(taskId)
      await fetchTasks()
    } catch (e) {
      error.value = (e as Error).message
      throw e
    }
  }

  const deleteTask = async (taskId: string) => {
    try {
      await tasksApi.deleteTask(taskId)
      await fetchTasks()
    } catch (e) {
      error.value = (e as Error).message
      throw e
    }
  }

  const startPolling = (interval = 3000) => {
    stopPolling()
    console.log('[TasksStore] Starting polling with interval:', interval)
    isPolling.value = true

    pollingInterval.value = setInterval(async () => {
      try {
        if (!isPolling.value) {
          console.log('[TasksStore] Polling stopped, skipping fetch')
          return
        }
        console.log('[TasksStore] Polling tick - fetching tasks and stats')
        await Promise.all([
          fetchTasks(),
          fetchStats()
        ])
      } catch (e) {
        console.error('[TasksStore] Polling error:', e)
        // 轮询出错时继续，但不抛出异常
      }
    }, interval)
  }

  const stopPolling = () => {
    console.log('[TasksStore] Stopping polling')
    isPolling.value = false

    if (pollingInterval.value) {
      clearInterval(pollingInterval.value)
      pollingInterval.value = null
    }
  }

  return {
    // State
    tasks,
    stats,
    loading,
    error,
    isPolling,
    // Getters
    runningTasks,
    pendingTasks,
    completedTasks,
    failedTasks,
    // Actions
    fetchTasks,
    fetchStats,
    cancelTask,
    deleteTask,
    startPolling,
    stopPolling
  }
})
