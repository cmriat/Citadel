<script setup lang="ts">
import Layout from '@/components/Layout.vue'
import { onErrorCaptured } from 'vue'

// 全局错误捕获
onErrorCaptured((err, instance, info) => {
  console.error('[Global Error Captured]:', err)
  console.error('Component:', instance)
  console.error('Error Info:', info)
  return false // 不阻止错误传播，但记录日志
})
</script>

<template>
  <Layout />
</template>

<style>
html.dark {
  color-scheme: dark;
}

/* 全局错误样式 */
.error-boundary {
  padding: 40px;
  text-align: center;
  color: #f56c6c;
}

.error-boundary h2 {
  margin-bottom: 20px;
  font-size: 24px;
}

.error-boundary p {
  margin-bottom: 10px;
  color: #909399;
}
</style>
