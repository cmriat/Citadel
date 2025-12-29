import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

// Template types
export type TemplateType = 'download' | 'convert' | 'upload'

export interface Template {
  id: string
  name: string
  type: TemplateType
  config: Record<string, unknown>
  createdAt: string
  updatedAt: string
}

// Storage key
const STORAGE_KEY = 'citadel_templates'

// Generate unique ID
const generateId = (): string => {
  return `tpl_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
}

export const useTemplateStore = defineStore('templates', () => {
  // State
  const templates = ref<Template[]>([])
  const initialized = ref(false)

  // Getters
  const downloadTemplates = computed(() =>
    templates.value.filter(t => t.type === 'download')
  )

  const convertTemplates = computed(() =>
    templates.value.filter(t => t.type === 'convert')
  )

  const uploadTemplates = computed(() =>
    templates.value.filter(t => t.type === 'upload')
  )

  const getTemplatesByType = (type: TemplateType) => {
    return templates.value.filter(t => t.type === type)
  }

  // Actions
  const loadFromStorage = () => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY)
      if (saved) {
        templates.value = JSON.parse(saved)
        console.log('[TemplateStore] Loaded templates from storage:', templates.value.length)
      }
    } catch (e) {
      console.error('[TemplateStore] Failed to load templates:', e)
      templates.value = []
    }
    initialized.value = true
  }

  const saveToStorage = () => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(templates.value))
      console.log('[TemplateStore] Saved templates to storage')
    } catch (e) {
      console.error('[TemplateStore] Failed to save templates:', e)
    }
  }

  const createTemplate = (
    name: string,
    type: TemplateType,
    config: Record<string, unknown>
  ): Template => {
    const now = new Date().toISOString()
    const template: Template = {
      id: generateId(),
      name,
      type,
      config: { ...config },
      createdAt: now,
      updatedAt: now
    }
    templates.value.push(template)
    saveToStorage()
    console.log('[TemplateStore] Created template:', template.name)
    return template
  }

  const updateTemplate = (
    id: string,
    updates: { name?: string; config?: Record<string, unknown> }
  ): boolean => {
    const index = templates.value.findIndex(t => t.id === id)
    if (index === -1) return false

    const template = templates.value[index]
    if (updates.name) template.name = updates.name
    if (updates.config) template.config = { ...updates.config }
    template.updatedAt = new Date().toISOString()

    saveToStorage()
    console.log('[TemplateStore] Updated template:', template.name)
    return true
  }

  const deleteTemplate = (id: string): boolean => {
    const index = templates.value.findIndex(t => t.id === id)
    if (index === -1) return false

    const deleted = templates.value.splice(index, 1)[0]
    saveToStorage()
    console.log('[TemplateStore] Deleted template:', deleted.name)
    return true
  }

  const getTemplate = (id: string): Template | undefined => {
    return templates.value.find(t => t.id === id)
  }

  // Initialize on first access
  if (!initialized.value) {
    loadFromStorage()
  }

  return {
    // State
    templates,
    // Getters
    downloadTemplates,
    convertTemplates,
    uploadTemplates,
    getTemplatesByType,
    // Actions
    loadFromStorage,
    createTemplate,
    updateTemplate,
    deleteTemplate,
    getTemplate
  }
})
