import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

declare module 'vue-router' {
  interface RouteMeta {
    requiresAuth?: boolean
    role?: 'admin' | 'merchant' | 'customer'
    public?: boolean
  }
}

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: () => import('@/views/LoginView.vue'), meta: { public: true } },
    {
      path: '/register',
      name: 'register',
      component: () => import('@/views/RegisterView.vue'),
      meta: { public: true },
    },
    {
      path: '/',
      name: 'chat',
      component: () => import('@/views/CustomerChatView.vue'),
      meta: { requiresAuth: true, role: 'customer' },
    },
    {
      path: '/history',
      name: 'history',
      component: () => import('@/views/ConversationHistoryView.vue'),
      meta: { requiresAuth: true, role: 'customer' },
    },
    {
      path: '/history/:conversationId',
      name: 'history-detail',
      component: () => import('@/views/ConversationResumeView.vue'),
      meta: { requiresAuth: true, role: 'customer' },
    },
    {
      path: '/profile',
      name: 'profile',
      component: () => import('@/views/ProfileView.vue'),
      meta: { requiresAuth: true, role: 'customer' },
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach((to) => {
  const auth = useAuthStore()

  if (to.meta.public && auth.isAuthenticated) {
    return { path: '/' }
  }
  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  if (to.meta.role && auth.user && auth.user.role !== to.meta.role) {
    // Only the customer role has a home today (merchant/admin surfaces land
    // in later stories) — send any other authenticated role back to login
    // rather than a raw 403.
    return { path: '/login' }
  }
  return true
})

export default router
