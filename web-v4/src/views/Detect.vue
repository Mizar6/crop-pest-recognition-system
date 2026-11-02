<script setup>
import { computed, onMounted, ref } from 'vue'
import ImageTab from '../components/detect/ImageTab.vue'
import ImageResult from '../components/detect/ImageResult.vue'
import VideoTab from '../components/detect/VideoTab.vue'
import VideoResult from '../components/detect/VideoResult.vue'
import RealtimeTab from '../components/detect/RealtimeTab.vue'
import RealtimeResult from '../components/detect/RealtimeResult.vue'
import { useImageDetect } from '../composables/detectImage'
import { useVideoDetect } from '../composables/detectVideo'
import { useRealtimeDetect } from '../composables/detectRealtime'
import { useModelInfo } from '../composables/modelInfo'

const mode = ref('image')
const modes = [
  { key: 'image', icon: '🖼️', label: '图片识别', hint: '单张叶片照片' },
  { key: 'video', icon: '🎬', label: '视频识别', hint: '田间录像 · 逐帧检测' },
  { key: 'realtime', icon: '📷', label: '实时检测', hint: '摄像头实时画面' }
]
const current = computed(() => modes.find((m) => m.key === mode.value))

const img = useImageDetect()
const vid = useVideoDetect()
const rt = useRealtimeDetect()
const { info: modelInfo, label: modelLabel } = useModelInfo()
modelInfo.value || useModelInfo().refresh()

// 结果区空态文案
const emptyTips = {
  image: { icon: '🪴', title: '还没有识别结果', desc: '左侧选择一张叶片照片并点击「开始识别」' },
  video: { icon: '🎞️', title: '还没有识别结果', desc: '左侧选择一段田间视频并提交识别任务' },
  realtime: { icon: '📡', title: '摄像头未开启', desc: '左侧点击「开启摄像头」开始实时检测' }
}
const stageBottom = ref(0)
const opsEl = ref(null)
const opsTick = ref(0) // 用于窗口变化时重新计算
// 左栏高度 = 黑框下沿 - 左栏上沿，这样左栏底部正好停在黑框底部
const opsHeight = computed(() => {
  opsTick.value
  if (mode.value !== 'realtime' || !stageBottom.value || !opsEl.value) return ''
  const top = opsEl.value.getBoundingClientRect().top
  return Math.max(320, Math.round(stageBottom.value - top)) + 'px'
})
onMounted(() => {
  window.addEventListener('resize', () => { opsTick.value++ })
})
const hasResult = computed(() => {
  if (mode.value === 'image') return !!img.result.value
  if (mode.value === 'video') return vid.task.value?.status === 'done' && !!vid.task.value?.result
  return rt.running.value || rt.logs.value.length > 0
})
</script>

<template>
  <div class="page">
    <header class="page-head">
      <div>
        <h1>智能识别</h1>
        <p>左侧上传或开启设备，右侧实时查看标注结果、严重程度与关联知识。</p>
      </div>
      <span class="model-chip" :title="modelLabel()">
        <i></i>{{ modelLabel() }}
      </span>
    </header>

    <div class="workbench">
      <!-- 左：识别区 -->
      <section
        class="panel panel--ops"
        ref="opsEl"
        :class="{ 'to-stage': mode === 'realtime' && stageBottom }"
        :style="{ height: opsHeight }"
      >
        <div class="segs">
          <button
            v-for="m in modes" :key="m.key"
            class="seg" :class="{ on: mode === m.key }"
            @click="mode = m.key"
          >
            <span class="seg-icon">{{ m.icon }}</span>
            <span class="seg-text">{{ m.label }}</span>
          </button>
        </div>

        <p class="ops-hint">{{ current.hint }}</p>

        <div class="ops-body">
          <ImageTab v-if="mode === 'image'" />
          <VideoTab v-else-if="mode === 'video'" />
          <RealtimeTab v-else />
        </div>
      </section>

      <!-- 右：结果区 -->
      <section class="panel panel--res">
        <div class="res-top">
          <b>识别结果</b>
          <span class="res-state" :class="{ live: hasResult }">
            <i></i>{{ hasResult ? '已出结果' : '等待识别' }}
          </span>
        </div>

        <div class="res-body">
          <ImageResult v-if="mode === 'image' && hasResult" />
          <VideoResult v-if="mode === 'video' && hasResult" />
          <RealtimeResult v-if="mode === 'realtime'" @stage-bottom="stageBottom = $event" />

          <div v-if="!hasResult && mode !== 'realtime'" class="placeholder">
            <div class="ph-icon">{{ emptyTips[mode].icon }}</div>
            <b>{{ emptyTips[mode].title }}</b>
            <p>{{ emptyTips[mode].desc }}</p>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.page-head {
  display: flex; align-items: flex-start; justify-content: space-between; gap: 16px;
  margin-bottom: 18px;
}
.page-head h1 { font-size: 24px; font-weight: 700; letter-spacing: -.01em; }
.page-head p { font-size: 13px; color: var(--text-2); margin-top: 6px; }

