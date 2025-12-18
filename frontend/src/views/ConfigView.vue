<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getConfig, updateConfig, testBosConnection } from '../api'

const loading = ref(false)
const testLoading = ref(false)
const testResult = ref(null)

const form = reactive({
  bos: {
    endpoint: 'https://s3.bj.bcebos.com',
    bucket: 'srgdata',
    region: 'bj',
    access_key: '',
    secret_key: ''
  },
  paths: {
    raw_data: '',
    converted: '',
    task_name: ''
  },
  conversion: {
    strategy: 'nearest',
    tolerance_ms: 20,
    chunk_size: 10,
    fps: 30
  },
  scanner: {
    interval: 120,
    stable_time: 10,
    min_file_count: 1
  },
  redis: {
    host: 'localhost',
    port: 6379,
    db: 0,
    password: null
  }
})

const showSecretKey = ref(false)
const showAccessKey = ref(false)

const strategyOptions = [
  { label: 'Nearest (最近邻)', value: 'nearest' },
  { label: 'Chunking (动作分块)', value: 'chunking' },
  { label: 'Window (时间窗口)', value: 'window' }
]

const loadConfig = async () => {
  loading.value = true
  try {
    const { data } = await getConfig()
    Object.assign(form, data)
  } catch (error) {
    console.error('Failed to load config:', error)
    ElMessage.error('加载配置失败')
  } finally {
    loading.value = false
  }
}

const saveConfig = async () => {
  loading.value = true
  try {
    const { data } = await updateConfig(form)
    if (data.success) {
      ElMessage.success(data.message || '配置已保存')
    } else {
      ElMessage.error(data.message || '保存失败')
    }
  } catch (error) {
    console.error('Failed to save config:', error)
    ElMessage.error('保存配置失败')
  } finally {
    loading.value = false
  }
}

const testBos = async () => {
  testLoading.value = true
  testResult.value = null
  try {
    // 使用当前表单中的配置进行测试
    const { data } = await testBosConnection(form)
    testResult.value = data
    if (data.success) {
      ElMessage.success(data.message)
    } else {
      ElMessage.warning(data.message)
    }
  } catch (error) {
    console.error('Failed to test BOS:', error)
    ElMessage.error('测试连接失败')
    testResult.value = { success: false, message: '测试连接失败' }
  } finally {
    testLoading.value = false
  }
}

const resetForm = () => {
  loadConfig()
}

onMounted(() => {
  loadConfig()
})
</script>

