<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useRealtimeDetect } from '../../composables/detectRealtime'

const { videoEl, overlayEl, captureEl, running, conf, costMs, fps, logs, errText } = useRealtimeDetect()

/**
 * 把摄像头黑框的高度上报给父级，让左栏底部刚好停在黑框下沿。
 * 黑框高度随视口变化，所以用 ResizeObserver 实时同步。
 */
const emit = defineEmits(['stage-bottom'])
const stageEl = ref(null)
let ro = null

onMounted(() => {
  if (!stageEl.value) return
  const report = () => {
    if (stageEl.value) emit('stage-bottom', Math.round(stageEl.value.getBoundingClientRect().bottom))
  }
  ro = new ResizeObserver(report)
  ro.observe(stageEl.value)
  report()
  window.addEventListener('resize', report)
  ro._onResize = report
})

onBeforeUnmount(() => {
  if (ro) { ro._onResize && window.removeEventListener('resize', ro._onResize); ro.disconnect() }
})
</script>

<template>
  <div class="res">
    <div class="stage card" ref="stageEl" :class="{ live: running }">
      <video ref="videoEl" muted playsinline></video>
      <canvas ref="overlayEl" class="overlay"></canvas>
      <div class="live-tag" v-if="running"><i></i>LIVE · {{ fps }} FPS · {{ costMs ?? '—' }}ms</div>
      <div class="stage-mask" v-if="!running">
        <div class="icon">📡</div>
        <b>等待摄像头画面</b>
        <span>左侧点击「开启摄像头」后，这里显示实时检测画面</span>
      </div>
    </div>
    <canvas ref="captureEl" hidden></canvas>

    <div v-if="errText" class="err card card-pad">⚠️ {{ errText }}</div>

    <div class="card card-pad">
      <div class="card-title">实时检出流 <span class="sub">{{ logs.length ? `最近 ${logs.length} 条` : '' }}</span></div>
      <div v-if="logs.length" class="log-list">
        <div v-for="(l, i) in logs" :key="i" class="log-item">
          <div class="log-top">
            <b>{{ l.name }}</b>
            <span class="badge green">{{ (l.conf * 100).toFixed(0) }}%</span>
          </div>
          <div class="log-sub">
            {{ l.time }} · {{ l.count }} 个目标
            <span v-if="l.saved" class="badge blue sm-badge">已存档</span>
          </div>
        </div>
      </div>
      <div v-else class="empty">
        <div class="icon">📡</div>
        开启摄像头并检出目标后，这里会滚动显示检出流
      </div>
    </div>
  </div>
</template>

<style scoped>
.res { display: flex; flex-direction: column; gap: 14px; }
.stage {
  position: relative; background: #10160f; overflow: hidden;
  min-height: 380px; display: flex; align-items: center; justify-content: center;
}
.stage.live { border: 1.5px solid var(--indigo-500); }
.stage video { width: 100%; max-height: 560px; display: block; object-fit: contain; }
.stage .overlay { position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none; }
.live-tag {
  position: absolute; top: 12px; left: 12px; display: flex; align-items: center; gap: 6px;
  background: rgba(10, 20, 12, .72); color: #fff; font-size: 12px; font-family: var(--mono);
  padding: 5px 11px; border-radius: 999px;
}
.live-tag i { width: 8px; height: 8px; border-radius: 50%; background: #ff4d4f; animation: blink 1.1s infinite; }
@keyframes blink { 50% { opacity: .35; } }
.stage-mask {
  position: absolute; inset: 0; display: flex; flex-direction: column; gap: 8px;
  align-items: center; justify-content: center; color: #7d9a86; text-align: center; padding: 20px;
}
.stage-mask .icon { font-size: 44px; opacity: .5; }
.stage-mask b { color: #a8c2ad; font-size: 15px; }
.stage-mask span { font-size: 12px; max-width: 300px; line-height: 1.6; }
.err { color: var(--red); font-size: 13px; }
.log-list { display: flex; flex-direction: column; gap: 8px; max-height: 320px; overflow-y: auto; }
.log-item { background: #f6f6fa; border: 1px solid #e9e9f2; border-radius: 10px; padding: 9px 12px; }
.log-top { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.log-top b { font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.log-sub { font-size: 11px; color: var(--text-3); margin-top: 4px; display: flex; align-items: center; gap: 6px; }
.sm-badge { font-size: 10px; padding: 0 6px; }
.empty { color: var(--text-3); font-size: 12.5px; }
</style>
