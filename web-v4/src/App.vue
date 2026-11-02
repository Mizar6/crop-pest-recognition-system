<script setup>
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRoute } from 'vue-router'
import { api } from './api/client'
import { toastState } from './composables/toast'
import { useModelInfo } from './composables/modelInfo'

const route = useRoute()

const nav = [
  { path: '/', title: '总览' },
  { path: '/detect', title: '智能识别' },
  { path: '/chat', title: 'AI 问答' },
  { path: '/records', title: '检测记录' },
  { path: '/library', title: '图鉴' },
  { path: '/pesticides', title: '药剂' },
  { path: '/insights', title: '数据洞察' },
  { path: '/kb', title: '知识库' },
  { path: '/graph', title: '知识图谱' },
  { path: '/models', title: '模型' }
]

const { info: modelInfo, label: modelLabel, refresh: refreshModel } = useModelInfo()
const health = ref('checking')
let timer = null

async function ping() {
  try {
    await api.health()
    health.value = 'ok'
  } catch {
    health.value = 'down'
  }
}

onMounted(async () => {
  ping()
  timer = setInterval(ping, 15000)
  refreshModel()
})
onBeforeUnmount(() => clearInterval(timer))
watch(() => route.meta.title, (t) => { if (t) document.title = `${t} · 禾鉴` }, { immediate: true })
</script>

<template>
  <div class="shell">
    <header class="topbar">
      <div class="bar-inner">
        <RouterLink to="/" class="brand">
          <div class="brand-mark">禾</div>
          <div class="brand-text">
            <b>禾鉴</b>
            <span>叶片病虫害智能识别</span>
          </div>
        </RouterLink>

        <nav class="nav">
          <RouterLink v-for="n in nav" :key="n.path" :to="n.path" class="nav-item" :class="{ active: route.path === n.path }">
            {{ n.title }}
          </RouterLink>
        </nav>

        <div class="bar-right">
          <div class="health" :class="health">
            <i></i>
            <span>{{ health === 'ok' ? '在线 8001' : health === 'down' ? '后端离线' : '检测中' }}</span>
          </div>
          <div class="model-chip" v-if="modelInfo" :title="modelLabel()">{{ modelLabel() }}</div>
        </div>
      </div>
    </header>

    <main class="main">
      <RouterView />
    </main>

    <div class="toast-host">
      <transition-group name="pop">
        <div v-for="t in toastState.list" :key="t.id" class="toast" :class="t.type">
          <span class="dot"></span>{{ t.msg }}
        </div>
      </transition-group>
    </div>
  </div>
</template>

<style scoped>
.shell { min-height: 100vh; display: flex; flex-direction: column; }

.topbar {
  position: sticky; top: 0; z-index: 900;
  background: linear-gradient(180deg, var(--ink-bar), var(--ink-bar-2));
  border-bottom: 1px solid rgba(255, 255, 255, .06);
  box-shadow: 0 8px 24px -12px rgba(20, 22, 28, .5);
}
.bar-inner {
  max-width: 1440px; margin: 0 auto; padding: 0 24px;
  display: flex; align-items: center; gap: 22px; height: 58px;
}
.brand { display: flex; align-items: center; gap: 10px; flex-shrink: 0; }
.brand-mark {
  width: 34px; height: 34px; border-radius: 10px;
  background: linear-gradient(135deg, var(--indigo-400), var(--indigo-700));
  color: #fff; font-size: 17px; font-weight: 700;
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 4px 12px -2px rgba(90, 95, 216, .6);
}
.brand-text b { display: block; font-size: 15.5px; color: #fff; letter-spacing: 2.5px; line-height: 1.15; }
.brand-text span { font-size: 10px; color: #8b8e9c; letter-spacing: .5px; }

.nav { display: flex; align-items: center; gap: 2px; flex: 1; overflow-x: auto; scrollbar-width: none; }
.nav::-webkit-scrollbar { display: none; }
.nav-item {
  padding: 6.5px 13px; border-radius: 9px; color: #a3a6b3;
  font-size: 13px; white-space: nowrap; transition: all .15s;
}
.nav-item:hover { color: #fff; background: rgba(255, 255, 255, .08); }
.nav-item.active {
  background: linear-gradient(135deg, var(--indigo-500), var(--indigo-600));
  color: #fff; font-weight: 500;
  box-shadow: 0 3px 10px -2px rgba(90, 95, 216, .7);
}

.bar-right { display: flex; align-items: center; gap: 12px; flex-shrink: 0; }
.health { display: flex; align-items: center; gap: 6px; font-size: 11.5px; color: #8b8e9c; }
.health i { width: 7px; height: 7px; border-radius: 50%; background: #666; }
.health.ok i { background: #34d399; box-shadow: 0 0 8px #34d399; }
.health.down i { background: #f87171; box-shadow: 0 0 8px #f87171; }
.model-chip {
  font-size: 10.5px; color: #a3a6b3; background: rgba(255, 255, 255, .06);
  border: 1px solid rgba(255, 255, 255, .1); border-radius: 999px; padding: 4px 11px;
  max-width: 180px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}

.main { flex: 1; }
@media (max-width: 980px) {
  .bar-inner { gap: 12px; }
  .model-chip { display: none; }
  .brand-text span { display: none; }
}
</style>
