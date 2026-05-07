import { createRouter, createWebHashHistory } from 'vue-router'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    {
      path: '/',
      name: 'Dashboard',
      component: () => import('@/views/Dashboard.vue'),
    },
    {
      path: '/alerts',
      name: 'AlertList',
      component: () => import('@/views/AlertList.vue'),
    },
    {
      path: '/alerts/:id',
      name: 'AlertDetail',
      component: () => import('@/views/AlertDetail.vue'),
    },
  ],
})

export default router
