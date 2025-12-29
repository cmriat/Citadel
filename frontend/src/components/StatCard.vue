<script setup lang="ts">
import { Icon } from '@iconify/vue'
import { useThemeStore } from '@/stores/theme'

const themeStore = useThemeStore()

defineProps<{
  title: string
  value: number | string
  icon: string
  color?: 'primary' | 'success' | 'warning' | 'danger' | 'info'
}>()
</script>

<template>
  <div class="stat-card" :class="[color, themeStore.theme]">
    <div class="stat-icon">
      <Icon :icon="icon" />
    </div>
    <div class="stat-info">
      <div class="stat-value">{{ value }}</div>
      <div class="stat-title">{{ title }}</div>
    </div>
  </div>
</template>

<style scoped>
.stat-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
  border-radius: 12px;
  border: 1px solid;
  transition: all 0.3s ease;
}

.stat-card:hover {
  transform: translateY(-2px);
}

/* Dark theme */
.stat-card.dark {
  background-color: #1a1a2e;
  border-color: #2a2a4e;
}

.stat-card.dark .stat-value {
  color: #fff;
}

.stat-card.dark .stat-title {
  color: #6a6a8a;
}

/* Light theme */
.stat-card.light {
  background-color: #ffffff;
  border-color: #e4e7ed;
}

.stat-card.light .stat-value {
  color: #303133;
}

.stat-card.light .stat-title {
  color: #909399;
}

/* Common styles */
.stat-icon {
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  font-size: 24px;
  background-color: #409eff20;
  color: #409eff;
}

.stat-card.success .stat-icon {
  background-color: #67c23a20;
  color: #67c23a;
}

.stat-card.warning .stat-icon {
  background-color: #e6a23c20;
  color: #e6a23c;
}

.stat-card.danger .stat-icon {
  background-color: #f56c6c20;
  color: #f56c6c;
}

.stat-card.info .stat-icon {
  background-color: #90939920;
  color: #909399;
}

.stat-info {
  flex: 1;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  line-height: 1.2;
}

.stat-title {
  font-size: 14px;
  margin-top: 4px;
}
</style>
