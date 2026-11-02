<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

const props = defineProps({ embedded: { type: Boolean, default: false } })
import * as echarts from 'echarts'
import api from '../api/client'
import { toast } from '../composables/toast'

// ── 表单 ──
const uploading = ref(false)
const dataset = ref(null)          // 上传成功后返回的 meta
const baseModel = ref('yolo26s')
const preset = ref('standard')
const threshold = ref(Number(localStorage.getItem('train_threshold') || 0.5))
const starting = ref(false)

const PRESETS = { quick: 30, standard: 120, fine: 300 }

// ── 任务 ──
const task = ref(null)
const curves = ref(null)
const showCurves = ref(false)
let pollTimer = null
let chartLoss = null
let chartMetric = null

const epochs = computed(() => PRESETS[preset.value] || 120)
const statusText = {
  pending: '排队中', running: '训练中', success: '已完成',
  failed: '失败', canceled: '已取消', interrupted: '被中断'
}

function pickFile(f) {
  if (!f) return
  if (!/\.zip$/i.test(f.name)) return toast.error('请上传 .zip')
  upload(f)
}

async function upload(f) {
  uploading.value = true
  dataset.value = null
  try {
    const fd = new FormData()
    fd.append('file', f)
    const d = await api.trainUpload(fd)
    dataset.value = d
    toast.success(`校验通过：${d.classes} 类 · ${d.images} 张图 · ${d.boxes} 个框`)
  } catch (e) {
    toast.error(e.message)
  } finally {
    uploading.value = false
  }
}

async function start() {
  if (!dataset.value || starting.value) return
  starting.value = true
  try {
    localStorage.setItem('train_threshold', String(threshold.value))
    const r = await api.trainStart({
      dataset_id: dataset.value.dataset_id,
      base_model: baseModel.value,
      preset: preset.value,
      epochs: epochs.value,
      threshold: threshold.value
    })
    task.value = { task_id: r.task_id, status: 'pending', progress: 0, total_epochs: r.epochs }
    poll()
  } catch (e) {
    toast.error(e.message)
  } finally {
    starting.value = false
  }
}

async function poll() {
  if (!task.value?.task_id) return
  try {
    task.value = await api.trainTask(task.value.task_id)
    if (['pending', 'running'].includes(task.value.status)) {
      pollTimer = setTimeout(poll, 3000)
    } else {
      toast[task.value.status === 'success' ? 'success' : 'error'](
        task.value.status === 'success'
          ? `训练完成 · mAP50 ${(task.value.map50 ?? 0).toFixed(3)}`
          : `训练${statusText[task.value.status] || '结束'}：${task.value.error || ''}`
      )
    }
  } catch (e) {
    toast.error(e.message)
  }
}

async function cancel() {
  if (!task.value?.task_id) return
  try {
    await api.trainCancel(task.value.task_id)
    toast.info('已取消')
    poll()
  } catch (e) { toast.error(e.message) }
}

async function openCurves() {
  if (!task.value?.task_id) return
  showCurves.value = true
  try {
    curves.value = await api.trainCurves(task.value.task_id)
    requestAnimationFrame(drawCurves)
  } catch (e) { toast.error(e.message) }
}

