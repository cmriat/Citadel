<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { Icon } from '@iconify/vue'

export interface Episode {
  name: string
  path: string
  frame_count: number
  size: number
  thumbnails: string[]
}

interface Props {
  modelValue: boolean
  episodes: Episode[]
  loading?: boolean
  baseDir?: string
}

interface Emits {
  (e: 'update:modelValue', value: boolean): void
  (e: 'confirm', selectedEpisodes: string[]): void
}

const props = withDefaults(defineProps<Props>(), {
  loading: false,
  baseDir: ''
})

const emit = defineEmits<Emits>()

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

// Selected episodes (checked = will merge)
const selectedSet = ref<Set<string>>(new Set())

// Initialize selection when episodes change
watch(() => props.episodes, (eps) => {
  selectedSet.value = new Set(eps.map(ep => ep.name))
}, { immediate: true })

const selectAll = computed({
  get: () => selectedSet.value.size === props.episodes.length,
  set: (val) => {
    if (val) {
      selectedSet.value = new Set(props.episodes.map(ep => ep.name))
    } else {
      selectedSet.value.clear()
    }
  }
})

const isIndeterminate = computed(() => {
  return selectedSet.value.size > 0 && selectedSet.value.size < props.episodes.length
})

const toggleAll = () => {
  if (selectAll.value) {
    selectedSet.value.clear()
  } else {
    selectedSet.value = new Set(props.episodes.map(ep => ep.name))
  }
}

const toggleEpisode = (name: string) => {
  if (selectedSet.value.has(name)) {
    selectedSet.value.delete(name)
  } else {
    selectedSet.value.add(name)
  }
  // Force reactivity update
  selectedSet.value = new Set(selectedSet.value)
}

const isSelected = (name: string) => selectedSet.value.has(name)

const handleConfirm = () => {
  // Return selected episode names
  const selected = Array.from(selectedSet.value)
  emit('confirm', selected)
  visible.value = false
}

const formatSize = (bytes: number): string => {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`
}

const frameTitles = ['开始', '1/3', '2/3', '结束']
</script>

<template>
  <el-dialog
    v-model="visible"
    title="选择要合并的 Episode"
    width="900px"
    :close-on-click-modal="false"
  >
    <div class="dialog-hint">
      <Icon icon="mdi:information-outline" />
      <span>以下是通过质检的 Episode，勾选要合并的项（默认全选）</span>
    </div>

    <div v-if="loading" class="loading-state">
      <Icon icon="mdi:loading" class="spin" />
      <span>正在加载 Episode...</span>
    </div>

    <div v-else-if="episodes.length === 0" class="empty-state">
      <Icon icon="mdi:folder-off-outline" />
      <span>没有可用的 Episode</span>
    </div>

    <div v-else class="episode-list">
      <div
        v-for="ep in episodes"
        :key="ep.name"
        class="episode-card"
        :class="{ excluded: !isSelected(ep.name) }"
        @click="toggleEpisode(ep.name)"
      >
        <div class="episode-header">
          <el-checkbox
            :model-value="isSelected(ep.name)"
            @click.stop
            @change="toggleEpisode(ep.name)"
          >
            <span class="ep-name">{{ ep.name }}</span>
          </el-checkbox>
          <span class="ep-meta">{{ ep.frame_count }} 帧 · {{ formatSize(ep.size) }}</span>
        </div>
        <div class="frame-previews">
          <template v-if="ep.thumbnails && ep.thumbnails.length > 0">
            <div
              v-for="(thumb, idx) in ep.thumbnails"
              :key="idx"
              class="frame-preview"
            >
              <img
                :src="thumb"
                :title="frameTitles[idx] || `Frame ${idx}`"
                alt="preview"
              />
              <span class="frame-label">{{ frameTitles[idx] }}</span>
            </div>
          </template>
          <div v-else class="no-preview">
            <Icon icon="mdi:image-off-outline" />
            <span>无预览</span>
          </div>
        </div>
      </div>
    </div>

    <template #footer>
      <div class="dialog-footer">
        <div class="footer-left">
          <el-checkbox
            :model-value="selectAll"
            :indeterminate="isIndeterminate"
            @change="toggleAll"
          >
            全选
          </el-checkbox>
          <span class="selection-count">
            已选择 <strong>{{ selectedSet.size }}</strong> / {{ episodes.length }} 个 Episode
          </span>
        </div>
        <div class="footer-actions">
          <el-button @click="visible = false">取消</el-button>
          <el-button
            type="primary"
            :disabled="selectedSet.size === 0"
            @click="handleConfirm"
          >
            <Icon icon="mdi:merge" />
            开始合并 ({{ selectedSet.size }})
          </el-button>
        </div>
      </div>
    </template>
  </el-dialog>
</template>

<style scoped>
.dialog-hint {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px;
  margin-bottom: 16px;
  background: var(--el-color-info-light-9);
  border-radius: 6px;
  font-size: 13px;
  color: var(--el-text-color-regular);
}

.dialog-hint .iconify {
  font-size: 18px;
  color: var(--el-color-info);
}

.loading-state,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px;
  color: var(--el-text-color-secondary);
  gap: 12px;
}

.loading-state .iconify,
.empty-state .iconify {
  font-size: 48px;
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.episode-list {
  max-height: 520px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 2px;
}

/* Custom scrollbar */
.episode-list::-webkit-scrollbar {
  width: 8px;
}

.episode-list::-webkit-scrollbar-track {
  background: var(--el-fill-color-light);
  border-radius: 4px;
}

.episode-list::-webkit-scrollbar-thumb {
  background: var(--el-border-color);
  border-radius: 4px;
}

.episode-list::-webkit-scrollbar-thumb:hover {
  background: var(--el-border-color-dark);
}

.episode-card {
  border: 2px solid var(--el-border-color);
  border-radius: 8px;
  padding: 14px;
  cursor: pointer;
  transition: all 0.2s;
  background: var(--el-bg-color);
}

.episode-card:hover {
  border-color: var(--el-color-primary);
  box-shadow: 0 2px 12px rgba(64, 158, 255, 0.15);
}

.episode-card.excluded {
  opacity: 0.4;
  background: var(--el-fill-color-lighter);
  border-color: var(--el-border-color-lighter);
}

.episode-card.excluded:hover {
  opacity: 0.6;
  border-color: var(--el-border-color);
}

.episode-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.ep-name {
  font-weight: 600;
  font-size: 14px;
  color: var(--el-text-color-primary);
}

.ep-meta {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
}

.frame-previews {
  display: flex;
  gap: 10px;
  overflow-x: auto;
}

.frame-preview {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
  align-items: center;
}

.frame-preview img {
  width: 160px;
  height: 120px;
  object-fit: cover;
  border-radius: 6px;
  border: 1px solid var(--el-border-color-lighter);
  background: var(--el-fill-color-light);
}

.frame-label {
  font-size: 11px;
  color: var(--el-text-color-secondary);
  font-weight: 500;
}

.no-preview {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 120px;
  background: var(--el-fill-color-light);
  border-radius: 6px;
  color: var(--el-text-color-secondary);
  gap: 8px;
}

.no-preview .iconify {
  font-size: 32px;
}

.dialog-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.footer-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.selection-count {
  font-size: 13px;
  color: var(--el-text-color-regular);
}

.selection-count strong {
  color: var(--el-color-primary);
  font-weight: 600;
}

.footer-actions {
  display: flex;
  gap: 8px;
}

.footer-actions .iconify {
  margin-right: 4px;
}
</style>
