<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '../api/client'
import { toast } from '../composables/toast'
import EChart from '../components/EChart.vue'
import { graphData as fallbackGraph } from '../data/graphFallback'

// ── 设计令牌（沿用「墨与靛」体系）──
const C = {
  ink: '#20222b', text2: '#5b5f6e', dim: '#9094a2',
  line: '#e7e7e2', edge: '#dcdce4', label: '#5b5f6e'
}
// 类别 → 颜色：作物 病害 症状 药剂 防治措施 + 扩展
const COLORS = ['#8c3a1e', '#4c5b45', '#a9772f', '#6f6c5f', '#b0765a', '#7a8a63', '#8e4b2f', '#3f4a38', '#9c6b4a', '#5d6b57']
const DEFAULT_SIZE = [34, 22, 11, 13, 9]

// ── 数据 ──
const raw = ref({ nodes: [], links: [], categories: [] })
const usingFallback = ref(false)
const loading = ref(true)
const layout = ref('force')          // force | circular | grid
const query = ref('')
const activeCats = ref([])
const activeRels = ref([])
const focusId = ref(null)      // 搜索聚焦：只保留该节点及其相关节点
const side = ref({ title: '节点详情', sub: '点击节点查看关联。', rows: [] })

const catNames = computed(() => (raw.value.categories || []).map((c) => c.name))
// 只显示真的有节点的类别（索引保持原样，避免颜色/筛选错位）
const catList = computed(() => (raw.value.categories || [])
  .map((c, i) => ({ name: c.name, index: i, count: c.count ?? 0 })))
const relTypes = computed(() => [...new Set((raw.value.links || []).map((l) => l.value || '关联'))])
// 图例用全量关系类型（含被窗口截断的），带次数
const relList = computed(() => (raw.value.rel_types || relTypes.value.map((n) => ({ name: n, count: 0 }))))

const nodeMap = computed(() => {
  const m = {}
  raw.value.nodes.forEach((n) => { m[n.id] = n })
  return m
})

const filtered = computed(() => {
  let pool = raw.value.nodes
  // 搜索聚焦：只保留命中节点 + 它的直接关联节点
  if (focusId.value && nodeMap.value[focusId.value]) {
    const keep = new Set([focusId.value])
    raw.value.links.forEach((l) => {
      if (l.source === focusId.value) keep.add(l.target)
      else if (l.target === focusId.value) keep.add(l.source)
    })
    pool = pool.filter((n) => keep.has(n.id))
  }
  const nodes = pool.filter((n) => activeCats.value.includes(n.category))
  const ids = new Set(nodes.map((n) => n.id))
  const links = raw.value.links.filter(
    (l) => activeRels.value.includes(l.value || '关联') && ids.has(l.source) && ids.has(l.target)
  )
  return { nodes, links }
})

/* ── 三种布局（全部交给 ECharts 原生实现）──
   力导向走内置模拟；环形 / 网格为静态排布；zoom 按节点数自适应，画布始终铺满 */
