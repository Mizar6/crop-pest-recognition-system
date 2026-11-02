<script setup>
import { ref, onMounted } from 'vue'
import api from '../api/client'
import { toast } from '../composables/toast'
import { useModelInfo } from '../composables/modelInfo'
import Modal from '../components/Modal.vue'
import Train from './Train.vue'

const loading = ref(false)
const list = ref([])
const active = ref('')

const fileInput = ref(null)
const upFile = ref(null)
const upName = ref('')
const uploading = ref(false)
const actingId = ref('')

const curModel = ref(null)
const { refresh: refreshModelInfo } = useModelInfo()
const mapping = ref(null)
const view = ref('models')  // models | train

async function load() {
  loading.value = true
  try {
    const d = await api.modelList()
    list.value = d.models || []
    active.value = d.active || ''
    const act = list.value.find((m) => m.active)
    if (act && !curModel.value) curModel.value = act
  } catch (e) { toast.error(e.message) } finally { loading.value = false }
}

function pick(f) {
  if (!f) return
  if (!/\.pt$/i.test(f.name)) return toast.error('只接受 .pt 权重文件')
  if (f.size > 300 * 1024 * 1024) return toast.error('权重不能超过 300MB')
  upFile.value = f
  if (!upName.value) upName.value = f.name.replace(/\.pt$/i, '')
}

async function upload() {
  if (!upFile.value || uploading.value) return
  uploading.value = true
  try {
    const fd = new FormData()
    fd.append('file', upFile.value)
    if (upName.value.trim()) fd.append('name', upName.value.trim())
    const r = await api.modelUpload(fd)
    toast.success(`上传成功：${r.name}（${r.class_num} 类），已自动探测`)
    refreshModelInfo()
    upFile.value = null
    upName.value = ''
    if (fileInput.value) fileInput.value.value = ''
    load()
  } catch (e) { toast.error('上传失败：' + e.message) } finally { uploading.value = false }
}

async function activate(m) {
  actingId.value = m.id
  try {
    await api.modelActivate(m.id)
    toast.success(`已切换到「${m.name}」，下一次识别生效`)
    load()
    refreshModelInfo()
    api.detectModel().then((info) => {
      curModel.value = { ...m, ...info }
      mapping.value = info.mapping || null
    }).catch(() => {})
    } catch (e) { toast.error(e.message) } finally { actingId.value = '' }
}

async function remove(m) {
  if (!confirm(`确定删除模型「${m.name}」（${m.file}）吗？`)) return
  try {
    await api.modelDelete(m.id)
    toast.success('已删除')
    load()
    refreshModelInfo()
  } catch (e) { toast.error(e.message) }
}


onMounted(async () => {
  await load()
    try {
    const info = await api.detectModel()
    curModel.value = info
    mapping.value = info.mapping || null
  } catch (e) { toast.error('读取模型信息失败：' + e.message) }
})
</script>

