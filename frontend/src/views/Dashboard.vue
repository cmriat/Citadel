<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useTaskStore } from '@/stores/tasks'
import { useThemeStore } from '@/stores/theme'
import { storeToRefs } from 'pinia'
import type { Task } from '@/api/index'
import StatCard from '@/components/StatCard.vue'
import TaskTable from '@/components/TaskTable.vue'
import TaskDetail from '@/components/TaskDetail.vue'
import { ElMessage, ElMessageBox } from 'element-plus'

console.log('[Dashboard] Component setup called at:', new Date().toISOString())

const taskStore = useTaskStore()
const themeStore = useThemeStore()
const { tasks, stats, loading } = storeToRefs(taskStore)

const statusFilter = ref<string>('')
const selectedTask = ref<Task | null>(null)
const detailVisible = ref(false)

const statusOptions = [
  { label: 'All', value: '' },
  { label: 'Pending', value: 'pending' },
  { label: 'Running', value: 'running' },
  { label: 'Completed', value: 'completed' },
  { label: 'Failed', value: 'failed' },
  { label: 'Cancelled', value: 'cancelled' }
]

const handleFilterChange = () => {
  taskStore.fetchTasks({ status: statusFilter.value || undefined })
}

const handleView = (task: Task) => {
  selectedTask.value = task
  detailVisible.value = true
}

const handleCancel = async (taskId: string) => {
  try {
    await ElMessageBox.confirm(
      'Are you sure to cancel this task?',
      'Confirm',
      { type: 'warning' }
    )
    await taskStore.cancelTask(taskId)
    ElMessage.success('Task cancelled')
    detailVisible.value = false
  } catch (e) {
    if ((e as Error).message !== 'cancel') {
      ElMessage.error((e as Error).message)
    }
  }
}

const handleDelete = async (taskId: string) => {
  try {
    await ElMessageBox.confirm(
      'Are you sure to delete this task?',
      'Confirm',
      { type: 'warning' }
    )
    await taskStore.deleteTask(taskId)
    ElMessage.success('Task deleted')
    detailVisible.value = false
  } catch (e) {
    if ((e as Error).message !== 'cancel') {
      ElMessage.error((e as Error).message)
    }
  }
}

onMounted(() => {
  console.log('[Dashboard] onMounted called')
  taskStore.fetchTasks()
  taskStore.fetchStats()
  taskStore.startPolling(3000)
})

onUnmounted(() => {
  console.log('[Dashboard] onUnmounted called - cleaning up')
  // 强制停止轮询
  taskStore.stopPolling()

  // 额外的安全措施：延迟清理确保所有异步操作完成
  setTimeout(() => {
    console.log('[Dashboard] Final cleanup')
    taskStore.stopPolling()
  }, 100)
})
</script>

<template>
  <div class="dashboard" :class="themeStore.theme">
    <!-- Stats Cards -->
    <div class="stats-grid">
      <StatCard
        title="Running"
        :value="stats?.tasks.running ?? 0"
        icon="mdi:play-circle"
        color="primary"
      />
      <StatCard
        title="Pending"
        :value="stats?.tasks.pending ?? 0"
        icon="mdi:clock-outline"
        color="info"
      />
      <StatCard
        title="Completed"
        :value="stats?.tasks.completed ?? 0"
        icon="mdi:check-circle"
        color="success"
      />
      <StatCard
        title="Failed"
        :value="stats?.tasks.failed ?? 0"
        icon="mdi:close-circle"
        color="danger"
      />
    </div>

    <!-- Task List -->
    <div class="task-section">
      <div class="section-header">
        <h2 class="section-title">Tasks</h2>
        <div class="section-actions">
          <el-radio-group v-model="statusFilter" @change="handleFilterChange" size="small">
            <el-radio-button
              v-for="opt in statusOptions"
              :key="opt.value"
              :value="opt.value"
            >
              {{ opt.label }}
            </el-radio-button>
          </el-radio-group>
        </div>
      </div>

      <div class="table-container">
        <TaskTable
          :tasks="tasks"
          :loading="loading"
          @view="handleView"
          @cancel="handleCancel"
          @delete="handleDelete"
        />
      </div>
    </div>

    <!-- Task Detail Drawer -->
    <TaskDetail
      v-model:visible="detailVisible"
      :task="selectedTask"
      @cancel="handleCancel"
      @delete="handleDelete"
    />
  </div>
</template>

<style scoped>
.dashboard {
  max-width: 1400px;
  margin: 0 auto;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
  margin-bottom: 32px;
}

@media (max-width: 1200px) {
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 600px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }
}

.task-section {
  border-radius: 12px;
  padding: 24px;
  border: 1px solid;
  transition: all 0.3s ease;
  display: flex;
  flex-direction: column;
  /* 固定高度：视窗高度 - header(60px) - padding(48px) - stats区域(约140px) - 间距 */
  height: calc(100vh - 280px);
  min-height: 400px;
}

.table-container {
  flex: 1;
  overflow-y: auto;
  margin: 0 -24px -24px;
  padding: 0 24px 24px;
}

/* Dark theme */
.dashboard.dark .task-section {
  background-color: #1a1a2e;
  border-color: #2a2a4e;
}

.dashboard.dark .section-title {
  color: #fff;
}

/* Light theme */
.dashboard.light .task-section {
  background-color: #ffffff;
  border-color: #e4e7ed;
}

.dashboard.light .section-title {
  color: #303133;
}

/* Common styles */
.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.section-title {
  font-size: 18px;
  font-weight: 600;
  margin: 0;
}

.section-actions {
  display: flex;
  gap: 12px;
}
</style>
