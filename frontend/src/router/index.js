import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    redirect: '/control'
  },
  {
    path: '/control',
    name: 'Control',
    component: () => import('../views/ScannerView.vue')
  },
  {
    path: '/monitor',
    name: 'Monitor',
    component: () => import('../views/MonitorView.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
