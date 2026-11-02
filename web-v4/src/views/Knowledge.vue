<script setup>
import { ref, onMounted } from 'vue'
import api from '../api/client'
import { toast } from '../composables/toast'
import StatCard from '../components/StatCard.vue'

const loading = ref(false)
const stats = ref({})
const docs = ref([])
const total = ref(0)
const q = ref('')

// 上传
const fileInput = ref(null)
const upFile = ref(null)
const upCrop = ref('')
const upTitle = ref('')
const uploading = ref(false)
const upResult = ref(null)

async function load() {
  loading.value = true
  try {
    const [s, d] = await Promise.all([api.kbStats(), api.kbDocuments()])
    stats.value = s
    docs.value = filterDocs(d.items || [])
    total.value = d.total || 0
  } catch (e) { toast.error(e.message) } finally { loading.value = false }
}

function filterDocs(items) {
  const kw = q.value.trim().toLowerCase()
  if (!kw) return items
  return items.filter((i) => (i.title + i.file + (i.crop || '')).toLowerCase().includes(kw))
}

function pick(f) {
  if (!f) return
  if (!/\.(txt|md|pdf|docx)$/i.test(f.name)) return toast.error('仅支持 txt / md / pdf / docx')
  if (f.size > 20 * 1024 * 1024) return toast.error('文档不能超过 20MB')
  upFile.value = f
  if (!upTitle.value) upTitle.value = f.name.replace(/\.[^.]+$/, '')
}

async function upload() {
  if (!upFile.value || uploading.value) return
  uploading.value = true
  upResult.value = null
  try {
    const fd = new FormData()
    fd.append('file', upFile.value)
    if (upCrop.value.trim()) fd.append('crop', upCrop.value.trim())
    if (upTitle.value.trim()) fd.append('title', upTitle.value.trim())
    const r = await api.kbUpload(fd)
    upResult.value = r
    toast.success(r.duplicated ? '内容重复，未新增切片' : `入库成功，新增 ${r.chunks_added} 个切片`)
    load()
  } catch (e) { toast.error(e.message) } finally { uploading.value = false }
}

async function remove(doc) {
  if (!confirm(`确定删除文档「${doc.title}」及其 ${doc.chunk_count} 个切片吗？删除会重建向量矩阵，可能较慢。`)) return
  try {
    const r = await api.kbDelete(doc.id)
    toast.success(`已删除，剩余 ${r.chunks_left} 个切片`)
    load()
  } catch (e) { toast.error(e.message) }
}

