<script setup lang="ts">
import { computed } from 'vue'
import type { Task } from '@/api/index'
import { Icon } from '@iconify/vue'

const props = defineProps<{
  tasks: Task[]
  loading?: boolean
}>()

const emit = defineEmits<{
  cancel: [taskId: string]
  delete: [taskId: string]
  view: [task: Task]
}>()

const getStatusType = (status: string) => {
  const map: Record<string, string> = {
    pending: 'info',
    running: 'primary',
    completed: 'success',
    failed: 'danger',
    cancelled: 'warning'
  }
  return map[status] || 'info'
}

const getStatusIcon = (status: string) => {
  const map: Record<string, string> = {
    pending: 'mdi:clock-outline',
    running: 'mdi:loading',
    completed: 'mdi:check-circle',
    failed: 'mdi:close-circle',
    cancelled: 'mdi:cancel'
  }
  return map[status] || 'mdi:help-circle'
}

const getTypeIcon = (type: string) => {
  const map: Record<string, string> = {
    download: 'mdi:download',
    convert: 'mdi:swap-horizontal',
    upload: 'mdi:upload'
  }
  return map[type] || 'mdi:file'
}

const formatTime = (time: string | null) => {
  if (!time) return '-'
  return new Date(time).toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}
</script>

<template>
  <el-table
    :data="tasks"
    :loading="loading"
    style="width: 100%"
    row-class-name="task-row"
  >
    <el-table-column prop="type" label="Type" width="100">
      <template #default="{ row }">
        <div class="type-cell">
          <Icon :icon="getTypeIcon(row.type)" />
          <span>{{ row.type }}</span>
        </div>
      </template>
    </el-table-column>

    <el-table-column prop="status" label="Status" width="120">
      <template #default="{ row }">
        <el-tag :type="getStatusType(row.status)" size="small">
          <Icon
            :icon="getStatusIcon(row.status)"
            :class="{ spinning: row.status === 'running' }"
            style="margin-right: 4px"
          />
          {{ row.status }}
        </el-tag>
      </template>
    </el-table-column>

    <el-table-column prop="progress" label="Progress" width="200">
      <template #default="{ row }">
        <el-progress
          :percentage="row.progress"
          :status="row.status === 'completed' ? 'success' : row.status === 'failed' ? 'exception' : undefined"
          :stroke-width="8"
        />
      </template>
    </el-table-column>

    <el-table-column prop="message" label="Message" min-width="200">
      <template #default="{ row }">
        <span class="message-text">{{ row.message || '-' }}</span>
      </template>
    </el-table-column>

    <el-table-column prop="created_at" label="Created" width="140">
      <template #default="{ row }">
        {{ formatTime(row.created_at) }}
      </template>
    </el-table-column>

    <el-table-column label="Actions" width="120" fixed="right">
      <template #default="{ row }">
        <el-button-group>
          <el-button
            size="small"
            :icon="() => h(Icon, { icon: 'mdi:eye' })"
            @click="emit('view', row)"
          />
          <el-button
            v-if="row.status === 'running' || row.status === 'pending'"
            size="small"
            type="warning"
            :icon="() => h(Icon, { icon: 'mdi:stop' })"
            @click="emit('cancel', row.id)"
          />
          <el-button
            v-else
            size="small"
            type="danger"
            :icon="() => h(Icon, { icon: 'mdi:delete' })"
            @click="emit('delete', row.id)"
          />
        </el-button-group>
      </template>
    </el-table-column>
  </el-table>
</template>

<script lang="ts">
import { h } from 'vue'
export default {}
</script>

<style scoped>
.type-cell {
  display: flex;
  align-items: center;
  gap: 6px;
  text-transform: capitalize;
}

.message-text {
  color: #a0a0c0;
  font-size: 13px;
}

.spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

:deep(.task-row) {
  background-color: #1a1a2e;
}

:deep(.task-row:hover > td) {
  background-color: #252545 !important;
}
</style>
