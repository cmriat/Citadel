<script setup lang="ts">
/**
 * QC 质检组件
 *
 * 用于在 Merge 前对 episode 进行质量检查，支持视频播放和标记通过/不通过
 */

import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { Icon } from '@iconify/vue'
import { ElMessage, ElMessageBox } from 'element-plus'

interface Episode {
  name: string
  path: string
  frame_count: number
  size: number
  thumbnails: string[]
}

interface QCResult {
  passed: string[]
  failed: string[]
}

interface Props {
  modelValue: boolean
  episodes: Episode[]
  baseDir: string
  loading?: boolean
  initialResult?: QCResult  // 上次保存的 QC 结果
}

const props = withDefaults(defineProps<Props>(), {
  loading: false,
  initialResult: undefined
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'confirm', result: QCResult): void
  (e: 'episode-update', payload: { episodeName: string; status: 'passed' | 'failed' | 'pending' }): void
  (e: 'bulk-episode-update', payload: { episodeName: string; status: 'passed' | 'failed' | 'pending'; baseStatus: 'passed' | 'failed' | 'pending' }[]): void
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

// QC 状态: 'passed' | 'failed' | 'pending'
const qcStatus = ref<Record<string, 'passed' | 'failed' | 'pending'>>({})
const currentEpisode = ref<string | null>(null)
const hasShownResumeHint = ref(false)

// 相机切换
const cameras = [
  { id: 'cam_env', label: '环境', icon: 'mdi:camera' },
  { id: 'cam_left_wrist', label: '左腕', icon: 'mdi:hand-back-left' },
  { id: 'cam_right_wrist', label: '右腕', icon: 'mdi:hand-back-right' }
]
const currentCamera = ref('cam_env')

const resetQCState = () => {
  qcStatus.value = {}
  currentEpisode.value = null
  currentCamera.value = 'cam_env'
  hasShownResumeHint.value = false
}

const activeBaseDir = ref<string | null>(null)

watch(visible, (val) => {
  if (!val) {
    activeBaseDir.value = null
    resetQCState()
    return
  }

  activeBaseDir.value = props.baseDir
  resetQCState()
})

// 初始化 QC 状态（episodes / initialResult 可能异步到达）
watch(
  [() => props.episodes, () => props.initialResult, () => props.baseDir, () => visible.value],
  ([eps, initialResult, baseDir, isVisible]) => {
    if (!isVisible) return

    if (activeBaseDir.value !== baseDir) {
      activeBaseDir.value = baseDir
      resetQCState()
    }

    const newStatus: Record<string, 'passed' | 'failed' | 'pending'> = {}
    let resumeCount = 0

    const passed = new Set(initialResult?.passed ?? [])
    const failed = new Set(initialResult?.failed ?? [])

    eps.forEach(ep => {
      if (passed.has(ep.name)) {
        newStatus[ep.name] = 'passed'
        resumeCount++
      } else if (failed.has(ep.name)) {
        newStatus[ep.name] = 'failed'
        resumeCount++
      } else {
        newStatus[ep.name] = 'pending'
      }
    })

    qcStatus.value = newStatus

    if (resumeCount > 0 && !hasShownResumeHint.value && eps.length > 0) {
      hasShownResumeHint.value = true
      const pendingEpisodes = eps.filter(ep => newStatus[ep.name] === 'pending')
      const firstPending = pendingEpisodes[0]

      if (firstPending) {
        currentEpisode.value = firstPending.name
        ElMessage.info({
          message: `已恢复上次进度: ${resumeCount} 个已标记，从 ${firstPending.name} 继续`,
          duration: 4000
        })
      } else {
        currentEpisode.value = eps[0]?.name || null
        ElMessage.success({
          message: `所有 ${resumeCount} 个 episode 已标记完成`,
          duration: 3000
        })
      }
    }
  },
  { immediate: true }
)

// 统计
const stats = computed(() => {
  const values = Object.values(qcStatus.value)
  return {
    total: values.length,
    passed: values.filter(v => v === 'passed').length,
    failed: values.filter(v => v === 'failed').length,
    pending: values.filter(v => v === 'pending').length
  }
})

// 获取视频流 URL
const getVideoUrl = (episodeName: string, camera?: string): string => {
  const encodedBaseDir = encodeURIComponent(props.baseDir)
  const encodedEpisode = encodeURIComponent(episodeName)
  const cam = camera || currentCamera.value
  return `/api/upload/video-stream?base_dir=${encodedBaseDir}&episode_name=${encodedEpisode}&camera=${cam}`
}

// 当前视频 key（用于强制刷新 video 元素）
const videoKey = computed(() => `${currentEpisode.value}-${currentCamera.value}`)

const playVideo = async (episodeName: string) => {
  const status = qcStatus.value[episodeName]
  if (status && status !== 'pending') {
    try {
      await ElMessageBox.confirm(
        `该 episode 已标记为「${status === 'passed' ? '通过' : '不通过'}」，是否继续查看/修改？`,
        '提示',
        {
          confirmButtonText: '继续',
          cancelButtonText: '取消',
          type: 'warning',
        }
      )
    } catch {
      return
    }
  }

  currentEpisode.value = episodeName
}

const markPassed = (episodeName: string) => {
  qcStatus.value[episodeName] = 'passed'
  emit('episode-update', { episodeName, status: 'passed' })
  autoNextPending()
}

const markFailed = (episodeName: string) => {
  qcStatus.value[episodeName] = 'failed'
  emit('episode-update', { episodeName, status: 'failed' })
  autoNextPending()
}

// 自动跳转到下一个待检查的
const autoNextPending = () => {
  const currentIdx = props.episodes.findIndex(e => e.name === currentEpisode.value)
  // 从当前位置往后找
  for (let i = currentIdx + 1; i < props.episodes.length; i++) {
    const ep = props.episodes[i]
    if (ep && qcStatus.value[ep.name] === 'pending') {
      currentEpisode.value = ep.name
      return
    }
  }
  // 从头找
  for (let i = 0; i < currentIdx; i++) {
    const ep = props.episodes[i]
    if (ep && qcStatus.value[ep.name] === 'pending') {
      currentEpisode.value = ep.name
      return
    }
  }
}

// 全部标记为通过
const markAllPassed = () => {
  const updates = Object.entries(qcStatus.value)
    .filter(([_, s]) => s !== 'passed')
    .map(([episodeName, baseStatus]) => ({ episodeName, status: 'passed' as const, baseStatus }))

  Object.keys(qcStatus.value).forEach(k => {
    qcStatus.value[k] = 'passed'
  })

  if (updates.length > 0) {
    emit('bulk-episode-update', updates)
  }
  ElMessage.success(`已将 ${stats.value.total} 个 episode 标记为通过`)
}

// 重置所有状态
const resetAll = () => {
  const updates = Object.entries(qcStatus.value)
    .filter(([_, s]) => s !== 'pending')
    .map(([episodeName, baseStatus]) => ({ episodeName, status: 'pending' as const, baseStatus }))

  Object.keys(qcStatus.value).forEach(k => {
    qcStatus.value[k] = 'pending'
  })

  if (updates.length > 0) {
    emit('bulk-episode-update', updates)
  }
  ElMessage.info('已重置所有状态')
}

// 确认并返回结果
const handleConfirm = () => {
  const result: QCResult = {
    passed: Object.entries(qcStatus.value)
      .filter(([_, s]) => s === 'passed')
      .map(([n]) => n),
    failed: Object.entries(qcStatus.value)
      .filter(([_, s]) => s === 'failed')
      .map(([n]) => n)
  }
  emit('confirm', result)
  visible.value = false
}

// 获取 episode 对象
const currentEpisodeData = computed(() => {
  return props.episodes.find(e => e.name === currentEpisode.value)
})

// 格式化文件大小
const formatSize = (bytes: number): string => {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

// 键盘快捷键
const handleKeyDown = (e: KeyboardEvent) => {
  if (!visible.value || !currentEpisode.value) return

  switch (e.key) {
    case 'ArrowUp':
    case 'k':
      e.preventDefault()
      navigatePrev()
      break
    case 'ArrowDown':
    case 'j':
      e.preventDefault()
      navigateNext()
      break
    case 'p':
    case 'Enter':
      e.preventDefault()
      markPassed(currentEpisode.value)
      break
    case 'f':
    case 'Backspace':
      e.preventDefault()
      markFailed(currentEpisode.value)
      break
    case ' ':
      e.preventDefault()
      toggleVideoPlay()
      break
    // 相机切换快捷键
    case '1':
      e.preventDefault()
      currentCamera.value = 'cam_env'
      break
    case '2':
      e.preventDefault()
      currentCamera.value = 'cam_left_wrist'
      break
    case '3':
      e.preventDefault()
      currentCamera.value = 'cam_right_wrist'
      break
  }
}

const navigatePrev = () => {
  const idx = props.episodes.findIndex(e => e.name === currentEpisode.value)
  if (idx > 0) {
    const prevEp = props.episodes[idx - 1]
    if (prevEp) {
      currentEpisode.value = prevEp.name
    }
  }
}

const navigateNext = () => {
  const idx = props.episodes.findIndex(e => e.name === currentEpisode.value)
  if (idx >= 0 && idx < props.episodes.length - 1) {
    const nextEp = props.episodes[idx + 1]
    if (nextEp) {
      currentEpisode.value = nextEp.name
    }
  }
}

const toggleVideoPlay = () => {
  // 三路视频并排后不再支持单一 videoRef 控制，保留空实现以兼容快捷键分支
}

onMounted(() => {
  window.addEventListener('keydown', handleKeyDown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown)
})

</script>

<template>
  <el-dialog
    v-model="visible"
    title="QC 质检 - Episode 视频预览"
    width="1100px"
    :close-on-click-modal="false"
    destroy-on-close
  >
    <div class="qc-container">
      <!-- 左侧: Episode 列表 -->
      <div class="episode-list">
        <div class="list-header">
          <span class="title">Episode 列表</span>
          <div class="header-actions">
            <el-button size="small" text @click="resetAll">
              <Icon icon="mdi:refresh" />
            </el-button>
            <el-button size="small" type="success" @click="markAllPassed">
              <Icon icon="mdi:check-all" /> 全部通过
            </el-button>
          </div>
        </div>

        <div class="episodes" v-loading="loading">
          <div
            v-for="ep in episodes"
            :key="ep.name"
            class="episode-item"
            :class="{
              active: currentEpisode === ep.name,
              passed: qcStatus[ep.name] === 'passed',
              failed: qcStatus[ep.name] === 'failed'
            }"
            @click="playVideo(ep.name)"
          >
            <div class="ep-thumbnail">
              <img
                v-if="ep.thumbnails?.[0]"
                :src="ep.thumbnails[0]"
                alt="thumbnail"
              />
              <Icon v-else icon="mdi:video-outline" class="placeholder-icon" />
            </div>
            <div class="ep-info">
              <span class="ep-name">{{ ep.name }}</span>
              <span class="ep-meta">{{ ep.frame_count }} 帧 · {{ formatSize(ep.size) }}</span>
            </div>
            <div class="ep-status">
              <Icon
                v-if="qcStatus[ep.name] === 'passed'"
                icon="mdi:check-circle"
                class="status-icon passed"
              />
              <Icon
                v-else-if="qcStatus[ep.name] === 'failed'"
                icon="mdi:close-circle"
                class="status-icon failed"
              />
              <Icon
                v-else
                icon="mdi:help-circle-outline"
                class="status-icon pending"
              />
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧: 视频播放器 -->
      <div class="video-panel">
        <div v-if="!currentEpisode" class="no-selection">
          <Icon icon="mdi:video-off-outline" class="big-icon" />
          <span>点击左侧 Episode 播放视频</span>
          <span class="hint">快捷键: ↑↓ 导航, P 通过, F 不通过, 空格 播放/暂停, 1/2/3 切换相机</span>
        </div>

        <template v-else>
          <div class="video-header">
            <div class="video-info">
              <span class="video-title">{{ currentEpisode }}</span>
              <span v-if="currentEpisodeData" class="video-meta">
                {{ currentEpisodeData.frame_count }} 帧 · {{ formatSize(currentEpisodeData.size) }}
              </span>
            </div>
          </div>

          <!-- 三个相机并排显示 -->
          <div class="video-grid">
            <div v-for="cam in cameras" :key="cam.id" class="video-cell">
              <div class="camera-label">
                <Icon :icon="cam.icon" /> {{ cam.label }}
              </div>
              <video
                :key="`${currentEpisode}-${cam.id}`"
                :src="getVideoUrl(currentEpisode, cam.id)"
                controls
                autoplay
                muted
                class="video-player-small"
              />
            </div>
          </div>

          <div class="qc-actions">
            <el-button
              type="danger"
              size="large"
              @click="markFailed(currentEpisode)"
              :class="{ active: qcStatus[currentEpisode] === 'failed' }"
            >
              <Icon icon="mdi:close" /> 不通过 (F)
            </el-button>
            <el-button
              type="success"
              size="large"
              @click="markPassed(currentEpisode)"
              :class="{ active: qcStatus[currentEpisode] === 'passed' }"
            >
              <Icon icon="mdi:check" /> 通过 (P)
            </el-button>
          </div>
        </template>
      </div>
    </div>

    <template #footer>
      <div class="dialog-footer">
        <div class="stats">
          <span class="stat passed">
            <Icon icon="mdi:check-circle" /> {{ stats.passed }} 通过
          </span>
          <span class="stat failed">
            <Icon icon="mdi:close-circle" /> {{ stats.failed }} 不通过
          </span>
          <span class="stat pending">
            <Icon icon="mdi:help-circle-outline" /> {{ stats.pending }} 待检查
          </span>
        </div>
        <div class="actions">
          <el-button @click="visible = false">取消</el-button>
          <el-button
            type="primary"
            :disabled="stats.passed === 0"
            @click="handleConfirm"
          >
            确认 ({{ stats.passed }} 个通过)
          </el-button>
        </div>
      </div>
    </template>
  </el-dialog>
</template>

<style scoped>
.qc-container {
  display: flex;
  gap: 20px;
  height: 550px;
}

/* 左侧 Episode 列表 */
.episode-list {
  width: 320px;
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  border-bottom: 1px solid var(--el-border-color);
  background: var(--el-fill-color-light);
}

.list-header .title {
  font-weight: 600;
}

.header-actions {
  display: flex;
  gap: 4px;
}

.episodes {
  flex: 1;
  overflow-y: auto;
}

.episode-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  cursor: pointer;
  border-bottom: 1px solid var(--el-border-color-lighter);
  transition: all 0.2s;
}

