<script setup>
import { ref, onMounted } from 'vue'
import api from '../api/client'
import { toast } from '../composables/toast'
import Modal from '../components/Modal.vue'
import { severityTone } from '../components/chartTheme'

const loading = ref(false)
const list = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)
const detectType = ref('')
const keyword = ref('')
const appliedKeyword = ref('')

const detail = ref(null) // { record, details }
const detailLoading = ref(false)
const showDetail = ref(false)

const typeTone = { image: 'green', video: 'blue', realtime: 'violet' }
const typeText = { image: '图片识别', video: '视频识别', realtime: '实时检测' }
const pages = ref(0)

async function load() {
  loading.value = true
  try {
    const d = await api.recordPage({ page: page.value, pageSize: pageSize.value, detectType: detectType.value, keyword: appliedKeyword.value })
    list.value = d.list || []
    total.value = d.total || 0
    pages.value = Math.max(1, Math.ceil(total.value / pageSize.value))
  } catch (e) { toast.error(e.message) } finally { loading.value = false }
}

function search() {
  appliedKeyword.value = keyword.value.trim()
  page.value = 1
  load()
}
function goPage(p) {
  if (p < 1 || p > pages.value || p === page.value) return
  page.value = p
  load()
}

async function openDetail(id) {
  showDetail.value = true
  detailLoading.value = true
  detail.value = null
  try {
    detail.value = await api.recordDetail(id)
  } catch (e) {
    toast.error(e.message)
    showDetail.value = false
  } finally { detailLoading.value = false }
}

async function remove(r) {
  if (!confirm(`确定删除记录 #${r.id}（${r.source_name}）吗？明细将一并删除。`)) return
  try {
    await api.recordDelete(r.id)
    toast.success('删除成功')
    if (list.value.length === 1 && page.value > 1) page.value--
    load()
  } catch (e) { toast.error(e.message) }
}

