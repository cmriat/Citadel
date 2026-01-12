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

const formatSpeed = (bytesPerSec: number): string => {
  if (bytesPerSec < 1024) return bytesPerSec + ' B/s'
  if (bytesPerSec < 1024 * 1024) return (bytesPerSec / 1024).toFixed(1) + ' KB/s'
  if (bytesPerSec < 1024 * 1024 * 1024) return (bytesPerSec / 1024 / 1024).toFixed(1) + ' MB/s'
  return (bytesPerSec / 1024 / 1024 / 1024).toFixed(2) + ' GB/s'
}
</script>

<template>
  <el-table
    :data="tasks"
    :loading="loading"
    style="width: 100%"
    row-class-name="task-row"
  >
    <el-table-column prop="type" label="Type" width="120">
      <template #default="{ row }">
        <div class="type-cell">
          <Icon :icon="getTypeIcon(row.type)" />
          <span>{{ row.type }}</span>
        </div>
      </template>
    </el-table-column>

    <el-table-column prop="progress" label="Progress" width="240">
      <template #default="{ row }">
        <el-progress
          :percentage="row.progress?.percent || 0"
          :status="row.status === 'completed' ? 'success' : row.status === 'failed' ? 'exception' : undefined"
          :stroke-width="8"
        />
      </template>
    </el-table-column>

    <el-table-column prop="message" label="Info" min-width="200">
      <template #default="{ row }">
        <div class="info-cell">
          <span v-if="row.progress?.speed_bytes_per_sec > 0" class="speed-text">
            {{ formatSpeed(row.progress.speed_bytes_per_sec) }}
          </span>
          <span v-if="row.progress?.completed_files > 0" class="files-text">
            {{ row.progress.completed_files }}/{{ row.progress.total_files }} files
          </span>
          <span class="message-text">{{ row.progress?.message || '-' }}</span>
        </div>
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
            @click="emit('view', row)"
          >
            <Icon icon="mdi:eye" />
          </el-button>
          <el-button
            v-if="row.status === 'running' || row.status === 'pending'"
            size="small"
            type="warning"
            @click="emit('cancel', row.id)"
          >
            <Icon icon="mdi:stop" />
          </el-button>
          <el-button
            v-else
            size="small"
            type="danger"
            @click="emit('delete', row.id)"
          >
            <Icon icon="mdi:delete" />
          </el-button>
        </el-button-group>
      </template>
    </el-table-column>
  </el-table>
</template>

<style scoped>
.type-cell {
  display: flex;
  align-items: center;
  gap: 6px;
  text-transform: capitalize;
}

.info-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.speed-text {
  color: #67c23a;
  font-size: 12px;
  font-weight: 600;
}

.files-text {
  color: #409eff;
  font-size: 12px;
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

</style>