function drawCurves() {
  const c = curves.value
  if (!c?.epochs?.length) return

  const axisCommon = {
    type: 'category', data: c.epochs, boundaryGap: false,
    axisLabel: { fontSize: 10, color: '#6a655a' },
    axisLine: { lineStyle: { color: '#e3ddce' } }, axisTick: { show: false }
  }
  const yCommon = {
    type: 'value', splitLine: { lineStyle: { color: '#efeade' } },
    axisLabel: { fontSize: 10, color: '#6a655a' }
  }
  const tip = { trigger: 'axis', backgroundColor: '#fff', borderColor: '#e3ddce', textStyle: { color: '#1d1b17', fontSize: 11 } }

  const lossEl = document.getElementById('train-loss')
  const metricEl = document.getElementById('train-metric')
  if (lossEl) {
    chartLoss = chartLoss || echarts.init(lossEl)
    chartLoss.setOption({
      tooltip: tip, legend: { top: 0, textStyle: { fontSize: 11 } },
      grid: { left: 44, right: 16, top: 34, bottom: 28 },
      xAxis: axisCommon, yAxis: yCommon,
      series: [
        { name: '训练框损失', type: 'line', smooth: true, symbol: 'none', data: c.losses.train_box, lineStyle: { width: 2 } },
        { name: '验证框损失', type: 'line', smooth: true, symbol: 'none', data: c.losses.val_box, lineStyle: { width: 2 } },
        { name: '训练分类损失', type: 'line', smooth: true, symbol: 'none', data: c.losses.train_cls, lineStyle: { width: 1, type: 'dashed' } },
        { name: '验证分类损失', type: 'line', smooth: true, symbol: 'none', data: c.losses.val_cls, lineStyle: { width: 1, type: 'dashed' } }
      ]
    }, true)
  }
  if (metricEl) {
    chartMetric = chartMetric || echarts.init(metricEl)
    chartMetric.setOption({
      tooltip: tip, legend: { top: 0, textStyle: { fontSize: 11 } },
      grid: { left: 44, right: 16, top: 34, bottom: 28 },
      xAxis: axisCommon,
      yAxis: { ...yCommon, max: 1, axisLabel: { fontSize: 10, color: '#6a655a', formatter: (v) => (v * 100).toFixed(0) + '%' } },
      series: [
        { name: 'Precision', type: 'line', smooth: true, symbol: 'none', data: c.metrics.precision },
        { name: 'Recall', type: 'line', smooth: true, symbol: 'none', data: c.metrics.recall },
        { name: 'mAP@0.5', type: 'line', smooth: true, symbol: 'none', data: c.metrics.map50, lineStyle: { width: 2 } },
        { name: 'mAP@0.5-0.95', type: 'line', smooth: true, symbol: 'none', data: c.metrics.map50_95 }
      ]
    }, true)
  }
}

const onResize = () => { chartLoss?.resize(); chartMetric?.resize() }

onMounted(() => {
  window.addEventListener('resize', onResize)
  api.trainList().then((d) => {
    const latest = (d.items || [])[0]
    if (latest) dataset.value = latest
  }).catch(() => {})
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  clearTimeout(pollTimer)
  chartLoss?.dispose(); chartMetric?.dispose()
})
</script>

