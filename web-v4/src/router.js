import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', name: 'dashboard', component: () => import('./views/Dashboard.vue'), meta: { title: '总览' } },
  { path: '/detect', name: 'detect', component: () => import('./views/Detect.vue'), meta: { title: '智能识别' } },
  { path: '/detect/:tab', name: 'detect-tab', component: () => import('./views/Detect.vue'), meta: { title: '智能识别' } },
  { path: '/chat', name: 'chat', component: () => import('./views/Chat.vue'), meta: { title: 'AI 问答' } },
  { path: '/records', name: 'records', component: () => import('./views/Records.vue'), meta: { title: '检测记录' } },
  { path: '/library', name: 'library', component: () => import('./views/Library.vue'), meta: { title: '病虫害图鉴' } },
  { path: '/pesticides', name: 'pesticides', component: () => import('./views/Pesticides.vue'), meta: { title: '药剂资料' } },
  { path: '/insights', name: 'insights', component: () => import('./views/Insights.vue'), meta: { title: '数据洞察' } },
  { path: '/kb', name: 'kb', component: () => import('./views/Knowledge.vue'), meta: { title: '知识库' } },
  { path: '/graph', name: 'graph', component: () => import('./views/Graph.vue'), meta: { title: '知识图谱' } },
  { path: '/train', redirect: '/models' },
  { path: '/models', name: 'models', component: () => import('./views/Models.vue'), meta: { title: '模型管理' } },
  { path: '/:pathMatch(.*)*', redirect: '/' }
]

export default createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 })
})
