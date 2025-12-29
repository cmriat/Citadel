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
}

interface Emits {
  (e: 'update:modelValue', value: boolean): void
  (e: 'confirm', excludeEpisodes: string[]): void
}

const props = withDefaults(defineProps<Props>(), {
  loading: false
})

const emit = defineEmits<Emits>()

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

// Selected episodes (checked = will upload)
const selectedSet = ref<string[]>([])

// Initialize selection when episodes change
watch(() => props.episodes, (eps) => {
  selectedSet.value = eps.map(ep => ep.name)
}, { immediate: true })

const selectAll = computed({
  get: () => selectedSet.value.length === props.episodes.length,
  set: (val) => {
    selectedSet.value = val ? props.episodes.map(ep => ep.name) : []
  }
})

const isIndeterminate = computed(() => {
  return selectedSet.value.length > 0 && selectedSet.value.length < props.episodes.length
})

const toggleAll = () => {
  if (selectAll.value) {
    selectedSet.value = []
  } else {
    selectedSet.value = props.episodes.map(ep => ep.name)
  }
}

const toggleEpisode = (name: string) => {
  const idx = selectedSet.value.indexOf(name)
  if (idx >= 0) {
    selectedSet.value.splice(idx, 1)
  } else {
    selectedSet.value.push(name)
  }
}

const isSelected = (name: string) => selectedSet.value.includes(name)

const handleConfirm = () => {
  // Get excluded episodes (unchecked ones)
  const excludeEpisodes = props.episodes
    .filter(ep => !selectedSet.value.includes(ep.name))
    .map(ep => ep.name)
  emit('confirm', excludeEpisodes)
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
    title="选择要上传的 Episode"
    width="760px"
    :close-on-click-modal="false"
  >
    <div v-if="loading" class="loading-state">
      <Icon icon="mdi:loading" class="spin" />
      <span>正在扫描 Episode...</span>
    </div>

    <div v-else-if="episodes.length === 0" class="empty-state">
      <Icon icon="mdi:folder-off-outline" />
      <span>未找到 LeRobot 格式的 Episode</span>
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
          <span class="ep-meta">{{ ep.frame_count }} frames · {{ formatSize(ep.size) }}</span>
        </div>
        <div class="frame-previews">
          <template v-if="ep.thumbnails && ep.thumbnails.length > 0">
            <img
              v-for="(thumb, idx) in ep.thumbnails"
              :key="idx"
              :src="thumb"
              :title="frameTitles[idx] || `Frame ${idx}`"
              alt="preview"
            />
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
        <div class="select-all">
          <el-checkbox
            :model-value="selectAll"
            :indeterminate="isIndeterminate"
            @change="toggleAll"
          >
            全选 ({{ selectedSet.length }}/{{ episodes.length }})
          </el-checkbox>
        </div>
        <div class="actions">
          <el-button @click="visible = false">取消</el-button>
          <el-button
            type="primary"
            :disabled="selectedSet.length === 0"
            @click="handleConfirm"
          >
            <Icon icon="mdi:upload" />
            上传 {{ selectedSet.length }} 个 Episode
          </el-button>
        </div>
      </div>
    </template>
  </el-dialog>
</template>

<style scoped>
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
  max-height: 500px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.episode-card {
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  padding: 12px;
  cursor: pointer;
  transition: all 0.2s;
  background: var(--el-bg-color);
}

.episode-card:hover {
  border-color: var(--el-color-primary);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.episode-card.excluded {
  opacity: 0.5;
  background: var(--el-fill-color-light);
}

.episode-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.ep-name {
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.ep-meta {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.frame-previews {
  display: flex;
  gap: 8px;
}

.frame-previews img {
  width: 160px;
  height: 120px;
  object-fit: cover;
  border-radius: 4px;
  border: 1px solid var(--el-border-color-lighter);
}

.no-preview {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 120px;
  background: var(--el-fill-color-light);
  border-radius: 4px;
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

.select-all {
  color: var(--el-text-color-regular);
}

.actions {
  display: flex;
  gap: 8px;
}

.actions .iconify {
  margin-right: 4px;
}
</style>