function seriesFor(kind, nodes, links) {
  const s = {
    type: 'graph',
    layout: kind,
    roam: false,          // 画布整体不可拖动、不可缩放
    draggable: true,      // 单个节点仍可拖开（不影响画布）
    data: nodes.map((n) => ({
      id: n.id,
      name: n.name,
      category: n.category,
      value: n.value,
      symbolSize: n.symbolSize || DEFAULT_SIZE[n.category] || 10
    })),
    links: links.map((l) => ({ ...l })),
    categories: catNames.value.map((n, i) => ({ name: n, itemStyle: { color: COLORS[i % COLORS.length] } })),
    label: {
      show: true, fontSize: 10, color: C.label, position: 'right',
      formatter: (p) => (p.data.category <= 1 ? (p.name.length > 8 ? p.name.slice(0, 8) + '…' : p.name) : '')
    },
    labelLayout: { hideOverlap: true },
    lineStyle: { color: '#ded7c6', width: 1, curveness: 0, opacity: 0.9 },
    emphasis: { focus: 'adjacency', lineStyle: { width: 2, color: '#8c3a1e' } }
  }

  const n = nodes.length
  if (kind === 'force') {
    s.force = { repulsion: 130, edgeLength: [70, 110], gravity: 0.28 }
    s.zoom = n < 20 ? 1.8 : n < 60 ? 1.15 : 0.72
  } else if (kind === 'circular') {
    s.circular = { rotateLabel: true }
    s.zoom = n < 60 ? 1.1 : 0.78
  } else {
    const cols = Math.ceil(Math.sqrt(n || 1))
    const data = s.data
    data.forEach((d, i) => { d.x = (i % cols) * 96; d.y = Math.floor(i / cols) * 78 })
    s.layout = 'none'
    const xs = data.map((d) => d.x), ys = data.map((d) => d.y)
    const sx = Math.max(...xs) - Math.min(...xs) || 1
    const sy = Math.max(...ys) - Math.min(...ys) || 1
    s.zoom = Math.max(0.15, Math.min(1.1, 0.85 * Math.min(980 / sx, 520 / sy)))
  }
  return s
}

const option = computed(() => {
  const { nodes, links } = filtered.value
  return {
    backgroundColor: 'transparent',
    tooltip: {
      backgroundColor: '#fff', borderColor: C.line, borderWidth: 1,
      textStyle: { color: C.ink, fontSize: 11 },
      formatter: (p) => (p.dataType === 'node' ? `<b>${p.data.name}</b>` : (p.data.value || '关联'))
    },
    series: [seriesFor(layout.value, nodes, links)]
  }
})

// ── 交互 ──
function onChartClick(p) {
  if (p.dataType === 'node') showNode(p.data.id)
  else if (p.dataType === 'edge') showEdge(p.data)
}

function showNode(id) {
  const node = nodeMap.value[id]
  if (!node) return
  const rels = raw.value.links
    .filter((l) => l.source === id || l.target === id)
    .map((l) => ({ rel: l.value || '关联', other: nodeMap.value[l.source === id ? l.target : l.source]?.name || '?' }))
  side.value = {
    title: node.name,
    sub: `${catNames.value[node.category] || '未知'} · 关联 ${rels.length} 条`,
    rows: rels
  }
}

function showEdge(link) {
  side.value = {
    title: '关系详情',
    sub: link.value || '关联',
    rows: [
      { rel: '起点', other: nodeMap.value[link.source]?.name || link.source },
      { rel: '终点', other: nodeMap.value[link.target]?.name || link.target }
    ]
  }
}

function doSearch() {
  const kw = query.value.trim()
  if (!kw) return
  const hit = raw.value.nodes.find((n) => n.name.includes(kw))
  if (!hit) { side.value = { title: '无匹配', sub: '', rows: [] }; return }
  // 只保留该节点及其相关节点
  focusId.value = hit.id
  // 相关节点的类别若被取消勾选会导致看不到，这里自动勾上
  const cats = new Set([hit.category])
  raw.value.links.forEach((l) => {
    if (l.source === hit.id) { const n = nodeMap.value[l.target]; n && cats.add(n.category) }
    else if (l.target === hit.id) { const n = nodeMap.value[l.source]; n && cats.add(n.category) }
  })
  activeCats.value = catNames.value.map((_, i) => i).filter((i) => cats.has(i))
  showNode(hit.id)
}

function toggleIn(list, v) {
  const i = list.indexOf(v)
  i >= 0 ? list.splice(i, 1) : list.push(v)
}

function resetAll() {
  query.value = ''
  focusId.value = null
  activeCats.value = catNames.value.map((_, i) => i)
  activeRels.value = [...relTypes.value]
  side.value = { title: '节点详情', sub: '点击节点查看关联。', rows: [] }
}

// ── 加载 ──
function normalize(data) {
  const nodes = (data.nodes || []).map((n) => ({
    id: n.id, name: n.name, category: n.category, value: n.value,
    symbolSize: n.symbolSize || DEFAULT_SIZE[n.category] || 10
  }))
  return {
    nodes,
    links: data.links || [],
    categories: data.categories || [],
    rel_types: data.rel_types || [],
  }
}

