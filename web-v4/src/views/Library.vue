<script setup>
import { ref, onMounted } from 'vue'
import api from '../api/client'
import { toast } from '../composables/toast'
import Drawer from '../components/Drawer.vue'

const loading = ref(false)
const q = ref('')
const appliedQ = ref('')
const crop = ref('')
const crops = ref([])
const items = ref([])
const total = ref(0)
const page = ref(1)
const size = 24
const pages = ref(0)

const detail = ref(null)
const detailLoading = ref(false)
const showDetail = ref(false)

const levelTone = { 轻: 'green', 中: 'amber', 重: 'red' }
const catTone = { 病害: 'red', 虫害: 'amber', 健康: 'green' }

async function load() {
  loading.value = true
  try {
    const d = await api.libraryList(appliedQ.value, crop.value, page.value, size)
    items.value = d.items || []
    total.value = d.total || 0
    pages.value = d.pages || 0
    crops.value = d.crops || []
  } catch (e) { toast.error(e.message) } finally { loading.value = false }
}

function search() { appliedQ.value = q.value.trim(); page.value = 1; load() }
function pickCrop(c) { crop.value = c === crop.value ? '' : c; page.value = 1; load() }
function go(p) { if (p < 1 || p > pages.value) return; page.value = p; load(); window.scrollTo({ top: 0, behavior: 'smooth' }) }

async function open(item) {
  showDetail.value = true
  detailLoading.value = true
  detail.value = null
  try {
    detail.value = await api.libraryDetail(item.id)
  } catch (e) { toast.error(e.message); showDetail.value = false } finally { detailLoading.value = false }
}

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-head">
      <h1>病虫害图鉴</h1>
      <p>{{ total }} 条病虫害 · 覆盖 {{ crops.length }} 种作物 · 已隐藏健康叶片，每页 {{ size }} 条</p>
    </div>

    <div class="card card-pad">
      <div class="search-row">
        <input class="input" style="flex:1" v-model="q" placeholder="搜索病名 / 作物 / 症状，如「锈病」「叶片黄斑」…" @keydown.enter="search" />
        <button class="btn primary" @click="search">检索</button>
      </div>
      <div class="crop-chips">
        <button class="chip" :class="{ on: crop === '' }" @click="pickCrop('')">全部</button>
        <button v-for="c in crops" :key="c.name" class="chip" :class="{ on: crop === c.name }" @click="pickCrop(c.name)">
          {{ c.name }}<span class="chip-n">{{ c.count }}</span>
        </button>
      </div>
    </div>

    <div v-if="loading" class="loading-row" style="margin-top: 14px"><span class="spinner"></span>加载图鉴…</div>

    <div v-else class="lib-grid">
      <div v-for="it in items" :key="it.id" class="lib-card card" @click="open(it)">
        <div class="lib-top">
          <span class="badge" :class="catTone[it.category] || 'gray'">{{ it.category }}</span>
          <span class="badge" :class="levelTone[it.level] || 'gray'">{{ it.level }}</span>
        </div>
        <div class="lib-name">{{ it.name }}</div>
        <div class="lib-sub">{{ it.crop }} · {{ it.class_name }}</div>
        <div class="lib-brief">{{ it.brief || '暂无简介' }}</div>
        <div class="lib-more">查看详情 →</div>
      </div>
    </div>
    <div v-if="!loading && pages > 1" class="pager">
      <button class="btn ghost" :disabled="page <= 1" @click="go(page - 1)">上一页</button>
      <span class="pager-info">第 {{ page }} / {{ pages }} 页 · 共 {{ total }} 条</span>
      <button class="btn ghost" :disabled="page >= pages" @click="go(page + 1)">下一页</button>
    </div>
    <div v-if="!loading && !items.length" class="empty card" style="margin-top: 14px">
      <div class="icon">🔎</div>没有匹配的图鉴条目，换个关键词试试
    </div>

    <!-- 详情抽屉 -->
    <Drawer :show="showDetail" :title="detail ? `${detail.crop} · ${detail.name}` : '图鉴详情'" width="600px" @close="showDetail = false">
      <div v-if="detailLoading" class="loading-row"><span class="spinner"></span>加载详情…</div>
      <template v-else-if="detail">
        <div class="d-head">
          <span class="badge" :class="catTone[detail.category] || 'gray'">{{ detail.category }}</span>
          <span class="badge" :class="levelTone[detail.level] || 'gray'">为害程度：{{ detail.level }}</span>
          <span class="badge outline">{{ detail.class_name }}</span>
        </div>

        <section class="sec">
          <h3>概述</h3>
          <p>{{ detail.overview || '暂无' }}</p>
        </section>
        <section class="sec">
          <h3>为害症状</h3>
          <p>{{ detail.symptom || '暂无' }}</p>
        </section>
        <section class="sec">
          <h3>防治方法</h3>
          <p>{{ detail.control || '暂无' }}</p>
        </section>
        <section class="sec" v-if="detail.regulation">
          <h3>发生规律 / 法规</h3>
          <p>{{ detail.regulation }}</p>
        </section>

        <section class="sec" v-if="detail.neighbors?.length">
          <h3>图谱关联事实</h3>
          <div class="facts">
            <div v-for="(n, i) in detail.neighbors" :key="i" class="fact">{{ n }}</div>
          </div>
        </section>
      </template>
    </Drawer>
  </div>
</template>

<style scoped>
.search-row { display: flex; gap: 10px; }
.crop-chips { display: flex; flex-wrap: wrap; gap: 7px; margin-top: 13px; }
.chip {
  border: 1px solid var(--line); background: #fff; border-radius: 999px;
  padding: 4.5px 15px; font-size: 12.5px; cursor: pointer; color: var(--text-2); transition: all .14s;
}
.chip:hover { border-color: var(--indigo-400); color: var(--indigo-600); }
.chip.on { background: var(--indigo-600); border-color: var(--indigo-600); color: #fff; }

.lib-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 14px; margin-top: 14px; }
.lib-card { padding: 16px 18px; cursor: pointer; transition: all .16s; display: flex; flex-direction: column; }
.lib-card:hover { transform: translateY(-3px); box-shadow: var(--shadow-lg); border-color: var(--indigo-300); }
.lib-top { display: flex; justify-content: space-between; margin-bottom: 10px; }
.lib-name { font-size: 16.5px; font-weight: 700; }
.lib-sub { font-size: 11.5px; color: var(--text-3); margin: 3px 0 9px; }
.lib-brief {
  font-size: 12.5px; color: var(--text-2); line-height: 1.65; flex: 1;
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;
}
.lib-more { font-size: 12px; color: var(--indigo-600); margin-top: 11px; }

.d-head { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 6px; }
.sec { margin-top: 18px; }
.sec h3 { font-size: 14px; margin-bottom: 8px; padding-left: 9px; border-left: 3px solid var(--indigo-500); }
.sec p { font-size: 13.2px; line-height: 1.85; color: var(--text-2); white-space: pre-wrap; }
.facts { display: flex; flex-direction: column; gap: 6px; }
.fact { font-size: 12.5px; background: var(--indigo-50); border: 1px solid var(--indigo-100); color: var(--indigo-800); border-radius: 8px; padding: 7px 11px; }
.pager { display: flex; align-items: center; justify-content: center; gap: 16px; margin: 22px 0 6px; }
.pager-info { color: #8a7f74; font-size: 13px; }
.chip-n { margin-left: 4px; font-size: 11px; opacity: 0.6; }
</style>