.model-chip {
  display: inline-flex; align-items: center; gap: 7px; flex: none;
  background: #fff; border: 1px solid var(--line); border-radius: 999px;
  padding: 7px 14px; font-size: 12px; color: var(--text-2);
  font-family: var(--mono);
}
.model-chip i { width: 7px; height: 7px; border-radius: 50%; background: #22a06b; }

/* 工作台：左窄右宽 */
.workbench {
  display: grid;
  grid-template-columns: 420px minmax(0, 1fr);
  gap: 18px;
  align-items: start;
}

.panel {
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 14px;
  box-shadow: 0 1px 2px rgba(20, 20, 45, .04), 0 8px 24px -18px rgba(20, 20, 45, .25);
}
/* 左栏跟右栏等高：三个标签页底部才会对齐 */
.panel--ops {
  padding: 16px;
  display: flex;
  flex-direction: column;
  min-height: 0;
  align-self: stretch;
}

/* 三合一切换 */
.segs {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 4px;
  background: #f2f3f9; border-radius: 11px; padding: 4px;
}
.seg {
  display: flex; flex-direction: column; align-items: center; gap: 3px;
  border: 0; background: transparent; cursor: pointer;
  padding: 9px 4px; border-radius: 8px; color: var(--text-2);
  transition: background .16s, color .16s, box-shadow .16s;
}
.seg:hover { color: var(--indigo-600); }
.seg.on {
  background: #fff; color: var(--indigo-600);
  box-shadow: 0 1px 4px rgba(20, 20, 45, .12);
}
.seg-icon { font-size: 15px; line-height: 1; }
.seg-text { font-size: 12.5px; font-weight: 500; }

.ops-hint {
  font-size: 11.5px; color: var(--text-3);
  margin: 10px 2px 14px; text-align: center;
}
.ops-body { min-width: 0; flex: 1; display: flex; flex-direction: column; min-height: 0; }
.ops-body :deep(.ops) { flex: 1; min-height: 0; }
.panel--ops.to-stage { min-height: 0; }
.panel--ops.to-stage .ops-body { overflow: hidden; }
.ops-body :deep(.drop),
.ops-body :deep(.cam) { flex: 1; }

/* 结果面板 */
.panel--res { min-width: 0; }
.res-top {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 18px; border-bottom: 1px solid var(--line);
}
.res-top b { font-size: 14.5px; }
.res-state {
  display: inline-flex; align-items: center; gap: 6px;
  font-size: 11.5px; color: var(--text-3);
}
.res-state i { width: 7px; height: 7px; border-radius: 50%; background: #c8c9d4; }
.res-state.live { color: #1a7f5a; }
.res-state.live i { background: #22a06b; box-shadow: 0 0 0 3px rgba(34, 160, 107, .16); }

.res-body { padding: 16px; }

.placeholder {
  min-height: 420px; display: flex; flex-direction: column;
  align-items: center; justify-content: center; gap: 6px;
  border: 1.5px dashed #e4e5ef; border-radius: 12px; background: #fbfbfe;
  color: var(--text-3); text-align: center;
}
.ph-icon { font-size: 44px; opacity: .55; margin-bottom: 6px; }
.placeholder b { font-size: 14.5px; color: var(--text-2); font-weight: 500; }
.placeholder p { font-size: 12.5px; }

@media (max-width: 1180px) {
  .workbench { grid-template-columns: 1fr; }
  .panel--ops { position: static; }
}
</style>
