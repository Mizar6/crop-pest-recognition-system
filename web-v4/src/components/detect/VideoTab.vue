<script setup>
import { ref } from 'vue'
import { useVideoDetect } from '../../composables/detectVideo'

const { file, previewUrl, conf, task, busy, pick, submit, reset } = useVideoDetect()
const fileInput = ref(null)

const statusText = { submitting: '上传中…', pending: '排队中…', running: '识别中', error: '识别失败' }
const isError = () => task.value?.status === 'error'
</script>

<template>
  <div class="ops">
    <div class="drop" :class="{ filled: !!previewUrl }" @click="!previewUrl && fileInput.click()">
      <input ref="fileInput" type="file" accept="video/*" hidden @change="e => pick(e.target.files[0])" />
      <template v-if="!previewUrl">
        <div class="drop-icon">🎬</div>
        <b>点击选择田间视频</b>
        <span>mp4 / avi / mov / mkv / wmv</span>
      </template>
      <template v-else>
        <video v-if="!task?.result" :src="previewUrl" controls muted class="preview"></video>
        <div class="file-chip">{{ file.name }} · {{ (file.size / 1024 / 1024).toFixed(1) }} MB</div>
      </template>
    </div>

    <div class="field-row">
      <div class="field-head">
        <span>置信度阈值</span>
        <b>{{ conf.toFixed(2) }}</b>
      </div>
      <input type="range" min="0.05" max="0.95" step="0.05" v-model.number="conf" />
    </div>

    <div v-if="task && task.status !== 'done'" class="progress-box">
      <div class="prog-top">
        <b>{{ statusText[task.status] || task.status }}</b>
        <span class="prog-num">{{ task.progress }}%</span>
      </div>
      <div class="bar"><i :style="{ width: task.progress + '%' }"></i></div>
      <div v-if="task.error" class="err">⚠️ {{ task.error }}</div>
    </div>

    <div class="actions">
      <button v-if="file && !busy" class="btn ghost" @click="reset">重选</button>
      <button class="btn primary" :disabled="!file || busy" @click="submit">
        {{ busy ? '识别中…' : (isError() ? '重试识别' : '提交识别任务') }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.ops { display: flex; flex-direction: column; gap: 14px; }

.drop {
  position: relative; min-height: 232px; display: flex; flex-direction: column;
  align-items: center; justify-content: center; gap: 6px;
  border: 1.5px dashed #dfe0ec; border-radius: 12px; background: #fbfbfe;
  cursor: pointer; transition: border-color .18s, background .18s;
  text-align: center; color: var(--text-3);
}
.drop:hover { border-color: var(--indigo-400); background: #f4f5fd; }
.drop.filled { padding: 0; overflow: hidden; border-style: solid; border-color: var(--line); cursor: default; }
.drop-icon { font-size: 36px; margin-bottom: 4px; }
.drop b { font-size: 13.5px; color: var(--text); font-weight: 600; }
.drop > span { font-size: 11.5px; }
.preview { width: 100%; max-height: 232px; display: block; background: #10160f; }
.file-chip {
  position: absolute; left: 8px; right: 8px; bottom: 8px;
  background: rgba(16, 18, 30, .72); color: #fff; border-radius: 8px;
  font-size: 11.5px; padding: 6px 10px; backdrop-filter: blur(6px);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}

.field-row { display: flex; flex-direction: column; gap: 7px; }
.field-head { display: flex; justify-content: space-between; font-size: 12.5px; color: var(--text-2); }
.field-head b {
  color: var(--indigo-600); font-family: var(--mono); font-size: 12px;
  background: var(--indigo-50); border-radius: 6px; padding: 1px 7px;
}
.field-row input[type=range] { width: 100%; accent-color: var(--indigo-500); cursor: pointer; }

.progress-box { background: #f5f6fc; border: 1px solid #e6e8f6; border-radius: 10px; padding: 11px 13px; }
.prog-top { display: flex; justify-content: space-between; align-items: center; font-size: 12.5px; color: var(--text-2); }
.prog-num { font-family: var(--mono); color: var(--indigo-600); }
.bar { height: 6px; background: #e3e5f2; border-radius: 99px; overflow: hidden; margin: 8px 0 2px; }
.bar i { display: block; height: 100%; border-radius: 99px; background: linear-gradient(90deg, #8f92ee, var(--indigo-600)); transition: width .3s; }
.err { font-size: 11.5px; color: var(--red); margin-top: 6px; }

.actions { display: flex; gap: 10px; }
.btn { height: 40px; border-radius: 10px; font-size: 13px; cursor: pointer; border: 1px solid var(--line); background: #fff; color: var(--text-2); padding: 0 18px; }
.btn.ghost:hover { border-color: var(--indigo-400); color: var(--indigo-600); }
.btn.primary {
  flex: 1; background: linear-gradient(135deg, var(--indigo-500), var(--indigo-600));
  border: 0; color: #fff; font-weight: 600;
  box-shadow: 0 6px 16px -8px rgba(74, 74, 194, .8);
}
.btn.primary:disabled { opacity: .45; box-shadow: none; cursor: not-allowed; }
</style>