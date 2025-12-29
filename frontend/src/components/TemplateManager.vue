<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    title="Manage Templates"
    width="600px"
  >
    <div v-if="templates.length === 0" class="empty-state">
      <Icon icon="mdi:file-document-outline" class="empty-icon" />
      <p>No templates saved yet</p>
      <span class="empty-hint">Save your current configuration as a template to quickly reuse it later.</span>
    </div>

    <div v-else class="template-list">
      <div
        v-for="tpl in templates"
        :key="tpl.id"
        class="template-card"
      >
        <div class="template-header">
          <div class="template-info">
            <Icon icon="mdi:file-document" class="template-icon" />
            <div class="template-details">
              <span class="template-name" v-if="editingId !== tpl.id">{{ tpl.name }}</span>
              <el-input
                v-else
                v-model="editName"
                size="small"
                @keyup.enter="confirmEdit(tpl.id)"
                @blur="confirmEdit(tpl.id)"
              />
              <span class="template-meta">
                Updated {{ formatTime(tpl.updatedAt) }}
              </span>
            </div>
          </div>
          <div class="template-actions">
            <el-button
              type="primary"
              size="small"
              @click="handleLoad(tpl)"
            >
              <Icon icon="mdi:upload" />
              Load
            </el-button>
            <el-button
              size="small"
              @click="startEdit(tpl)"
              :disabled="editingId === tpl.id"
            >
              <Icon icon="mdi:pencil" />
            </el-button>
            <el-popconfirm
              title="Delete this template?"
              confirm-button-text="Delete"
              cancel-button-text="Cancel"
              @confirm="handleDelete(tpl.id)"
            >
              <template #reference>
                <el-button
                  type="danger"
                  size="small"
                >
                  <Icon icon="mdi:delete" />
                </el-button>
              </template>
            </el-popconfirm>
          </div>
        </div>
        <div class="template-preview">
          <pre>{{ JSON.stringify(tpl.config, null, 2) }}</pre>
        </div>
      </div>
    </div>

    <template #footer>
      <el-button @click="$emit('update:visible', false)">Close</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { Icon } from '@iconify/vue'
import { ElMessage } from 'element-plus'
import { useTemplateStore, type TemplateType, type Template } from '@/stores/templates'

const props = defineProps<{
  visible: boolean
  type: TemplateType
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  select: [config: Record<string, unknown>]
}>()

const templateStore = useTemplateStore()

// Computed
const templates = computed(() => templateStore.getTemplatesByType(props.type))

// Edit state
const editingId = ref<string | null>(null)
const editName = ref('')

// Handlers
const handleLoad = (template: Template) => {
  emit('select', template.config)
  emit('update:visible', false)
  ElMessage.success(`Loaded template: ${template.name}`)
}

const startEdit = (template: Template) => {
  editingId.value = template.id
  editName.value = template.name
}

const confirmEdit = (id: string) => {
  if (editingId.value !== id) return

  const name = editName.value.trim()
  if (name) {
    templateStore.updateTemplate(id, { name })
    ElMessage.success('Template renamed')
  }
  editingId.value = null
}

const handleDelete = (id: string) => {
  templateStore.deleteTemplate(id)
  ElMessage.success('Template deleted')
}

// Helpers
const formatTime = (isoString: string): string => {
  const date = new Date(isoString)
  const now = new Date()
  const diff = now.getTime() - date.getTime()

  // Less than 1 minute
  if (diff < 60000) return 'just now'

  // Less than 1 hour
  if (diff < 3600000) {
    const mins = Math.floor(diff / 60000)
    return `${mins} min${mins > 1 ? 's' : ''} ago`
  }

  // Less than 24 hours
  if (diff < 86400000) {
    const hours = Math.floor(diff / 3600000)
    return `${hours} hour${hours > 1 ? 's' : ''} ago`
  }

  // Default: show date
  return date.toLocaleDateString('zh-CN')
}
</script>

<style scoped>
.empty-state {
  text-align: center;
  padding: 40px;
  color: #909399;
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 16px;
  opacity: 0.5;
}

.empty-hint {
  font-size: 13px;
  color: #6a6a8a;
}

.template-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-height: 400px;
  overflow-y: auto;
}

.template-card {
  border: 1px solid #363662;
  border-radius: 8px;
  padding: 16px;
  background-color: #1e1e3a;
}

.template-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
}

.template-info {
  display: flex;
  gap: 12px;
}

.template-icon {
  font-size: 24px;
  color: #409eff;
}

.template-details {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.template-name {
  font-weight: 600;
  color: #e0e0e0;
}

.template-meta {
  font-size: 12px;
  color: #6a6a8a;
}

.template-actions {
  display: flex;
  gap: 8px;
}

.template-preview {
  background-color: #141428;
  border-radius: 6px;
  padding: 12px;
  max-height: 120px;
  overflow: auto;
}

.template-preview pre {
  margin: 0;
  font-size: 11px;
  color: #a0a0c0;
  white-space: pre-wrap;
  word-break: break-all;
}

/* Light theme adjustments */
:global(.light) .template-card {
  border-color: #e4e7ed;
  background-color: #f5f7fa;
}

:global(.light) .template-name {
  color: #303133;
}

:global(.light) .template-preview {
  background-color: #ffffff;
}

:global(.light) .template-preview pre {
  color: #606266;
}
</style>
