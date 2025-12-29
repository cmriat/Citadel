import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'Dashboard',
    component: () => import('@/views/Dashboard.vue'),
    meta: { title: 'Dashboard', icon: 'mdi:view-dashboard' }
  },
  {
    path: '/download',
    name: 'Download',
    component: () => import('@/views/Download.vue'),
    meta: { title: 'Download', icon: 'mdi:download' }
  },
  {
    path: '/convert',
    name: 'Convert',
    component: () => import('@/views/Convert.vue'),
    meta: { title: 'Convert', icon: 'mdi:swap-horizontal' }
  },
  {
    path: '/upload',
    name: 'Upload',
    component: () => import('@/views/Upload.vue'),
    meta: { title: 'Upload', icon: 'mdi:upload' }
  },
  {
    path: '/status',
    name: 'Status',
    component: () => import('@/views/Status.vue'),
    meta: { title: 'Status', icon: 'mdi:chart-line' }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior(to, from, savedPosition) {
    // 强制路由切换时滚动到顶部
    if (savedPosition) {
      return savedPosition
    } else {
      return { top: 0 }
    }
  }
})

// 路由守卫：强制组件重新渲染
router.beforeEach((to, from, next) => {
  console.log('[Router Guard] Navigating from', from.name, 'to', to.name)
  next()
})

export default router
