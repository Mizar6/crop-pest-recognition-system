<script setup>
import { ref } from 'vue'
import { useImageDetect } from '../../composables/detectImage'

const { file, previewUrl, conf, loading, pick, submit, reset } = useImageDetect()
const fileInput = ref(null)
const dragOver = ref(false)

function onDrop(e) {
  dragOver.value = false
  pick(e.dataTransfer.files?.[0])
}
</script>

<template>
  <div class="ops">
    <div
      class="drop" :class="{ over: dragOver, filled: !!previewUrl }"
      @click="!previewUrl && fileInput.click()"
      @dragover.prevent="dragOver = true" @dragleave="dragOver = false" @drop.prevent="onDrop"
    >
      <input ref="fileInput" type="file" accept="image/*" hidden @change="e => pick(e.target.files[0])" />
      <template v-if="!previewUrl">
        <div class="drop-icon">🖼️</div>
        <b>点击或拖拽叶片图片</b>
        <span>jpg / png / bmp / webp · ≤ 20MB</span>
      </template>
      <template v-else>
        <img :src="previewUrl" alt="预览" />
        <div class="file-chip">{{ file.name }} · {{ (file.size / 1024).toFixed(0) }} KB</div>
      </template>
    </div>

    <div class="field-row">
      <div class="field-head">
        <span>置信度阈值</span>
        <b>{{ conf.toFixed(2) }}</b>
      </div>
      <input type="range" min="0.05" max="0.95" step="0.05" v-model.number="conf" />
    </div>

    <div class="actions">
      <button v-if="previewUrl" class="btn ghost" @click="reset">重选</button>
      <button class="btn primary" :disabled="!previewUrl || loading" @click="submit">
        {{ loading ? '识别中…' : '开始识别' }}
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
  cursor: pointer; transition: border-color .18s, background .18s, transform .18s;
  text-align: center; color: var(--text-3);
}
.drop:hover, .drop.over { border-color: var(--indigo-400); background: #f4f5fd; }
.drop.over { transform: scale(.995); }
.drop.filled { padding: 0; overflow: hidden; border-style: solid; border-color: var(--line); cursor: default; }
.drop img { width: 100%; max-height: 240px; object-fit: contain; display: block; background: #f1f1f7; }
.drop-icon { font-size: 36px; margin-bottom: 4px; }
.drop b { font-size: 13.5px; color: var(--text); font-weight: 600; }
.drop > span { font-size: 11.5px; }
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

.actions { display: flex; gap: 10px; }
.btn { height: 40px; border-radius: 10px; font-size: 13px; cursor: pointer; border: 1px solid var(--line); background: #fff; color: var(--text-2); padding: 0 18px; }
.btn.ghost:hover { border-color: var(--indigo-400); color: var(--indigo-600); }
.btn.primary {
  flex: 1; background: linear-gradient(135deg, var(--indigo-500), var(--indigo-600));
  border: 0; color: #fff; font-weight: 600; letter-spacing: .02em;
  box-shadow: 0 6px 16px -8px rgba(74, 74, 194, .8);
}
.btn.primary:disabled { opacity: .45; box-shadow: none; cursor: not-allowed; }
</style>