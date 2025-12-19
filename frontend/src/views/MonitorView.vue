<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { getQueueStats, getEpisodes } from '../api'

// 队列统计
const stats = reactive({
  pending: 0,
  processing: 0,
  completed: 0,
  failed: 0
})

// Episodes 列表
const episodes = ref([])
const loading = ref(false)
const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

let refreshInterval = null

// 刷新统计
const refreshStats = async () => {
  try {
    const { data } = await getQueueStats()
    Object.assign(stats, data)
  } catch (error) {
    console.error('Failed to refresh stats:', error)
  }
}

// 刷新 Episodes
const refreshEpisodes = async () => {
  loading.value = true
  try {
    const offset = (pagination.page - 1) * pagination.pageSize
    const { data } = await getEpisodes(pagination.pageSize, offset)
    episodes.value = data.episodes || []
    pagination.total = data.total || 0
  } catch (error) {
    console.error('Failed to refresh episodes:', error)
  } finally {
    loading.value = false
  }
}

// 刷新所有数据
const refreshAll = async () => {
  await Promise.all([refreshStats(), refreshEpisodes()])
}

// 页码变化
const handlePageChange = (page) => {
  pagination.page = page
  refreshEpisodes()
}

// 格式化时间
const formatTime = (isoString) => {
  if (!isoString) return '-'
  const date = new Date(isoString)
  return date.toLocaleString('zh-CN')
}

// 格式化时间戳（Unix timestamp）
const formatTimestamp = (timestamp) => {
  if (!timestamp) return '-'
  // timestamp 可能是字符串或数字
  const ts = typeof timestamp === 'string' ? parseInt(timestamp) : timestamp
  if (isNaN(ts) || ts === 0) return '-'
  const date = new Date(ts * 1000)
  return date.toLocaleString('zh-CN')
}

// 状态标签类型
const getStatusType = (status) => {
  const types = {
    completed: 'success',
    processing: 'warning',
    pending: 'info',
    failed: 'danger'
  }
  return types[status] || 'info'
}

// 状态文字
const getStatusText = (status) => {
  const texts = {
    completed: '已完成',
    processing: '处理中',
    pending: '待处理',
    failed: '失败'
  }
  return texts[status] || status
}

onMounted(() => {
  refreshAll()
  // 每 5 秒刷新一次
  refreshInterval = setInterval(refreshAll, 5000)
})

onUnmounted(() => {
  if (refreshInterval) {
    clearInterval(refreshInterval)
  }
})
</script>

