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
        <el-table-column prop="episode_id" label="Episode" min-width="150" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="strategy" label="策略" width="100" />
        <el-table-column prop="frames" label="帧数" width="80">
          <template #default="{ row }">
            {{ row.frames || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column prop="completed_at" label="完成时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.completed_at) }}
          </template>
        </el-table-column>
        <el-table-column prop="error" label="错误信息" min-width="200">
          <template #default="{ row }">
            <span v-if="row.error" class="error-text">{{ row.error }}</span>
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
  max-width: 1200px;
}

.stats-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header span {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 500;
}

.stat-box {
  text-align: center;
  padding: 20px;
  border-radius: 8px;
  transition: transform 0.2s;
}

.stat-box:hover {
  transform: translateY(-2px);
}

.stat-box.pending {
  background: linear-gradient(135deg, #909399 0%, #c0c4cc 100%);
  color: white;
}

.stat-box.processing {
  background: linear-gradient(135deg, #e6a23c 0%, #f5c371 100%);
  color: white;
}

.stat-box.completed {
  background: linear-gradient(135deg, #67c23a 0%, #95d475 100%);
  color: white;
}

.stat-box.failed {
  background: linear-gradient(135deg, #f56c6c 0%, #f89898 100%);
  color: white;
}

.stat-number {
  font-size: 36px;
  font-weight: 700;
  line-height: 1.2;
}

.stat-label {
  font-size: 14px;
  opacity: 0.9;
  margin-top: 4px;
}

.episodes-card {
  margin-bottom: 20px;
}

.error-text {
  color: #f56c6c;
  font-size: 12px;
}

.pagination-wrapper {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