<template>
  <div class="page">
    <div class="page-head">
      <h1>模型管理</h1>
      <p>YOLO 权重的上传、训练、探测与热切换 —— 切换后下一次识别立即生效，无需重启</p>
    </div>

    <div class="view-tabs">
      <button class="vt" :class="{ on: view === 'models' }" @click="view = 'models'">模型管理</button>
      <button class="vt" :class="{ on: view === 'train' }" @click="view = 'train'">模型训练</button>
    </div>

    <Train v-if="view === 'train'" embedded />

    <template v-else>
    <div class="grid m-grid">
      <!-- 当前模型 -->
      <div class="card card-pad current">
        <div class="card-title">当前生效模型</div>
        <template v-if="curModel">
          <div class="cur-name">
            <span class="cur-dot"></span>
            <b>{{ curModel.model_name || curModel.name }}</b>
          </div>
          <div class="cur-meta">
            <span class="badge outline" v-if="curModel.file">权重：{{ curModel.file }}</span>
            <span class="badge outline">{{ curModel.class_num || curModel.classes?.length || '?' }} 类</span>
            <span class="badge outline" v-if="curModel.imgsz">imgsz {{ curModel.imgsz }}</span>
          </div>

          <!-- 类别与数据库表的对齐情况 -->
          <div v-if="mapping" class="map-box" :class="{ warn: (mapping.unmapped?.length || 0) + (mapping.mismatched?.length || 0) > 0 }">
            <div class="map-top">
              <b>类别与知识表匹配</b>
              <span class="map-num">
                {{ mapping.matched }} / {{ mapping.total }} 已匹配
              </span>
            </div>
            <p class="map-hint" v-if="!mapping.unmapped?.length && !mapping.mismatched?.length">
              全部类别都能按名字在知识表里找到，识别后可正常带出症状与防治建议。
            </p>
            <template v-else>
              <p class="map-hint">
                以下类别在知识表里按名字找不到，识别后会显示「数据库里没有」：
              </p>
              <ul class="map-list">
                <li v-for="n in mapping.unmapped || []" :key="'u' + n">
                  <span class="badge red">缺失</span> 模型「{{ n }}」在知识表里没有同名条目
                </li>
              </ul>
            </template>
          </div>

          <div class="cls-preview" v-if="curModel.classes?.length">
            <span v-for="(c, i) in curModel.classes.slice(0, 8)" :key="i" class="badge gray">
              {{ typeof c === 'string' ? c : c.class_name }}
            </span>
            <span v-if="curModel.classes.length > 8" class="badge outline">+{{ curModel.classes.length - 8 }}</span>
          </div>
        </template>
        <div v-else class="dim" style="padding: 12px 0">加载中…</div>
      </div>

      <!-- 上传 -->
      <div class="card card-pad">
        <div class="card-title">上传新权重 <span class="sub">.pt · ≤300MB · 自动探测类别</span></div>
        <div class="up-row">
          <button class="btn" @click="fileInput.click()">
            {{ upFile ? `✅ ${upFile.name}（${(upFile.size / 1024 / 1024).toFixed(1)}MB）` : '选择 .pt 文件' }}
          </button>
          <input ref="fileInput" type="file" accept=".pt" hidden @change="e => pick(e.target.files[0])" />
          <input class="input" style="flex: 1" v-model="upName" placeholder="模型名称（默认文件名）" />
          <button class="btn primary" :disabled="!upFile || uploading" @click="upload">
            <span v-if="uploading" class="spinner" style="border-color:#b6baf1;border-top-color:#fff"></span>
            {{ uploading ? '上传并探测中…' : '上传' }}
          </button>
        </div>
        <div class="hint">上传后服务端会立即加载一次权重读取类别表，非法权重会被拒绝且不留垃圾文件</div>
      </div>
    </div>

    <div v-if="loading" class="loading-row" style="margin-top: 16px"><span class="spinner"></span>加载模型列表…</div>

    <div v-else class="model-list">
      <div v-for="m in list" :key="m.id" class="card m-item" :class="{ active: m.active }">
        <div class="m-icon">{{ m.active ? '⚡' : '📦' }}</div>
        <div class="m-info">
          <div class="m-name">
            <b>{{ m.name }}</b>
            <span class="badge" :class="m.active ? 'green' : 'gray'">{{ m.active ? '使用中' : '备用' }}</span>
          </div>
          <div class="m-meta">
            <code>{{ m.file }}</code>
            <span>{{ m.class_num }} 类</span>
            <span>{{ m.size_mb }} MB</span>
            <span>{{ m.added_at }}</span>
          </div>
        </div>
        <div class="m-ops">
          <button v-if="!m.active" class="btn sm primary" :disabled="actingId === m.id" @click="activate(m)">
            {{ actingId === m.id ? '切换中…' : '切换启用' }}
          </button>
          <button class="btn sm danger" :disabled="m.active" :title="m.active ? '不可删除当前激活模型' : ''" @click="remove(m)">删除</button>
        </div>
      </div>
      <div v-if="!list.length" class="empty card"><div class="icon">📦</div>还没有模型</div>
    </div>
    </template>
  </div>
</template>

