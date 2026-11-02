<script setup>
import { useRealtimeDetect } from '../../composables/detectRealtime'

const { running, saveRecord, conf, errText, start, stop } = useRealtimeDetect()
</script>

<template>
  <div class="ops">
    <div class="cam" :class="{ live: running }">
      <div class="cam-icon">{{ running ? '🟢' : '📷' }}</div>
      <b>{{ running ? '摄像头运行中' : '摄像头未开启' }}</b>
      <span>{{ running ? '画面正逐帧推送到后端检测' : '开启后逐帧推送到后端 YOLO 实时检测' }}</span>
    </div>

    <div class="field-row" v-if="running">
      <div class="field-head">
        <span>置信度阈值</span>
        <b>{{ conf.toFixed(2) }}</b>
      </div>
      <input type="range" min="0.1" max="0.9" step="0.05" v-model.number="conf" />
    </div>

    <label v-if="running" class="save-toggle">
      <input type="checkbox" v-model="saveRecord" />
      检出目标时自动存入记录
    </label>

    <div v-if="errText" class="err">⚠️ {{ errText }}</div>

    <div class="actions">
      <button v-if="!running" class="btn primary" @click="start">开启摄像头</button>
      <button v-else class="btn danger" @click="stop">停止检测</button>
    </div>
  </div>
</template>

<style scoped>
.ops { display: flex; flex-direction: column; gap: 14px; }

.cam {
  /* 与图片/视频识别的上传区等高（232px），三个标签页左栏底部才对齐 */
  min-height: 232px; display: flex; flex-direction: column;
  align-items: center; justify-content: center; gap: 7px;
  border: 1.5px dashed #dfe0ec; border-radius: 12px; background: #fbfbfe;
  text-align: center; color: var(--text-3);
}
.cam.live { border-style: solid; border-color: #b9e6d2; background: #f2fbf6; }
.cam-icon { font-size: 34px; margin-bottom: 2px; }
.cam b { font-size: 13.5px; color: var(--text); font-weight: 600; }
.cam span { font-size: 11.5px; max-width: 240px; line-height: 1.6; }

.field-row { display: flex; flex-direction: column; gap: 7px; }
.field-head { display: flex; justify-content: space-between; font-size: 12.5px; color: var(--text-2); }
.field-head b {
  color: var(--indigo-600); font-family: var(--mono); font-size: 12px;
  background: var(--indigo-50); border-radius: 6px; padding: 1px 7px;
}
.field-row input[type=range] { width: 100%; accent-color: var(--indigo-500); cursor: pointer; }

.save-toggle { display: flex; align-items: center; gap: 8px; font-size: 12.5px; color: var(--text-2); cursor: pointer; }
.save-toggle input { accent-color: var(--indigo-500); width: 15px; height: 15px; }

.err { font-size: 11.5px; color: var(--red); background: #fdeeee; border-radius: 8px; padding: 8px 11px; }

.actions { display: flex; gap: 10px; }
.btn { flex: 1; height: 40px; border-radius: 10px; font-size: 13px; cursor: pointer; border: 0; font-weight: 600; }
.btn.primary { background: linear-gradient(135deg, var(--indigo-500), var(--indigo-600)); color: #fff; box-shadow: 0 6px 16px -8px rgba(74, 74, 194, .8); }
.btn.danger { background: #fff; color: var(--red); border: 1px solid #f3c9c7; }
.btn.danger:hover { background: #fdeeee; }
</style>