const isBuiltin = (d) => d.builtin || String(d.id).startsWith('builtin:')

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-head">
      <h1>知识库</h1>
      <p>RAG 向量知识库管理：内置语料只读，可上传自有文档充实问答依据</p>
    </div>

    <div class="grid k-grid">
      <StatCard label="向量切片总数" :value="stats.chunks ?? '—'" icon="🧬" tone="green" sub="chunks" />
      <StatCard label="上传文档" :value="stats.documents ?? '—'" icon="📄" tone="blue" sub="用户上传" />
      <StatCard label="内置语料页" :value="stats.builtin ?? '—'" icon="📚" tone="violet" :sub="`含 ${stats.builtin_chunks ?? '—'} 切片`" />
      <StatCard label="上传贡献切片" :value="stats.from_upload ?? '—'" icon="⬆️" tone="teal" sub="from_upload" />
    </div>

    <div class="grid upload-row">
      <div class="card card-pad">
        <div class="card-title">上传文档入库 <span class="sub">切块 → DashScope 向量化 → 进库</span></div>
        <div class="up-zone" :class="{ 'has-file': upFile }" @click="!upFile && fileInput.click()">
          <input ref="fileInput" type="file" accept=".txt,.md,.pdf,.docx" hidden @change="e => pick(e.target.files[0])" />
          <template v-if="!upFile">
            <div class="icon">📄</div>
            <b>点击选择 txt / md / pdf / docx</b>
            <span>≤ 20MB · 内容按 sha256 去重 · 首次向量化较慢</span>
          </template>
          <template v-else>
            <div class="icon">✅</div>
            <b>{{ upFile.name }}</b>
            <span>{{ (upFile.size / 1024).toFixed(0) }} KB · 点击可重选</span>
          </template>
        </div>
        <div class="up-form">
          <input class="input" v-model="upCrop" placeholder="作物名（选填，默认「自定义」）" />
          <input class="input" v-model="upTitle" placeholder="文档标题（选填，默认文件名）" />
          <div style="display:flex; gap:10px">
            <button v-if="upFile" class="btn" @click="upFile = null; fileInput.value = ''">清除</button>
            <button class="btn primary" style="flex:1" :disabled="!upFile || uploading" @click="upload">
              <span v-if="uploading" class="spinner" style="border-color:#b6baf1;border-top-color:#fff"></span>
              {{ uploading ? '向量化中，请稍候…' : '上传入库' }}
            </button>
          </div>
        </div>

        <div v-if="upResult" class="up-result" :class="{ dup: upResult.duplicated }">
          <template v-if="upResult.duplicated">
            ⚠️ 内容与已有文档重复（{{ upResult.title }}），未新增切片
          </template>
          <template v-else>
            ✅ 已入库「{{ upResult.title }}」：新增 <b>{{ upResult.chunks_added }}</b> 个切片
            <span v-if="upResult.chunks_failed">（失败 {{ upResult.chunks_failed }}）</span>
            ，当前总量 {{ upResult.total_chunks }}
          </template>
        </div>
      </div>

      <div class="card card-pad kb-intro">
        <div class="card-title">知识库如何工作</div>
        <div class="step"><b>1</b><span>上传的文档按语义切块（每块 <b>1024 维</b> 向量）存入本地向量库</span></div>
        <div class="step"><b>2</b><span>用户提问时，问题同样向量化，按余弦相似度召回最相关的切片</span></div>
        <div class="step"><b>3</b><span>召回结果连同知识图谱事实一起交给大模型生成回答</span></div>
        <div class="step"><b>4</b><span>向量分低且图谱无事实时，自动启用<b>联网搜索</b>兜底</span></div>
        <div class="tip">入库后可在「知识图谱」页把新文档抽取为图谱实体，回答会更精准。</div>
      </div>
    </div>

    <div class="card" style="margin-top: 16px">
      <div class="card-pad" style="padding-bottom: 0">
        <div class="card-title">
          文档列表 <span class="sub">{{ total }} 个（含内置语料）</span>
          <input class="input" style="width: 240px" v-model="q" placeholder="筛选标题 / 来源 / 作物…" @input="() => { docs = filterDocs(docs); load() }" />
        </div>
      </div>
      <div v-if="loading" class="loading-row"><span class="spinner"></span>加载文档…</div>
      <div v-else style="overflow-x: auto">
        <table class="table">
          <thead><tr><th>标题</th><th>来源 / 文件</th><th>作物</th><th>字数</th><th>切片</th><th>入库时间</th><th style="text-align:right">操作</th></tr></thead>
          <tbody>
            <tr v-for="d in docs" :key="d.id">
              <td><b style="font-size: 13px">{{ d.title }}</b> <span v-if="isBuiltin(d)" class="badge violet">内置</span></td>
              <td class="src" :title="d.file">
                <a v-if="d.url" :href="d.url" target="_blank" rel="noreferrer">{{ d.file }}</a>
                <span v-else>{{ d.file }}</span>
              </td>
              <td><span class="badge green" v-if="d.crop">{{ d.crop }}</span><span v-else class="dim">—</span></td>
              <td>{{ d.chars?.toLocaleString() }}</td>
              <td>{{ d.chunk_count }}</td>
              <td class="dim">{{ d.added_at }}</td>
              <td style="text-align: right">
                <button v-if="isBuiltin(d)" class="btn sm" disabled title="内置资料随项目发布，不能删除">只读</button>
                <button v-else class="btn sm danger" @click="remove(d)">删除</button>
              </td>
            </tr>
          </tbody>
        </table>
        <div v-if="!docs.length" class="empty"><div class="icon">📭</div>没有匹配的文档</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.k-grid { grid-template-columns: repeat(4, 1fr); }
.upload-row { grid-template-columns: 1.5fr 1fr; margin-top: 0; }
.up-zone {
  border: 2px dashed var(--line); border-radius: var(--radius); padding: 26px 16px; text-align: center;
  cursor: pointer; color: var(--text-2); background: #fbfbfd; transition: all .16s;
}
.up-zone:hover { border-color: var(--indigo-400); background: var(--indigo-50); }
.up-zone .icon { font-size: 32px; margin-bottom: 6px; }
.up-zone b { display: block; color: var(--text); font-size: 14px; }
.up-zone span { font-size: 11.5px; color: var(--text-3); margin-top: 5px; display: block; }
.up-form { display: flex; gap: 9px; margin-top: 13px; flex-wrap: wrap; }
.up-form .input { flex: 1; min-width: 150px; }
.up-result {
  margin-top: 12px; font-size: 12.5px; border-radius: 10px; padding: 10px 14px;
  background: var(--indigo-50); color: var(--indigo-800); border: 1px solid var(--indigo-100);
}
.up-result.dup { background: var(--amber-bg); color: var(--amber); border-color: #f5dfc0; }

.kb-intro .step { display: flex; gap: 11px; align-items: flex-start; margin-bottom: 12px; font-size: 12.5px; color: var(--text-2); line-height: 1.65; }
.kb-intro .step > b {
  width: 22px; height: 22px; border-radius: 7px; background: var(--indigo-100); color: var(--indigo-700);
  display: flex; align-items: center; justify-content: center; font-size: 12px; flex-shrink: 0; margin-top: 1px;
}
.kb-intro .tip { font-size: 11.5px; color: var(--amber); background: var(--amber-bg); border-radius: 9px; padding: 8px 12px; line-height: 1.6; }
.src { max-width: 260px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-size: 12px; }
.src a { color: var(--blue); }
.dim { color: var(--text-3); font-size: 12px; white-space: nowrap; }
@media (max-width: 1150px) { .k-grid { grid-template-columns: repeat(2, 1fr); } .upload-row { grid-template-columns: 1fr; } }
</style>