function exportExcel() {
  window.open(api.recordExportUrl, '_blank')
}

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-head" style="display:flex; justify-content:space-between; align-items:flex-end; gap: 16px; flex-wrap: wrap;">
      <div>
        <h1>检测记录</h1>
        <p>全部图片 / 视频 / 实时识别结果，可查看标注详情并导出 Excel</p>
      </div>
      <button class="btn" @click="exportExcel">⬇️ 导出 Excel（≤2000 条）</button>
    </div>

    <div class="card card-pad filter-bar">
      <select class="select" v-model="detectType" @change="search">
        <option value="">全部类型</option>
        <option value="image">图片识别</option>
        <option value="video">视频识别</option>
        <option value="realtime">实时检测</option>
      </select>
      <input class="input" style="flex:1; min-width: 200px" v-model="keyword" placeholder="按病害名 / 文件名搜索…" @keydown.enter="search" />
      <button class="btn primary" @click="search">搜索</button>
    </div>

    <div class="card" style="margin-top: 14px; overflow-x: auto;">
      <div v-if="loading" class="loading-row"><span class="spinner"></span>加载中…</div>
      <table class="table" v-else-if="list.length">
        <thead>
          <tr>
            <th>预览</th><th>类型</th><th>来源文件</th><th>主要类别</th><th>置信度</th>
            <th>目标数</th><th>耗时</th><th>时间</th><th style="text-align:right">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in list" :key="r.id">
            <td>
              <img v-if="r.source_url" :src="r.source_url" class="thumb" loading="lazy" alt="" />
              <span v-else class="thumb ph">🍃</span>
            </td>
            <td><span class="badge" :class="typeTone[r.detect_type] || 'gray'">{{ r.detect_type_text || typeText[r.detect_type] || r.detect_type }}</span></td>
            <td class="fname" :title="r.source_name">{{ r.source_name }}</td>
            <td>
              <b style="font-size: 13px">{{ r.top_class || '未检出' }}</b>
            </td>
            <td>{{ r.top_confidence != null ? (r.top_confidence * 100).toFixed(1) + '%' : '—' }}</td>
            <td>{{ r.target_count }}</td>
            <td>{{ r.cost_ms }}ms</td>
            <td class="dim">{{ r.detect_time }}</td>
            <td style="text-align:right; white-space: nowrap">
              <button class="btn sm" @click="openDetail(r.id)">详情</button>
              <button class="btn sm danger" style="margin-left:6px" @click="remove(r)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-else class="empty"><div class="icon">🗂️</div>没有匹配的记录</div>

      <div class="pager" v-if="pages > 1 && !loading">
        <button class="btn sm" :disabled="page <= 1" @click="goPage(page - 1)">‹ 上一页</button>
        <span class="pg-info">第 {{ page }} / {{ pages }} 页 · 共 {{ total }} 条</span>
        <button class="btn sm" :disabled="page >= pages" @click="goPage(page + 1)">下一页 ›</button>
      </div>
    </div>

    <!-- 详情弹窗 -->
    <Modal :show="showDetail" :title="detail ? `记录 #${detail.record?.id} · ${detail.record?.source_name || ''}` : '记录详情'" width="860px" @close="showDetail = false">
      <div v-if="detailLoading" class="loading-row"><span class="spinner"></span>加载详情…</div>
      <template v-else-if="detail">
        <div class="detail-grid">
          <div>
            <div class="img-box">
              <img :src="detail.record?.result_url || detail.record?.source_url" alt="结果图" />
            </div>
            <div class="meta-chips">
              <span class="badge" :class="typeTone[detail.record?.detect_type] || 'gray'">{{ detail.record?.detect_type_text || detail.record?.detect_type }}</span>
              <span class="badge outline">{{ detail.record?.detect_time }}</span>
              <span class="badge outline">{{ detail.record?.cost_ms }}ms</span>
            </div>
          </div>
          <div>
            <div class="d-rows">
              <div class="d-row"><span>主要类别</span><b>{{ detail.record?.top_class || '未检出' }}</b></div>
              <div class="d-row"><span>最高置信度</span><b>{{ detail.record?.top_confidence != null ? (detail.record.top_confidence * 100).toFixed(1) + '%' : '—' }}</b></div>
              <div class="d-row"><span>检出目标</span><b>{{ detail.record?.target_count }}</b></div>
              <div class="d-row"><span>来源文件</span><b>{{ detail.record?.source_name }}</b></div>
            </div>
            <div class="card-title" style="margin-top: 16px">检出框（{{ detail.details?.length || 0 }}）</div>
            <div class="box-list">
              <div v-for="(b, i) in detail.details" :key="i" class="box-item">
                <b>{{ b.class_name }}</b>
                <span class="badge green">{{ (b.confidence * 100).toFixed(1) }}%</span>
                <span class="coords">({{ b.x1 }},{{ b.y1 }},{{ b.x2 }},{{ b.y2 }})</span>
              </div>
            </div>
          </div>
        </div>
      </template>
    </Modal>
  </div>
</template>

<style scoped>
.filter-bar { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.thumb { width: 64px; height: 46px; object-fit: cover; border-radius: 8px; border: 1px solid var(--line); display: block; }
.thumb.ph { display: flex; align-items: center; justify-content: center; background: var(--indigo-50); font-size: 18px; }
.fname { max-width: 200px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-size: 12.5px; color: var(--text-2); }
.dim { color: var(--text-3); font-size: 12.5px; white-space: nowrap; }
.pager { display: flex; align-items: center; justify-content: center; gap: 14px; padding: 14px; }
.pg-info { font-size: 12.5px; color: var(--text-2); }

.detail-grid { display: grid; grid-template-columns: 1.2fr 1fr; gap: 18px; }
.img-box { border-radius: 12px; overflow: hidden; background: #10160f; display: flex; justify-content: center; }
.img-box img { max-width: 100%; max-height: 380px; object-fit: contain; }
.meta-chips { display: flex; gap: 7px; margin-top: 10px; flex-wrap: wrap; }
.d-rows { display: flex; flex-direction: column; gap: 8px; }
.d-row { display: flex; justify-content: space-between; font-size: 13px; padding: 8px 12px; background: #f6f6fa; border-radius: 9px; }
.d-row span { color: var(--text-2); }
.box-list { display: flex; flex-direction: column; gap: 7px; max-height: 260px; overflow-y: auto; }
.box-item { display: flex; align-items: center; gap: 9px; font-size: 12.5px; border: 1px solid var(--line); border-radius: 9px; padding: 7px 11px; }
.box-item b { flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.coords { font-family: var(--mono); font-size: 11px; color: var(--text-3); }
@media (max-width: 760px) { .detail-grid { grid-template-columns: 1fr; } }
</style>
