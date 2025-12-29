<template>
  <div class="template-selector">
    <el-dropdown
      v-if="templates.length > 0"
      trigger="click"
      @command="handleSelect"
    >
      <el-button type="primary" plain>
        <Icon icon="mdi:content-save-all" style="margin-right: 6px" />
        Templates
        <Icon icon="mdi:chevron-down" style="margin-left: 6px" />
      </el-button>
      <template #dropdown>
        <el-dropdown-menu>
          <el-dropdown-item
            v-for="tpl in templates"
            :key="tpl.id"
            :command="tpl.id"
          >
            <div class="template-item">
              <Icon icon="mdi:file-document-outline" />
              <span class="template-name">{{ tpl.name }}</span>
            </div>
          </el-dropdown-item>
          <el-dropdown-item divided command="__manage__">
            <div class="template-item manage">
              <Icon icon="mdi:cog" />
              <span>Manage Templates...</span>
            </div>
          </el-dropdown-item>
        </el-dropdown-menu>
      </template>
    </el-dropdown>

    <el-button
      @click="handleSave"
      type="success"
      plain
    >
      <Icon icon="mdi:content-save-plus" style="margin-right: 6px" />
      Save as Template
    </el-button>

    <!-- Save Dialog -->
    <el-dialog
      v-model="saveDialogVisible"
      title="Save Template"
      width="400px"
    >
      <el-form @submit.prevent="confirmSave">
        <el-form-item label="Template Name">
          <el-input
            v-model="newTemplateName"
            placeholder="Enter template name"
            @keyup.enter="confirmSave"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="saveDialogVisible = false">Cancel</el-button>
        <el-button type="primary" @click="confirmSave" :disabled="!newTemplateName.trim()">
          Save
        </el-button>
      </template>
    </el-dialog>

    <!-- Management Dialog -->
    <TemplateManager
      v-model:visible="manageDialogVisible"
      :type="type"
      @select="handleManagerSelect"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { Icon } from '@iconify/vue'
import { ElMessage } from 'element-plus'
import { useTemplateStore, type TemplateType } from '@/stores/templates'
import TemplateManager from './TemplateManager.vue'

const props = defineProps<{
  type: TemplateType
  currentConfig: Record<string, unknown>
}>()

const emit = defineEmits<{
  'load-template': [config: Record<string, unknown>]
}>()

const templateStore = useTemplateStore()

// Computed
const templates = computed(() => templateStore.getTemplatesByType(props.type))

// Dialog state
const saveDialogVisible = ref(false)
const manageDialogVisible = ref(false)
const newTemplateName = ref('')

// Handlers
const handleSelect = (command: string) => {
  if (command === '__manage__') {
    manageDialogVisible.value = true
    return
  }

  const template = templateStore.getTemplate(command)
  if (template) {
    emit('load-template', template.config)
    ElMessage.success(`Loaded template: ${template.name}`)
  }
}

const handleSave = () => {
  newTemplateName.value = ''
  saveDialogVisible.value = true
}

const confirmSave = () => {
  const name = newTemplateName.value.trim()
  if (!name) return

  templateStore.createTemplate(name, props.type, props.currentConfig)
  ElMessage.success(`Template saved: ${name}`)
  saveDialogVisible.value = false
}

const handleManagerSelect = (config: Record<string, unknown>) => {
  emit('load-template', config)
}
</script>

<style scoped>
.template-selector {
  display: flex;
  gap: 8px;
}

.template-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.template-name {
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.template-item.manage {
  color: #909399;
}
</style>