<template>
  <div class="config-view" v-loading="loading">
    <el-form :model="form" label-width="120px" label-position="right">
      <!-- BOS 连接配置 -->
      <el-card class="config-card">
        <template #header>
          <div class="card-header">
            <span><el-icon><Connection /></el-icon> BOS 连接配置</span>
            <el-button
              type="primary"
              :loading="testLoading"
              @click="testBos"
            >
              测试连接
            </el-button>
          </div>
        </template>

        <el-form-item label="Endpoint">
          <el-input v-model="form.bos.endpoint" placeholder="https://s3.bj.bcebos.com" />
        </el-form-item>

        <el-form-item label="Bucket">
          <el-input v-model="form.bos.bucket" placeholder="srgdata" />
        </el-form-item>

        <el-form-item label="Region">
          <el-input v-model="form.bos.region" placeholder="bj" />
        </el-form-item>

        <el-form-item label="Access Key">
          <el-input
            v-model="form.bos.access_key"
            :type="showAccessKey ? 'text' : 'password'"
            placeholder="输入 Access Key"
          >
            <template #suffix>
              <el-icon class="cursor-pointer" @click="showAccessKey = !showAccessKey">
                <View v-if="showAccessKey" />
                <Hide v-else />
              </el-icon>
            </template>
          </el-input>
        </el-form-item>

        <el-form-item label="Secret Key">
          <el-input
            v-model="form.bos.secret_key"
            :type="showSecretKey ? 'text' : 'password'"
            placeholder="输入 Secret Key"
          >
            <template #suffix>
              <el-icon class="cursor-pointer" @click="showSecretKey = !showSecretKey">
                <View v-if="showSecretKey" />
                <Hide v-else />
              </el-icon>
            </template>
          </el-input>
        </el-form-item>

        <!-- 测试结果 -->
        <el-alert
          v-if="testResult"
          :title="testResult.message"
          :type="testResult.success ? 'success' : 'warning'"
          show-icon
          :closable="false"
          style="margin-top: 10px"
        >
          <template v-if="testResult.success" #default>
            <div style="font-size: 12px; color: #666; margin-top: 5px">
              <span>Bucket: {{ testResult.bucket_exists ? '✓' : '✗' }}</span>
              <span style="margin-left: 15px">Raw Data: {{ testResult.raw_data_exists ? '✓' : '✗' }}</span>
              <span style="margin-left: 15px">Converted: {{ testResult.converted_exists ? '✓' : '✗' }}</span>
            </div>
            <div v-if="!testResult.raw_data_exists" style="font-size: 12px; color: #e6a23c; margin-top: 8px">
              请在下方「数据路径配置」中填写 Raw Data 路径，然后点击底部「保存配置」
            </div>
            <div v-else style="font-size: 12px; color: #67c23a; margin-top: 8px">
              配置完成！请点击底部「保存配置」，然后前往「扫描」页面启动服务
            </div>
          </template>
        </el-alert>
      </el-card>

      <!-- 数据路径配置 -->
      <el-card class="config-card">
        <template #header>
          <span><el-icon><FolderOpened /></el-icon> 数据路径配置</span>
        </template>

        <el-form-item label="Raw Data">
          <el-input
            v-model="form.paths.raw_data"
            placeholder="robot/raw_data/.../fold_laundry/"
          />
        </el-form-item>

        <el-form-item label="Converted">
          <el-input
            v-model="form.paths.converted"
            placeholder="robot/raw_data/.../converted/"
          />
        </el-form-item>

        <el-form-item label="Task Name">
          <el-input
            v-model="form.paths.task_name"
            placeholder="fold_laundry"
          />
        </el-form-item>
      </el-card>

      <!-- 转换策略配置 -->
      <el-card class="config-card">
        <template #header>
          <span><el-icon><Operation /></el-icon> 转换策略配置</span>
        </template>

        <el-form-item label="Strategy">
          <el-select v-model="form.conversion.strategy" style="width: 100%">
            <el-option
              v-for="opt in strategyOptions"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="Tolerance">
          <el-input-number
            v-model="form.conversion.tolerance_ms"
            :min="1"
            :max="1000"
          />
          <span style="margin-left: 8px; color: #909399">ms</span>
        </el-form-item>

        <el-form-item label="Chunk Size" v-if="form.conversion.strategy === 'chunking'">
          <el-input-number
            v-model="form.conversion.chunk_size"
            :min="1"
            :max="100"
          />
        </el-form-item>

        <el-form-item label="FPS">
          <el-input-number
            v-model="form.conversion.fps"
            :min="1"
            :max="120"
          />
        </el-form-item>
      </el-card>

      <!-- 扫描配置 -->
      <el-card class="config-card">
        <template #header>
          <span><el-icon><Timer /></el-icon> 扫描配置</span>
        </template>

        <el-form-item label="Scan Interval">
          <el-input-number
            v-model="form.scanner.interval"
            :min="10"
            :max="3600"
          />
          <span style="margin-left: 8px; color: #909399">秒</span>
        </el-form-item>

        <el-form-item label="Stable Time">
          <el-input-number
            v-model="form.scanner.stable_time"
            :min="0"
            :max="600"
          />
          <span style="margin-left: 8px; color: #909399">秒</span>
        </el-form-item>

        <el-form-item label="Min Files">
          <el-input-number
            v-model="form.scanner.min_file_count"
            :min="1"
            :max="100"
          />
        </el-form-item>
      </el-card>

      <!-- Redis 配置 -->
      <el-card class="config-card">
        <template #header>
          <span><el-icon><Coin /></el-icon> Redis 配置</span>
        </template>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="Host">
              <el-input v-model="form.redis.host" placeholder="localhost" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="Port">
              <el-input-number v-model="form.redis.port" :min="1" :max="65535" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="DB">
              <el-input-number v-model="form.redis.db" :min="0" :max="15" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="Password">
              <el-input
                v-model="form.redis.password"
                type="password"
                placeholder="可选"
                show-password
              />
            </el-form-item>
          </el-col>
        </el-row>
      </el-card>

      <!-- 操作按钮 -->
      <div class="form-actions">
        <el-button @click="resetForm">重置</el-button>
        <el-button type="primary" @click="saveConfig">保存配置</el-button>
      </div>
    </el-form>
  </div>
</template>

<style scoped>
.config-view {
  max-width: 800px;
}

.config-card {
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

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 20px;
}

.cursor-pointer {
  cursor: pointer;
}
</style>
