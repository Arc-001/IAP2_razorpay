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
    {
      path: '/orders',
      name: 'orders',
      component: () => import('@/views/OrdersView.vue'),
      meta: { requiresAuth: true, role: 'customer' },
    },
    {
      path: '/merchant/products',
      name: 'merchant-products',
      component: () => import('@/views/MerchantProductsView.vue'),
      meta: { requiresAuth: true, role: 'merchant' },
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

/** Where an authenticated user lands when redirected away from a route that
 * isn't theirs (a role mismatch, or a public-only page like /login). Admin
 * has no home yet (SCRUM-45) — falls back to /login rather than a 404. */
function roleHome(role: 'admin' | 'merchant' | 'customer' | undefined) {
  if (role === 'merchant') return { path: '/merchant/products' }
  if (role === 'customer') return { path: '/' }
  return { path: '/login' }
}

router.beforeEach((to) => {
  const auth = useAuthStore()

  if (to.meta.public && auth.isAuthenticated) {
    return roleHome(auth.user?.role)
  }
  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  if (to.meta.role && auth.user && auth.user.role !== to.meta.role) {
    return roleHome(auth.user.role)
  }
  return true
})

export default router
