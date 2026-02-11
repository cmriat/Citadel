<template>
  <div class="progress-display">
    <!-- Progress Bar -->
    <div class="progress-bar-wrapper">
      <el-progress
        :percentage="progress.percent"
        :status="progressStatus"
        :stroke-width="strokeWidth"
        :show-text="showText"
        :format="formatProgressText"
      />
    </div>

    <!-- Stats Row -->
    <div v-if="showStats" class="progress-stats">
      <!-- Files -->
      <div v-if="progress.total_files > 0" class="stat-item">
        <Icon icon="mdi:file-multiple" class="stat-icon" />
        <span class="stat-value">{{ progress.completed_files }}/{{ progress.total_files }}</span>
        <span class="stat-label">files</span>
      </div>

      <!-- Speed -->
      <div v-if="progress.speed_bytes_per_sec > 0" class="stat-item">
        <Icon icon="mdi:speedometer" class="stat-icon" />
        <span class="stat-value">{{ formatSpeed(progress.speed_bytes_per_sec) }}</span>
      </div>

      <!-- Transferred -->
      <div v-if="progress.bytes_total > 0" class="stat-item">
        <Icon icon="mdi:database" class="stat-icon" />
        <span class="stat-value">{{ formatSize(progress.bytes_transferred) }}</span>
        <span class="stat-label">/ {{ formatSize(progress.bytes_total) }}</span>
      </div>

      <!-- ETA -->
      <div v-if="progress.eta_seconds > 0" class="stat-item">
        <Icon icon="mdi:clock-outline" class="stat-icon" />
        <span class="stat-value">{{ formatEta(progress.eta_seconds) }}</span>
        <span class="stat-label">remaining</span>
      </div>
    </div>

    <!-- Current File -->
    <div v-if="showCurrentFile && progress.current_file" class="current-file">
      <Icon icon="mdi:file-document-outline" />
      <span class="file-name">{{ truncateFileName(progress.current_file) }}</span>
    </div>

    <!-- Message -->
    <div v-if="showMessage && progress.message" class="progress-message">
      {{ progress.message }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { formatPercent } from '@/utils/format'

interface TaskProgress {
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

interface Props {
  progress: TaskProgress
  status?: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
  strokeWidth?: number
  showText?: boolean
  showStats?: boolean
  showCurrentFile?: boolean
  showMessage?: boolean
  compact?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  status: 'running',
  strokeWidth: 8,
  showText: true,
  showStats: true,
  showCurrentFile: true,
  showMessage: true,
  compact: false
})

// Progress status for el-progress
const progressStatus = computed(() => {
  switch (props.status) {
    case 'completed':
      return 'success'
    case 'failed':
      return 'exception'
    default:
      return undefined
  }
})

// Format bytes to human readable
const formatSize = (bytes: number): string => {
  if (bytes === 0) return '0 B'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  if (bytes < 1024 * 1024 * 1024) return (bytes / 1024 / 1024).toFixed(1) + ' MB'
  return (bytes / 1024 / 1024 / 1024).toFixed(2) + ' GB'
}

// Format speed
const formatSpeed = (bytesPerSec: number): string => {
  return formatSize(bytesPerSec) + '/s'
}

// Format ETA to human readable
const formatEta = (seconds: number): string => {
  if (seconds < 60) return `${seconds}s`
  if (seconds < 3600) {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}m ${secs}s`
  }
  const hours = Math.floor(seconds / 3600)
  const mins = Math.floor((seconds % 3600) / 60)
  return `${hours}h ${mins}m`
}

// Truncate long file names
const truncateFileName = (fileName: string, maxLength: number = 50): string => {
  if (fileName.length <= maxLength) return fileName
  const ext = fileName.split('.').pop() || ''
  const name = fileName.slice(0, maxLength - ext.length - 3)
  return `${name}...${ext}`
}

const formatProgressText = (percentage: number): string => {
  return `${formatPercent(percentage)}%`
}
</script>

<style scoped>
.progress-display {
  width: 100%;
}

.progress-bar-wrapper {
  margin-bottom: 8px;
}

.progress-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  margin-bottom: 8px;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
}

.stat-icon {
  font-size: 14px;
  color: #909399;
}

.stat-value {
  font-weight: 600;
  color: #303133;
}

.stat-label {
  color: #909399;
}

.current-file {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #606266;
  margin-bottom: 4px;
}

.file-name {
  font-family: monospace;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.progress-message {
  font-size: 12px;
  color: #909399;
  font-style: italic;
}

/* Dark theme support */
:global(.dark) .stat-value {
  color: #e0e0e0;
}

:global(.dark) .stat-icon,
:global(.dark) .stat-label {
  color: #6a6a8a;
}

:global(.dark) .current-file {
  color: #a0a0c0;
}

:global(.dark) .progress-message {
  color: #6a6a8a;
}
</style>
