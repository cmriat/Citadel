<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Icon } from '@iconify/vue'
import { getHealth, getStats } from '@/api/tasks'
import type { HealthCheck, Stats } from '@/api/index'
import { useThemeStore } from '@/stores/theme'
import StatCard from '@/components/StatCard.vue'

const themeStore = useThemeStore()
const health = ref<HealthCheck | null>(null)
const stats = ref<Stats | null>(null)
const loading = ref(false)

const fetchData = async () => {
  loading.value = true
  try {
    const [healthData, statsData] = await Promise.all([
      getHealth(),
      getStats()
    ])
    health.value = healthData
    stats.value = statsData
  } catch (e) {
    console.error('Failed to fetch status:', e)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchData()
})
</script>

<template>
  <div class="status-page" :class="themeStore.theme">
    <!-- Health Check -->
    <div class="section">
      <h2 class="section-title">
        <Icon icon="mdi:heart-pulse" />
        System Health
      </h2>
      <div class="health-grid" v-if="health">
        <div class="health-card" :class="{ ok: health.status === 'healthy' }">
          <div class="health-icon">
            <Icon :icon="health.status === 'healthy' ? 'mdi:check-circle' : 'mdi:alert-circle'" />
          </div>
          <div class="health-info">
            <div class="health-label">Overall Status</div>
            <div class="health-value">{{ health.status }}</div>
          </div>
        </div>

        <div class="health-card" :class="{ ok: health.checks.database }">
          <div class="health-icon">
            <Icon icon="mdi:database" />
          </div>
          <div class="health-info">
            <div class="health-label">Database</div>
            <div class="health-value">{{ health.checks.database ? 'Connected' : 'Error' }}</div>
          </div>
        </div>

        <div class="health-card" :class="{ ok: health.checks.mc_tool }">
          <div class="health-icon">
            <Icon icon="mdi:console" />
          </div>
          <div class="health-info">
            <div class="health-label">MC Tool</div>
            <div class="health-value">{{ health.checks.mc_tool ? 'Available' : 'Not Found' }}</div>
          </div>
        </div>

        <div class="health-card" :class="{ ok: health.checks.bos_connection }">
          <div class="health-icon">
            <Icon icon="mdi:cloud" />
          </div>
          <div class="health-info">
            <div class="health-label">BOS Connection</div>
            <div class="health-value">{{ health.checks.bos_connection ? 'Connected' : 'Disconnected' }}</div>
          </div>
        </div>
      </div>
      <div v-else class="loading-placeholder">
        <Icon icon="mdi:loading" class="spinning" />
        Loading health status...
      </div>
    </div>

    <!-- Task Statistics -->
    <div class="section">
      <h2 class="section-title">
        <Icon icon="mdi:chart-bar" />
        Task Statistics
      </h2>
      <div class="stats-grid" v-if="stats">
        <StatCard
          title="Total Tasks"
          :value="stats.tasks.total"
          icon="mdi:format-list-numbered"
          color="primary"
        />
        <StatCard
          title="Downloads"
          :value="stats.by_type.download"
          icon="mdi:download"
          color="info"
        />
        <StatCard
          title="Converts"
          :value="stats.by_type.convert"
          icon="mdi:swap-horizontal"
          color="warning"
        />
        <StatCard
          title="Uploads"
          :value="stats.by_type.upload ?? 0"
          icon="mdi:upload"
          color="success"
        />
      </div>

      <div class="status-breakdown" v-if="stats">
        <h3 class="breakdown-title">Status Breakdown</h3>
        <div class="breakdown-bars">
          <div class="bar-item">
            <div class="bar-label">
              <span>Completed</span>
              <span>{{ stats.tasks.completed }}</span>
            </div>
            <el-progress
              :percentage="stats.tasks.total ? (stats.tasks.completed / stats.tasks.total * 100) : 0"
              status="success"
              :stroke-width="12"
            />
          </div>
          <div class="bar-item">
            <div class="bar-label">
              <span>Running</span>
              <span>{{ stats.tasks.running }}</span>
            </div>
            <el-progress
              :percentage="stats.tasks.total ? (stats.tasks.running / stats.tasks.total * 100) : 0"
              :stroke-width="12"
            />
          </div>
          <div class="bar-item">
            <div class="bar-label">
              <span>Pending</span>
              <span>{{ stats.tasks.pending }}</span>
            </div>
            <el-progress
              :percentage="stats.tasks.total ? (stats.tasks.pending / stats.tasks.total * 100) : 0"
              status="warning"
              :stroke-width="12"
            />
          </div>
          <div class="bar-item">
            <div class="bar-label">
              <span>Failed</span>
              <span>{{ stats.tasks.failed }}</span>
            </div>
            <el-progress
              :percentage="stats.tasks.total ? (stats.tasks.failed / stats.tasks.total * 100) : 0"
              status="exception"
              :stroke-width="12"
            />
          </div>
        </div>
      </div>
    </div>

    <!-- Refresh Button -->
    <div class="actions">
      <el-button @click="fetchData" :loading="loading">
        <Icon icon="mdi:refresh" style="margin-right: 6px" />
        Refresh
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.status-page {
  max-width: 1000px;
  margin: 0 auto;
}

.section {
  margin-bottom: 32px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 18px;
  font-weight: 600;
  margin: 0 0 20px 0;
}

/* Dark theme */
.status-page.dark .section-title {
  color: #fff;
}

.status-page.dark .health-card {
  background-color: #1a1a2e;
}

.status-page.dark .health-label {
  color: #6a6a8a;
}

.status-page.dark .health-value {
  color: #fff;
}

.status-page.dark .status-breakdown {
  background-color: #1a1a2e;
  border-color: #2a2a4e;
}

.status-page.dark .breakdown-title {
  color: #a0a0c0;
}

.status-page.dark .bar-label {
  color: #a0a0c0;
}

.status-page.dark .loading-placeholder {
  color: #6a6a8a;
}

/* Light theme */
.status-page.light .section-title {
  color: #303133;
}

.status-page.light .health-card {
  background-color: #ffffff;
}

.status-page.light .health-label {
  color: #909399;
}

.status-page.light .health-value {
  color: #303133;
}

.status-page.light .status-breakdown {
  background-color: #ffffff;
  border-color: #e4e7ed;
}

.status-page.light .breakdown-title {
  color: #606266;
}

.status-page.light .bar-label {
  color: #606266;
}

.status-page.light .loading-placeholder {
  color: #909399;
}

/* Common styles */
.health-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

@media (max-width: 900px) {
  .health-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

.health-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  border-radius: 12px;
  border: 1px solid #f56c6c40;
  transition: all 0.3s ease;
}

.health-card.ok {
  border-color: #67c23a40;
}

.health-icon {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  font-size: 20px;
  background-color: #f56c6c20;
  color: #f56c6c;
}

.health-card.ok .health-icon {
  background-color: #67c23a20;
  color: #67c23a;
}

.health-label {
  font-size: 12px;
}

.health-value {
  font-size: 14px;
  font-weight: 600;
  text-transform: capitalize;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

@media (max-width: 900px) {
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

.status-breakdown {
  border-radius: 12px;
  padding: 24px;
  border: 1px solid;
  transition: all 0.3s ease;
}

.breakdown-title {
  font-size: 14px;
  font-weight: 600;
  margin: 0 0 16px 0;
}

.breakdown-bars {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.bar-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.bar-label {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
}

.loading-placeholder {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 40px;
  justify-content: center;
}

.spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.actions {
  margin-top: 24px;
}
</style>