onMounted(async () => {
  try {
    const d = await api.graphAll()
    raw.value = normalize(d)
  } catch {
    raw.value = normalize(fallbackGraph)
    usingFallback.value = true
    toast.info('后端未连接，展示内置示例图谱')
  } finally {
    loading.value = false
    activeCats.value = catNames.value.map((_, i) => i)
    activeRels.value = [...relTypes.value]
    // 支持 ?q=稻瘟病 直达（打开即聚焦到该节点及其关联）
    const kw = new URLSearchParams(window.location.search).get('q')
    if (kw) {
      query.value = kw
      doSearch()
    }
  }
})
</script>

<template>
  <div class="kg">
    <!-- 页头 -->
    <header class="kg-head">
      <div class="kicker">KNOWLEDGE GRAPH</div>
      <div class="head-row">
        <div>
          <h1>关系网络</h1>
          <p>作物、病害、症状、药剂与措施之间的关系，问答检索的锚点就是这张图。</p>
        </div>
        <span class="count-tag" :class="{ warn: usingFallback }">
          {{ usingFallback ? '示例数据' : '' }}{{ filtered.nodes.length }} 实体 · {{ filtered.links.length }} 关系
        </span>
      </div>
    </header>

    <!-- 工具栏 -->
    <div class="toolbar">
      <div class="row">
        <span class="row-label">实体类型</span>
        <label v-for="c in catList" :key="c.name" class="ck" :class="{ dim: !c.count }">
          <input
            type="checkbox"
            :checked="activeCats.includes(c.index)"
            style="accent-color: #8c3a1e"
            @change="toggleIn(activeCats, c.index)"
          />
          <i class="dot" :style="{ background: COLORS[c.index % COLORS.length] }"></i>{{ c.name }}
          <span class="ck-n">{{ c.count }}</span>
        </label>
      </div>

      <div class="row">
        <span class="row-label">关系类型</span>
        <label v-for="r in relList" :key="r.name" class="ck" :class="{ dim: !r.count }">
          <input
            type="checkbox"
            :checked="activeRels.includes(r.name)"
            style="accent-color: #8c3a1e"
            @change="toggleIn(activeRels, r.name)"
          />{{ r.name }}<span class="ck-n">{{ r.count }}</span>
        </label>
        <select class="layout-select" v-model="layout" style="margin-left:auto">
          <option value="force">力导向布局</option>
          <option value="circular">环形布局</option>
          <option value="grid">网格布局</option>
        </select>
      </div>

      <div class="row">
        <span class="row-label">搜索节点</span>
        <input
          class="search-input"
          v-model="query"
          placeholder="输入病害 / 作物 / 药剂"
          @keydown.enter="doSearch"
        />
        <button class="btn-primary" @click="doSearch">搜索</button>
        <button class="btn-plain" @click="resetAll">重置</button>
        <button v-if="focusId" class="focus-tag" @click="focusId = null">
          仅显示关联 · {{ nodeMap[focusId]?.name }}（{{ filtered.nodes.length }} 节点）✕
        </button>
      </div>
    </div>

    <!-- 舞台 -->
    <div class="stage">
      <div class="canvas-wrap">
        <div v-if="loading" class="loading">加载图谱数据…</div>
        <EChart v-else :option="option" height="100%" @click="onChartClick" />
      </div>

      <aside class="side">
        <b class="side-title">{{ side.title }}</b>
        <span class="side-sub">{{ side.sub }}</span>
        <div class="side-body" v-if="side.rows.length">
          <div v-for="(r, i) in side.rows" :key="i" class="rel-row">
            <span class="rel-name">{{ r.rel }}</span>
            <span class="rel-other">{{ r.other }}</span>
          </div>
        </div>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.kg {
  height: calc(100vh - 58px);
  display: flex; flex-direction: column;
  padding: 20px 28px 24px;
  background: #f5f2ea;
}

