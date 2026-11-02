<script setup>
import { ref, onMounted } from 'vue'
import api from '../api/client'
import { toast } from '../composables/toast'
import Modal from '../components/Modal.vue'

const loading = ref(false)
const q = ref('')
const appliedQ = ref('')
const items = ref([])
const total = ref(0)
const page = ref(1)
const pages = ref(0)
const size = 24

const detail = ref(null)
const detailLoading = ref(false)
const showDetail = ref(false)

async function load() {
  loading.value = true
  try {
    const d = await api.pesticideList(appliedQ.value, page.value, size)
    items.value = d.items || []
    total.value = d.total || 0
    pages.value = d.pages || 0
  } catch (e) { toast.error(e.message) } finally { loading.value = false }
}
function search() { appliedQ.value = q.value.trim(); page.value = 1; load() }
function go(p) { if (p < 1 || p > pages.value) return; page.value = p; load(); window.scrollTo({ top: 0, behavior: 'smooth' }) }

async function open(item) {
  showDetail.value = true
  detailLoading.value = true
  detail.value = null
  try {
    detail.value = await api.pesticideDetail(item.name)
  } catch (e) { toast.error(e.message); showDetail.value = false } finally { detailLoading.value = false }
}

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-head">
      <h1>药剂资料</h1>
      <p>{{ total }} 种药剂 · 由各病害防治方案自动抽取，点开查看适用病害与用药原文</p>
    </div>

    <div class="card card-pad search-row">
      <input class="input" style="flex:1" v-model="q" placeholder="搜索药剂名或防治对象，如「苯醚甲环唑」「锈病」…" @keydown.enter="search" />
      <button class="btn primary" @click="search">检索</button>
    </div>

    <div v-if="loading" class="loading-row" style="margin-top: 14px"><span class="spinner"></span>加载药剂…</div>

    <div v-else class="grid ps-grid">
      <div v-for="it in items" :key="it.name" class="card ps-card" @click="open(it)">
        <div class="ps-head">
          <div class="ps-icon">🧪</div>
          <div>
            <div class="ps-name">{{ it.name }}</div>
            <div class="ps-count">
              适用于 {{ it.disease_count }} 种病害<template v-if="it.formulation"> · {{ it.formulation }}</template>
            </div>
          </div>
        </div>
        <div class="ps-crops">
          <span v-for="c in it.crops" :key="c" class="badge green">{{ c }}</span>
        </div>
        <div class="ps-brief" v-if="it.brief">{{ it.brief }}</div>
        <div class="ps-dose" v-if="it.dosage">用量：{{ it.dosage }}</div>
      </div>
    </div>
    <div v-if="!loading && pages > 1" class="pager">
      <button class="btn ghost" :disabled="page <= 1" @click="go(page - 1)">上一页</button>
      <span class="pager-info">第 {{ page }} / {{ pages }} 页 · 共 {{ total }} 种</span>
      <button class="btn ghost" :disabled="page >= pages" @click="go(page + 1)">下一页</button>
    </div>

    <div v-if="!loading && !items.length" class="empty card" style="margin-top: 14px">
      <div class="icon">🧪</div>没有匹配的药剂
    </div>

    <Modal :show="showDetail" :title="detail ? `药剂 · ${detail.name}` : '药剂详情'" width="620px" @close="showDetail = false">
      <div v-if="detailLoading" class="loading-row"><span class="spinner"></span>加载详情…</div>
      <template v-else-if="detail">
        <div class="card-title">适用病害（{{ detail.diseases?.length || 0 }}）</div>
        <div class="dis-list">
          <div v-for="(d, i) in detail.diseases" :key="i" class="dis-item">
            <span class="badge blue">{{ d.crop }}</span>
            <b>{{ d.disease }}</b>
          </div>
          <div v-if="!detail.diseases?.length" class="dim">暂无关联病害</div>
        </div>

        <div class="card-title" style="margin-top: 20px">用药方案原文</div>
        <div class="raw-list">
          <div v-for="(r, i) in detail.raw" :key="i" class="raw-item">{{ r }}</div>
          <div v-if="!detail.raw?.length" class="dim">暂无原文</div>
        </div>
  </template>
    </Modal>
  </div>
</template>

<style scoped>
.search-row { display: flex; gap: 10px; }
.ps-grid { grid-template-columns: repeat(auto-fill, minmax(270px, 1fr)); margin-top: 14px; }
.ps-card { padding: 16px 18px; cursor: pointer; transition: all .16s; }
.ps-card:hover { transform: translateY(-3px); box-shadow: var(--shadow-lg); border-color: var(--indigo-300); }
.ps-head { display: flex; gap: 12px; align-items: center; margin-bottom: 11px; }
.ps-icon { width: 42px; height: 42px; background: var(--teal-bg); border-radius: 11px; display: flex; align-items: center; justify-content: center; font-size: 20px; }
.ps-name { font-size: 15.5px; font-weight: 700; }
.ps-count { font-size: 11.5px; color: var(--text-3); margin-top: 2px; }
.ps-crops { display: flex; flex-wrap: wrap; gap: 5px; margin-bottom: 9px; }
.ps-dose { margin-top: 6px; font-size: 12px; color: #8a7f74; }
.ps-pager { display: flex; align-items: center; justify-content: center; gap: 16px; margin: 22px 0 6px; }
.ps-brief { font-size: 12.5px; color: var(--text-2); line-height: 1.6; }
.dis-list { display: flex; flex-wrap: wrap; gap: 8px; }
.dis-item { display: flex; align-items: center; gap: 8px; border: 1px solid var(--line); border-radius: 9px; padding: 7px 12px; font-size: 13px; }
.raw-list { display: flex; flex-direction: column; gap: 8px; }
.raw-item {
  font-size: 13px; line-height: 1.75; color: var(--text-2);
  background: #f6f6fa; border-left: 3px solid var(--indigo-400); border-radius: 0 9px 9px 0; padding: 10px 14px;
  white-space: pre-wrap;
}
.dim { color: var(--text-3); font-size: 13px; }
.pager { display: flex; align-items: center; justify-content: center; gap: 16px; margin: 22px 0 6px; }
.pager-info { color: #8a7f74; font-size: 13px; }
</style>
