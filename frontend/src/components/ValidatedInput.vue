<template>
  <div class="validated-input">
    <el-input
      v-model="inputValue"
      :placeholder="placeholder"
      :disabled="disabled"
      :clearable="clearable"
      @blur="handleBlur"
      @input="handleInput"
      @clear="handleClear"
    >
      <template #prefix v-if="prefixIcon">
        <Icon :icon="prefixIcon" />
      </template>
      <template #append v-if="$slots.append">
        <slot name="append" />
      </template>
      <template #suffix>
        <!-- 验证状态图标 -->
        <div class="validation-status">
          <Icon
            v-if="validationState === 'validating'"
            icon="mdi:loading"
            class="spinning text-blue-400"
          />
          <Icon
            v-else-if="validationState === 'valid'"
            icon="mdi:check-circle"
            class="text-green-500"
          />
          <Icon
            v-else-if="validationState === 'invalid'"
            icon="mdi:alert-circle"
            class="text-red-500"
          />
          <!-- 复制按钮 -->
          <el-tooltip v-if="copyable && inputValue" content="复制" placement="top">
            <Icon
              icon="mdi:content-copy"
              class="copy-btn cursor-pointer ml-1 hover:text-blue-400"
              @click="handleCopy"
            />
          </el-tooltip>
        </div>
      </template>
    </el-input>
    <!-- 验证消息 -->
    <transition name="fade">
      <div
        v-if="showMessage && validationMessage"
        :class="['validation-message', validationState === 'valid' ? 'success' : 'error']"
      >
        {{ validationMessage }}
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { Icon } from '@iconify/vue'
import { ElMessage } from 'element-plus'
import { validateLocalPath, validateBosPath } from '@/api/validation'

type ValidationType = 'local-path' | 'bos-path' | 'none'
type ValidationState = 'idle' | 'validating' | 'valid' | 'invalid'

interface Props {
  modelValue: string
  placeholder?: string
  validationType?: ValidationType
  validateOnBlur?: boolean
  validateOnInput?: boolean
  debounceMs?: number
  disabled?: boolean
  clearable?: boolean
  prefixIcon?: string
  copyable?: boolean
  showMessage?: boolean
  checkWritable?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  placeholder: '',
  validationType: 'none',
  validateOnBlur: true,
  validateOnInput: false,
  debounceMs: 500,
  disabled: false,
  clearable: true,
  prefixIcon: '',
  copyable: true,
  showMessage: true,
  checkWritable: false
})

const emit = defineEmits<{
  'update:modelValue': [value: string]
  'validation-change': [state: ValidationState, message: string]
}>()

// 状态
const inputValue = computed({
  get: () => props.modelValue,
  set: (value: string) => emit('update:modelValue', value)
})

const validationState = ref<ValidationState>('idle')
const validationMessage = ref('')
let debounceTimer: ReturnType<typeof setTimeout> | null = null

// 验证方法
const validate = async () => {
  if (!inputValue.value?.trim() || props.validationType === 'none') {
    validationState.value = 'idle'
    validationMessage.value = ''
    return
  }

  validationState.value = 'validating'
  validationMessage.value = ''

  try {
    if (props.validationType === 'local-path') {
      const result = await validateLocalPath(inputValue.value, props.checkWritable)
      validationState.value = result.valid ? 'valid' : 'invalid'
      validationMessage.value = result.message
    } else if (props.validationType === 'bos-path') {
      const result = await validateBosPath(inputValue.value)
      validationState.value = result.valid ? 'valid' : 'invalid'
      validationMessage.value = result.message
    }
  } catch (error) {
    validationState.value = 'invalid'
    validationMessage.value = '验证失败，请检查网络连接'
    console.error('Validation error:', error)
  }

  emit('validation-change', validationState.value, validationMessage.value)
}

// 防抖验证
const debouncedValidate = () => {
  if (debounceTimer) {
    clearTimeout(debounceTimer)
  }
  debounceTimer = setTimeout(validate, props.debounceMs)
}

// 事件处理
const handleBlur = () => {
  if (props.validateOnBlur) {
    validate()
  }
}

const handleInput = () => {
  if (props.validateOnInput) {
    debouncedValidate()
  }
}

const handleClear = () => {
  validationState.value = 'idle'
  validationMessage.value = ''
}

const handleCopy = async () => {
  if (!inputValue.value) return

  try {
    await navigator.clipboard.writeText(inputValue.value)
    ElMessage.success('已复制到剪贴板')
  } catch (error) {
    // Fallback for older browsers
    const textArea = document.createElement('textarea')
    textArea.value = inputValue.value
    document.body.appendChild(textArea)
    textArea.select()
    document.execCommand('copy')
    document.body.removeChild(textArea)
    ElMessage.success('已复制到剪贴板')
  }
}

// 监听值变化重置状态
watch(() => props.modelValue, (newVal, oldVal) => {
  if (newVal !== oldVal) {
    // 值变化时重置为 idle 状态
    if (validationState.value !== 'idle') {
      validationState.value = 'idle'
      validationMessage.value = ''
    }
  }
})

// 暴露方法供父组件调用
defineExpose({
  validate,
  validationState,
  validationMessage
})
</script>

<style scoped>
.validated-input {
  width: 100%;
}

.validation-status {
  display: flex;
  align-items: center;
  gap: 4px;
}

.validation-message {
  font-size: 12px;
  margin-top: 4px;
  padding: 2px 0;
}

.validation-message.success {
  color: #67c23a;
}

.validation-message.error {
  color: #f56c6c;
}

.spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.copy-btn {
  transition: color 0.2s;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