/* 页头 */
.kg-head { margin-bottom: 18px; }
.kicker {
  font-family: 'Consolas', 'SFMono-Regular', monospace;
  font-size: 9.5px; letter-spacing: .26em; text-transform: uppercase;
  color: #8c3a1e; margin-bottom: 6px;
}
.head-row { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; border-bottom: 2px solid #20222b; padding-bottom: 12px; }
.kg-head h1 { font-size: 24px; font-weight: 700; line-height: 1.2; }
.kg-head p { font-size: 12px; color: #9094a2; margin-top: 4px; }
.count-tag {
  flex-shrink: 0; font-size: 11.5px; font-weight: 600;
  color: #4c5b45; background: #edf2ea; border: 1px solid #cfdcc8;
  padding: 3px 10px; white-space: nowrap;
}
.count-tag.warn { color: #b45309; background: #fdf1e0; border-color: #ecd9bd; }

/* 工具栏 */
.toolbar {
  background: #faf7ee; border: 1px solid #e2ddce;
  padding: 12px 22px; margin-bottom: 14px;
  display: flex; flex-direction: column; gap: 8px;
}
.row { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; min-height: 28px; }
.row-label { width: 58px; flex-shrink: 0; font-size: 11px; color: #9094a2; }
.ck {
  display: inline-flex; align-items: center; gap: 6px;
  font-size: 12.5px; color: #5b5f6e; cursor: pointer; user-select: none;
}
.ck input { width: 13px; height: 13px; margin: 0; cursor: pointer; }
.ck .dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.layout-select { width: 132px; height: 28px; border: 1px solid #e2ddce; background: #fffdf8; font-size: 12px; color: #20222b; padding: 0 8px; outline: none; }
.search-input { width: 260px; height: 28px; border: 1px solid #e2ddce; padding: 0 10px; font-size: 12.5px; color: #20222b; outline: none; }
.search-input:focus { border-color: #8c3a1e; }
.search-input::placeholder { color: #b3b3bd; }
.btn-primary {
  height: 28px; padding: 0 16px; border: none; cursor: pointer;
  background: #8c3a1e; color: #fff; font-size: 12.5px;
}
.btn-primary:hover { background: #6f2d17; }
.btn-plain {
  height: 28px; padding: 0 12px; cursor: pointer;
  background: #fffdf8; border: 1px solid #e2ddce; color: #4a473d; font-size: 12.5px;
}
.btn-plain:hover { border-color: #8c3a1e; color: #8c3a1e; }
.focus-tag {
  height: 28px; padding: 0 12px; cursor: pointer;
  background: #f7ece4; border: 1px solid #e0c3b2; color: #8c3a1e; font-size: 12px;
}
.focus-tag:hover { background: #f2e0d5; }

/* 舞台 */
.stage {
  flex: 1; min-height: 0;
  display: grid; grid-template-columns: minmax(0, 1fr) 220px;
  background: #faf7ee; border: 1px solid #e2ddce; overflow: hidden;
}
.canvas-wrap { min-height: 0; min-width: 0; position: relative; }
.loading {
  position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
  color: #9094a2; font-size: 13px;
}

.side { border-left: 1px solid #e2ddce; padding: 16px; overflow-y: auto; min-height: 0; background: #faf7ee; }
.side-title { display: block; font-size: 13px; font-weight: 600; color: #20222b; word-break: break-all; }
.side-sub { display: block; font-size: 10.5px; color: #9094a2; margin-top: 3px; }
.side-body { margin-top: 10px; }
.rel-row {
  display: flex; align-items: baseline; gap: 8px;
  padding: 7px 0; border-bottom: 1px dashed #ececea; font-size: 11px;
}
.rel-row:last-child { border-bottom: none; }
.rel-name { width: 44px; flex-shrink: 0; color: #8c3a1e; font-weight: 600; }
.rel-other { color: #5b5f6e; word-break: break-all; }
.ck-n { margin-left: 3px; font-size: 11px; color: #a49a90; }
.ck.dim { opacity: 0.42; }
.ck.dim input { cursor: not-allowed; }
</style>
