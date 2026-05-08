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
    {
      path: '/portfolio',
      name: 'Portfolio',
      component: () => import('@/views/Portfolio.vue'),
    },
    {
      path: '/notifications',
      name: 'Notifications',
      component: () => import('@/views/Notifications.vue'),
    },
  ],
})

export default router
