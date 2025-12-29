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
    path: '/pipeline',
    name: 'Pipeline',
    component: () => import('@/views/Pipeline.vue'),
    meta: { title: 'Pipeline', icon: 'mdi:pipe' }
  },
  // Legacy routes - redirect to pipeline with step parameter
  {
    path: '/download',
    redirect: '/pipeline?step=0'
  },
  {
    path: '/convert',
    redirect: '/pipeline?step=1'
  },
  {
    path: '/upload',
    redirect: '/pipeline?step=2'
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