.episode-item:hover {
  background: var(--el-fill-color-light);
}

.episode-item.active {
  background: var(--el-color-primary-light-9);
  border-left: 3px solid var(--el-color-primary);
}

.episode-item.passed {
  background: rgba(103, 194, 58, 0.08);
}

.episode-item.failed {
  background: rgba(245, 108, 108, 0.08);
}

.ep-thumbnail {
  width: 48px;
  height: 36px;
  border-radius: 4px;
  overflow: hidden;
  background: var(--el-fill-color-dark);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.ep-thumbnail img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.placeholder-icon {
  font-size: 20px;
  color: var(--el-text-color-secondary);
}

.ep-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.ep-name {
  font-weight: 500;
  font-size: 13px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.ep-meta {
  font-size: 11px;
  color: var(--el-text-color-secondary);
}

.ep-status {
  flex-shrink: 0;
}

.status-icon {
  font-size: 20px;
}

.status-icon.passed {
  color: #67c23a;
}

.status-icon.failed {
  color: #f56c6c;
}

.status-icon.pending {
  color: #909399;
}

/* 右侧视频面板 */
.video-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  overflow: hidden;
}

.no-selection {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--el-text-color-secondary);
  gap: 12px;
}

.big-icon {
  font-size: 64px;
  opacity: 0.5;
}