<template>
  <div class="page" :style="props.embedded ? 'padding: 0' : ''">
    <div class="page-head" v-if="!props.embedded">
      <h1>模型训练</h1>
      <p>上传 YOLO 格式数据集 → 一键训练 → 看曲线 → 达标才允许上线</p>
    </div>

    <!-- 数据集与参数（常驻显示） -->
    <div class="card card-pad upload-panel">
      <div class="drop" @click="$refs.file.click()" @dragover.prevent @drop.prevent="pickFile($event.dataTransfer.files[0])">
        <input ref="file" type="file" accept=".zip" hidden @change="pickFile($event.target.files[0])" />
        <div class="dz-icon">📦</div>
        <b>{{ uploading ? '上传校验中…' : '点击或拖拽数据集 zip' }}</b>
        <span>严格 YOLO：images/ + labels/ + data.yaml（可选）· ≤2GB</span>
      </div>

      <div v-if="dataset" class="ds-info">
        <div class="row" style="gap:8px; flex-wrap:wrap">
          <span class="badge green">{{ dataset.classes }} 类</span>
          <span class="badge">{{ dataset.images }} 张图</span>
          <span class="badge">{{ dataset.boxes }} 个框</span>
          <span class="badge" v-if="dataset.clipped">{{ dataset.clipped }} 处坐标已裁剪</span>
        </div>
        <div class="chips">
          <span v-for="n in (dataset.class_names || []).slice(0, 12)" :key="n" class="chip">{{ n }}</span>
          <span v-if="(dataset.class_names || []).length > 12" class="chip">+{{ dataset.class_names.length - 12 }}</span>
        </div>
      </div>

      <div class="params">
        <label>基础模型
          <select v-model="baseModel" class="input">
            <option value="yolo26n">yolo26n（最快）</option>
            <option value="yolo26s">yolo26s（均衡）</option>
            <option value="yolo26m">yolo26m（更准）</option>
          </select>
        </label>
        <label>训练档位
          <select v-model="preset" class="input">
            <option value="quick">快速 30 轮</option>
            <option value="standard">标准 120 轮</option>
            <option value="fine">精细 300 轮</option>
          </select>
        </label>
        <label>上线阈值 mAP50
          <input v-model.number="threshold" type="number" min="0.05" max="0.99" step="0.01" class="input" />
        </label>
      </div>

      <div class="actions">
        <button class="btn primary" :disabled="!dataset || starting" @click="start">
          {{ starting ? '启动中…' : `开始训练（${epochs} 轮）` }}
        </button>
      </div>
    </div>

    <!-- 当前任务 -->
    <div v-if="task" class="card card-pad task-card">
      <div class="task-head">
        <b>{{ statusText[task.status] || task.status }}</b>
        <span class="mono small">{{ task.progress }} / {{ task.total_epochs }} 轮</span>
        <span class="spacer"></span>
        <span v-if="task.status === 'success'" class="badge" :class="task.passed ? 'green' : 'red'">
          {{ task.passed ? '可上线' : '未达标' }}
        </span>
        <button v-if="['pending','running'].includes(task.status)" class="btn sm" @click="cancel">取消</button>
      </div>
      <div class="bar"><i :style="{ width: (task.total_epochs ? task.progress / task.total_epochs * 100 : 0) + '%' }"></i></div>
      <div class="task-meta">
        <span v-if="task.map50 != null">mAP50 <b>{{ task.map50.toFixed(3) }}</b></span>
        <span v-if="task.map50_95 != null">mAP50-95 <b>{{ task.map50_95.toFixed(3) }}</b></span>
        <span>阈值 <b>{{ task.threshold }}</b></span>
        <span v-if="task.error" class="err">{{ task.error }}</span>
        <span class="spacer"></span>
        <button class="btn sm" :disabled="!task.progress" @click="openCurves">📈 查看训练数据</button>
      </div>
    </div>

    <!-- 曲线弹窗（按钮隐藏式） -->
    <div v-if="showCurves" class="mask" @click.self="showCurves = false">
      <div class="modal">
        <div class="modal-head">
          <b>训练过程数据</b>
          <button class="btn sm" @click="showCurves = false">关闭</button>
        </div>
        <div class="modal-body">
          <h4>损失曲线</h4>
          <div id="train-loss" class="chart"></div>
          <h4>精度曲线</h4>
          <div id="train-metric" class="chart"></div>
          <div class="chips" v-if="dataset?.class_names?.length">
            <span class="muted">类别：</span>
            <span v-for="n in dataset.class_names" :key="n" class="chip">{{ n }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.train-start { display: flex; align-items: center; gap: 12px; padding: 14px; margin-bottom: 14px; }
.hint { font-size: 12px; color: var(--text-3); }
.upload-panel { margin-bottom: 14px; }
.drop {
  border: 1.5px dashed #dfe0ec; border-radius: 12px; background: #fbfbfe;
  padding: 26px; text-align: center; cursor: pointer; color: var(--text-3);
}
.drop:hover { border-color: var(--indigo-400); background: #f4f5fd; }
.dz-icon { font-size: 32px; margin-bottom: 6px; }
.drop b { display: block; font-size: 13.5px; color: var(--text); }
.drop span { font-size: 11.5px; }
.ds-info { margin-top: 12px; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.chip {
  font-size: 11px; padding: 3px 8px; border-radius: 6px;
  background: #f4f5fb; color: var(--text-2); border: 1px solid #e8e9f4;
}
.params { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-top: 14px; }
.params label { display: flex; flex-direction: column; gap: 6px; font-size: 12.5px; color: var(--text-2); }
.actions { display: flex; justify-content: flex-end; margin-top: 14px; }

.task-card { margin-bottom: 14px; }
.task-head { display: flex; align-items: center; gap: 10px; }
.small { font-size: 12px; color: var(--text-3); }
.bar { height: 8px; background: #eef0f8; border-radius: 99px; overflow: hidden; margin: 10px 0; }
.bar i { display: block; height: 100%; background: linear-gradient(90deg, #8f92ee, var(--indigo-600)); transition: width .4s; }
.task-meta { display: flex; align-items: center; gap: 14px; font-size: 12.5px; color: var(--text-2); flex-wrap: wrap; }
.task-meta b { color: var(--indigo-700); font-family: var(--mono); }
.err { color: var(--red); }

.mask { position: fixed; inset: 0; background: rgba(15, 30, 18, .45); z-index: 1000; display: flex; align-items: center; justify-content: center; padding: 24px; }
.modal { background: #fff; border-radius: 14px; width: 960px; max-width: 94vw; max-height: 88vh; display: flex; flex-direction: column; overflow: hidden; }
.modal-head { display: flex; align-items: center; justify-content: space-between; padding: 14px 18px; border-bottom: 1px solid var(--line); }
.modal-body { padding: 16px 18px; overflow-y: auto; }
.modal-body h4 { font-size: 13px; margin: 8px 0 6px; }
.chart { height: 240px; }
</style>
