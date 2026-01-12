<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { useTaskStore } from '@/stores/tasks'
import { useThemeStore } from '@/stores/theme'

const taskStore = useTaskStore()
const themeStore = useThemeStore()

// 获取第一个运行中的任务
const runningTask = computed(() => taskStore.runningTasks[0] || null)

// 统计数据
const stats = computed(() => {
  const s = taskStore.stats
  if (!s) return { running: 0, pending: 0, completed: 0, failed: 0 }
  return {
    running: s.tasks?.running ?? 0,
    pending: s.tasks?.pending ?? 0,
    completed: s.tasks?.completed ?? 0,
    failed: s.tasks?.failed ?? 0
  }
})

// 始终显示预览条（移除条件判断）
const shouldShow = computed(() => true)

// 任务类型图标
const taskIcon = computed(() => {
  if (!runningTask.value) return 'mdi:check-circle'
  switch (runningTask.value.type) {
    case 'download': return 'mdi:download'
    case 'convert': return 'mdi:swap-horizontal'
    case 'upload': return 'mdi:upload'
    default: return 'mdi:cog'
  }
})

// 进度百分比
const progress = computed(() => {
  return runningTask.value?.progress?.percent || 0
})

// 简短消息
const shortMessage = computed(() => {
  const msg = runningTask.value?.progress?.message || ''
  return msg.length > 40 ? msg.slice(0, 40) + '...' : msg
})
</script>

<template>
  <div
    v-if="shouldShow"
    class="task-preview-card"
    :class="themeStore.theme"
  >
      <!-- 运行中任务 -->
      <div class="running-task" v-if="runningTask">
        <Icon :icon="taskIcon" class="task-icon" />
        <span class="task-type">{{ runningTask.type }}</span>
        <el-progress
          :percentage="progress"
          :stroke-width="6"
          :show-text="false"
          class="progress-bar"
        />
        <span class="task-percent">{{ progress }}%</span>
        <span class="task-msg">{{ shortMessage }}</span>
      </div>
      <div class="no-running" v-else>
        <Icon icon="mdi:check-circle" class="idle-icon" />
        <span>无运行中任务</span>
      </div>

      <!-- 分隔线 -->
      <div class="divider"></div>

      <!-- 统计 -->
      <div class="stats">
        <span class="stat pending" v-if="stats.pending > 0">
          <Icon icon="mdi:clock-outline" />
          <span>{{ stats.pending }}</span>
        </span>
        <span class="stat done">
          <Icon icon="mdi:check" />
          <span>{{ stats.completed }}</span>
        </span>
        <span class="stat failed" v-if="stats.failed > 0">
          <Icon icon="mdi:close" />
          <span>{{ stats.failed }}</span>
        </span>
      </div>

      <!-- 跳转按钮 -->
      <router-link to="/" class="view-all" title="查看任务列表">
        <Icon icon="mdi:arrow-right" />
      </router-link>
  </div>
</template>

<style scoped>
.task-preview-card {
  display: flex;
  align-items: center;
  padding: 16px 20px;
  gap: 16px;
  border-radius: 12px;
  border: 1px solid;
  margin-top: 16px;
}

/* 深色主题 */
.task-preview-card.dark {
  background: #1a1a2e;
  border-color: #2a2a4e;
}

/* 浅色主题 */
.task-preview-card.light {
  background: #fff;
  border-color: #e4e7ed;
}

.running-task {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  min-width: 0;
}

.task-icon {
  font-size: 20px;
  color: var(--el-color-primary);
  flex-shrink: 0;
}

.task-type {
  font-weight: 600;
  text-transform: capitalize;
  color: var(--el-text-color-primary);
  flex-shrink: 0;
}

.progress-bar {
  width: 120px;
  flex-shrink: 0;
}

.task-percent {
  font-size: 12px;
  font-weight: 600;
  color: var(--el-color-primary);
  min-width: 36px;
  flex-shrink: 0;
}

.task-msg {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  min-width: 0;
}

.no-running {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  color: var(--el-text-color-secondary);
}

.idle-icon {
  font-size: 18px;
  color: var(--el-color-success);
}

.divider {
  width: 1px;
  height: 24px;
  background: var(--el-border-color-lighter);
}

.stats {
  display: flex;
  gap: 12px;
  flex-shrink: 0;
}

.stat {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  font-weight: 500;
}

.stat .iconify {
  font-size: 16px;
}

.stat.pending {
  color: var(--el-color-warning);
}

.stat.done {
  color: var(--el-color-success);
}

.stat.failed {
  color: var(--el-color-danger);
}

.view-all {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 6px;
  color: var(--el-text-color-regular);
  transition: all 0.2s;
  flex-shrink: 0;
}

.view-all:hover {
  background: var(--el-fill-color-light);
  color: var(--el-color-primary);
}

.view-all .iconify {
  font-size: 18px;
}
</style>