<style scoped>
.view-tabs { display: inline-flex; gap: 4px; background: #f2f3f9; border-radius: 11px; padding: 4px; margin-bottom: 16px; }
.vt { border: 0; background: transparent; cursor: pointer; padding: 8px 20px; border-radius: 8px; font-size: 13px; color: var(--text-2); }
.vt:hover { color: var(--indigo-600); }
.vt.on { background: #fff; color: var(--indigo-600); font-weight: 600; box-shadow: 0 1px 4px rgba(20,20,45,.12); }
.map-panel-inner { display: flex; flex-direction: column; }
.map-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
.map-entry { display: flex; align-items: center; gap: 10px; margin: 10px 0 12px; }
.map-entry-hint { font-size: 11.5px; color: var(--text-3); }
.map-count { margin-left: auto; font-family: var(--mono); font-size: 11.5px; color: var(--indigo-600); }
.map-toolbar { display: flex; gap: 10px; margin-bottom: 12px; }
.map-table { max-height: 58vh; overflow-y: auto; border: 1px solid var(--line); border-radius: 10px; }
.map-row {
  display: grid; grid-template-columns: 48px 1fr 1.4fr 84px;
  gap: 10px; align-items: center; padding: 7px 12px;
  border-bottom: 1px solid var(--line-soft); font-size: 12.5px;
}
.map-row:last-child { border-bottom: 0; }
.map-row--head {
  position: sticky; top: 0; background: #f7f8fc; z-index: 1;
  font-size: 11px; color: var(--text-3); letter-spacing: .06em;
}
.map-name { color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.map-select { height: 30px; font-size: 12px; }
.map-box {
  margin: 12px 0 14px; border: 1px solid #d9ecdf; background: #f4fbf7;
  border-radius: 10px; padding: 11px 13px;
}
.map-box.warn { border-color: #f3ddc2; background: #fef9f2; }
.map-top { display: flex; justify-content: space-between; align-items: center; font-size: 12.5px; }
.map-top b { color: var(--text); font-weight: 600; }
.map-num { font-family: var(--mono); font-size: 11.5px; color: #1a7f5a; }
.map-box.warn .map-num { color: #b45309; }
.map-hint { font-size: 11.5px; color: var(--text-3); margin-top: 6px; line-height: 1.6; }
.map-list { list-style: none; margin: 8px 0 0; display: flex; flex-direction: column; gap: 6px; }
.map-list li { font-size: 11.5px; color: var(--text-2); display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
.map-actions { margin-top: 8px; }
.map-list li em { font-style: normal; color: var(--text-3); font-size: 11px; }
.badge.gold { background: #fdf6dc; color: #8a6a10; border: 1px solid #ecd9a0; }\n.badge.red { background: #fdeeee; color: var(--red); border: 1px solid #f3c9c7; }
.m-grid { grid-template-columns: 1.2fr 1fr; }
.cur-name { display: flex; align-items: center; gap: 10px; font-size: 16px; }
.cur-dot { width: 10px; height: 10px; border-radius: 50%; background: var(--indigo-500); box-shadow: 0 0 10px rgba(90, 95, 216, .7); }
.cur-meta { display: flex; gap: 7px; margin: 11px 0; flex-wrap: wrap; }
.cls-preview { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 4px; }

.up-row { display: flex; gap: 9px; flex-wrap: wrap; }
.hint { font-size: 11.5px; color: var(--text-3); margin-top: 10px; line-height: 1.6; }

.model-list { display: flex; flex-direction: column; gap: 11px; margin-top: 16px; }
.m-item { display: flex; align-items: center; gap: 15px; padding: 15px 19px; transition: all .15s; }
.m-item.active { border-color: var(--indigo-400); background: linear-gradient(135deg, #fbfbfd, var(--indigo-50)); }
.m-icon { width: 42px; height: 42px; border-radius: 11px; background: var(--indigo-100); display: flex; align-items: center; justify-content: center; font-size: 19px; flex-shrink: 0; }
.m-item:not(.active) .m-icon { background: #eef1ec; }
.m-info { flex: 1; min-width: 0; }
.m-name { display: flex; align-items: center; gap: 9px; font-size: 14.5px; }
.m-meta { display: flex; gap: 13px; margin-top: 5px; font-size: 11.5px; color: var(--text-3); flex-wrap: wrap; align-items: center; }
.m-meta code { font-family: var(--mono); background: #f1f1f6; border-radius: 5px; padding: 1px 7px; font-size: 11px; }
.m-ops { display: flex; gap: 8px; flex-shrink: 0; }
.dim { color: var(--text-3); }
@media (max-width: 1000px) { .m-grid { grid-template-columns: 1fr; } }
</style>