<template>
  <div class="monitor-view">
    <!-- 队列统计卡片 -->
    <el-card class="stats-card">
      <template #header>
        <div class="card-header">
          <span><el-icon><DataLine /></el-icon> 队列统计</span>
          <el-button text @click="refreshAll">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </div>
      </template>

      <el-row :gutter="20">
        <el-col :span="6">
          <div class="stat-box pending">
            <div class="stat-number">{{ stats.pending }}</div>
            <div class="stat-label">待处理</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-box processing">
            <div class="stat-number">{{ stats.processing }}</div>
            <div class="stat-label">处理中</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-box completed">
            <div class="stat-number">{{ stats.completed }}</div>
            <div class="stat-label">已完成</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-box failed">
            <div class="stat-number">{{ stats.failed }}</div>
            <div class="stat-label">失败</div>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <!-- Episodes 列表 -->
    <el-card class="episodes-card">
      <template #header>
        <div class="card-header">
          <span><el-icon><List /></el-icon> Episodes 列表</span>
          <el-tag type="info" effect="plain">
            共 {{ pagination.total }} 条
          </el-tag>
        </div>
      </template>

      <el-table
        :data="episodes"
        v-loading="loading"
        stripe
        style="width: 100%"
      >
        <el-table-column prop="episode_id" label="Episode" width="140" />
        <el-table-column prop="status" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="source_path" label="源路径" min-width="200">
          <template #default="{ row }">
            <span class="path-text" :title="row.source_path">{{ row.source_path || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="target_path" label="目标路径" min-width="200">
          <template #default="{ row }">
            <span class="path-text" :title="row.target_path">{{ row.target_path || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="timestamp" label="处理时间" width="160">
          <template #default="{ row }">
            {{ formatTimestamp(row.timestamp) }}
          </template>
        </el-table-column>
        <el-table-column prop="error" label="错误信息" min-width="150">
          <template #default="{ row }">
            <span v-if="row.error" class="error-text" :title="row.error">{{ row.error }}</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="pagination.page"
          :page-size="pagination.pageSize"
          :total="pagination.total"
          layout="prev, pager, next"
          @current-change="handlePageChange"
        />
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.monitor-view {
  width: 100%;
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.stats-card {
  margin-bottom: 16px;
  border-radius: 10px;
  border: none;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
  transition: all 0.3s ease;
  flex-shrink: 0;
}

.episodes-card {
  margin-bottom: 0;
  border-radius: 10px;
  border: none;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
  transition: all 0.3s ease;
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
}

.stats-card:hover,
.episodes-card:hover {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
}

.stats-card :deep(.el-card__header),
.episodes-card :deep(.el-card__header) {
  background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%);
  border-bottom: 1px solid #f0f2f5;
  padding: 12px 16px;
}

.stats-card :deep(.el-card__body) {
  padding: 16px;
}

.episodes-card :deep(.el-card__body) {
  padding: 16px;
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header span {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
  font-size: 14px;
  color: #303133;
}

.card-header span .el-icon {
  color: #667eea;
}

.stat-box {
  text-align: center;
  padding: 16px 12px;
  border-radius: 10px;
  transition: all 0.3s ease;
  cursor: default;
}

.stat-box:hover {
  transform: translateY(-3px);
}

.stat-box.pending {
  background: linear-gradient(135deg, #a8b5c8 0%, #c8d0dc 100%);
  color: white;
  box-shadow: 0 4px 10px rgba(144, 147, 153, 0.3);
}

.stat-box.processing {
  background: linear-gradient(135deg, #f0a020 0%, #f5c371 100%);
  color: white;
  box-shadow: 0 4px 10px rgba(230, 162, 60, 0.3);
}

.stat-box.completed {
  background: linear-gradient(135deg, #52c41a 0%, #95d475 100%);
  color: white;
  box-shadow: 0 4px 10px rgba(103, 194, 58, 0.3);
}

.stat-box.failed {
  background: linear-gradient(135deg, #ff4d4f 0%, #ff7875 100%);
  color: white;
  box-shadow: 0 4px 10px rgba(245, 108, 108, 0.3);
}

.stat-number {
  font-size: 32px;
  font-weight: 700;
  line-height: 1.2;
  text-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.stat-label {
  font-size: 12px;
  opacity: 0.95;
  margin-top: 4px;
  font-weight: 500;
  letter-spacing: 0.5px;
}

.episodes-card :deep(.el-table) {
  border-radius: 6px;
  font-size: 13px;
  flex: 1;
  overflow: auto;
}

.episodes-card :deep(.el-table__inner-wrapper) {
  height: 100% !important;
}

.episodes-card :deep(.el-scrollbar__wrap) {
  max-height: 100% !important;
}

.episodes-card :deep(.el-table th) {
  background: #f8f9fa !important;
  font-weight: 600;
  color: #606266;
  padding: 8px 0;
}

.episodes-card :deep(.el-table td) {
  padding: 6px 0;
}

.error-text {
  color: #f56c6c;
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  display: block;
}

.path-text {
  font-size: 12px;
  color: #606266;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  display: block;
  font-family: monospace;
}

.pagination-wrapper {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
  flex-shrink: 0;
}

/* 刷新按钮 */
.card-header .el-button {
  color: #667eea;
}

.card-header .el-button:hover {
  background: rgba(102, 126, 234, 0.1);
  border-radius: 6px;
}
</style>