.hint {
  font-size: 12px;
  opacity: 0.7;
}

.video-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: var(--el-fill-color-light);
  border-bottom: 1px solid var(--el-border-color);
}

.video-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.video-title {
  font-weight: 600;
}

.video-meta {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

/* 三相机并排布局 */
.video-grid {
  display: flex;
  gap: 8px;
  flex: 1;
  padding: 8px;
  min-height: 0;
}

.video-cell {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  overflow: hidden;
  background: #000;
}

.camera-label {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 6px 8px;
  background: var(--el-fill-color);
  font-size: 12px;
  font-weight: 500;
  color: var(--el-text-color-regular);
}

.video-player-small {
  flex: 1;
  width: 100%;
  min-height: 0;
  object-fit: contain;
  background: #000;
}

.qc-actions {
  display: flex;
  justify-content: center;
  gap: 24px;
  padding: 16px;
  background: var(--el-fill-color-light);
  border-top: 1px solid var(--el-border-color);
}

.qc-actions .el-button {
  width: 140px;
  height: 44px;
  font-size: 15px;
}

.qc-actions .el-button.active {
  box-shadow: 0 0 0 3px var(--el-color-primary-light-5);
}

/* Footer */
.dialog-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.stats {
  display: flex;
  gap: 20px;
}

.stat {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
}

.stat.passed {
  color: #67c23a;
}

.stat.failed {
  color: #f56c6c;
}

.stat.pending {
  color: #909399;
}

.actions {
  display: flex;
  gap: 8px;
}
</style>
