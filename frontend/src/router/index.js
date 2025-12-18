import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    redirect: '/config'
  },
  {
    path: '/config',
    name: 'Config',
    component: () => import('../views/ConfigView.vue')
  },
  {
    path: '/scanner',
    name: 'Scanner',
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
