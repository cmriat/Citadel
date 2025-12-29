<script setup lang="ts">
import { computed } from 'vue'
import type { Task } from '@/api/index'
import { Icon } from '@iconify/vue'
import ProgressDisplay from './ProgressDisplay.vue'

const props = defineProps<{
  task: Task | null
  visible: boolean
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  cancel: [taskId: string]
  delete: [taskId: string]
}>()

const drawerVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val)
})

const getStatusType = (status: string) => {
  const map: Record<string, string> = {
    pending: 'info',
    running: '',
    completed: 'success',
    failed: 'danger',
    cancelled: 'warning'
  }
  return map[status] || 'info'
}

const formatTime = (time: string | null) => {
  if (!time) return '-'
  return new Date(time).toLocaleString('zh-CN')
}

const formatDuration = (start: string | null, end: string | null) => {
  if (!start) return '-'
  const startTime = new Date(start).getTime()
  const endTime = end ? new Date(end).getTime() : Date.now()
  const seconds = Math.floor((endTime - startTime) / 1000)
  if (seconds < 60) return `${seconds}s`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`
  return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`
}
</script>

<template>
  <el-drawer
    v-model="drawerVisible"
    title="Task Details"
    direction="rtl"
    size="450px"
  >
    <template v-if="task">
      <div class="detail-section">
        <div class="section-title">Basic Info</div>
        <div class="detail-grid">
          <div class="detail-item">
            <span class="label">ID</span>
            <span class="value">{{ task.id }}</span>
          </div>
          <div class="detail-item">
            <span class="label">Type</span>
            <span class="value capitalize">
              <Icon :icon="task.type === 'download' ? 'mdi:download' : task.type === 'convert' ? 'mdi:swap-horizontal' : 'mdi:upload'" />
              {{ task.type }}
            </span>
          </div>
          <div class="detail-item">
            <span class="label">Status</span>
            <el-tag :type="getStatusType(task.status)" size="small">
              {{ task.status }}
            </el-tag>
          </div>
          <div class="detail-item">
            <span class="label">Progress</span>
            <span class="value">{{ task.progress?.percent || 0 }}%</span>
          </div>
        </div>
      </div>

      <!-- Progress Display Section -->
      <div v-if="task.status === 'running'" class="detail-section">
        <div class="section-title">Live Progress</div>
        <ProgressDisplay
          :progress="task.progress"
          :status="task.status"
          :show-current-file="true"
          :show-message="true"
        />
      </div>

      <div class="detail-section">
        <div class="section-title">Timeline</div>
        <div class="detail-grid">
          <div class="detail-item">
            <span class="label">Created</span>
            <span class="value">{{ formatTime(task.created_at) }}</span>
          </div>
          <div class="detail-item">
            <span class="label">Started</span>
            <span class="value">{{ formatTime(task.started_at) }}</span>
          </div>
          <div class="detail-item">
            <span class="label">Completed</span>
            <span class="value">{{ formatTime(task.completed_at) }}</span>
          </div>
          <div class="detail-item">
            <span class="label">Duration</span>
            <span class="value">{{ formatDuration(task.started_at, task.completed_at) }}</span>
          </div>
        </div>
      </div>

      <div class="detail-section">
        <div class="section-title">Message</div>
        <div class="message-box">{{ task.progress?.message || 'No message' }}</div>
      </div>

      <div class="detail-section">
        <div class="section-title">Configuration</div>
        <pre class="config-box">{{ JSON.stringify(task.config, null, 2) }}</pre>
      </div>

      <div v-if="task.result" class="detail-section">
        <div class="section-title">Result</div>
        <pre class="config-box">{{ JSON.stringify(task.result, null, 2) }}</pre>
      </div>

      <div class="detail-actions">
        <el-button
          v-if="task.status === 'running' || task.status === 'pending'"
          type="warning"
          @click="emit('cancel', task.id)"
        >
          <Icon icon="mdi:stop" style="margin-right: 4px" />
          Cancel Task
        </el-button>
        <el-button
          v-else
          type="danger"
          @click="emit('delete', task.id)"
        >
          <Icon icon="mdi:delete" style="margin-right: 4px" />
          Delete Task
        </el-button>
      </div>
    </template>
  </el-drawer>
</template>

<style scoped>
.detail-section {
  margin-bottom: 24px;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #a0a0c0;
  margin-bottom: 12px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.detail-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.detail-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.label {
  font-size: 12px;
  color: #6a6a8a;
}

.value {
  font-size: 14px;
  color: #fff;
  display: flex;
  align-items: center;
  gap: 6px;
}

.capitalize {
  text-transform: capitalize;
}

.message-box {
  padding: 12px;
  background-color: #252545;
  border-radius: 8px;
  font-size: 14px;
  color: #a0a0c0;
}

.config-box {
  padding: 12px;
  background-color: #252545;
  border-radius: 8px;
  font-size: 12px;
  color: #a0a0c0;
  overflow-x: auto;
  margin: 0;
}

.detail-actions {
  margin-top: 32px;
  padding-top: 24px;
  border-top: 1px solid #2a2a4e;
}
</style>
