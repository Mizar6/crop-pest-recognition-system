<script setup>
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import { useImageDetect } from '../../composables/detectImage'
import { severityTone } from '../../components/chartTheme'

const { result, showSource } = useImageDetect()

const displayUrl = computed(() => {
  if (!result.value) return ''
  const u = showSource.value ? result.value.source_url : (result.value.result_url || result.value.source_url)
  return u || ''
})
const sev = computed(() => result.value?.severity || {})
</script>

<template>
  <div v-if="result" class="res">
    <div class="card result-img">
      <div class="card-title">
        {{ showSource ? '原图' : '标注结果' }}
        <div class="toggle" v-if="result.result_url && result.source_url">
          <button :class="{ on: !showSource }" @click="showSource = false">标注图</button>
          <button :class="{ on: showSource }" @click="showSource = true">原图</button>
        </div>
      </div>
      <div class="img-wrap"><img :src="displayUrl" alt="识别结果" /></div>
    </div>

    <div class="card card-pad">
      <div class="badges">
        <span class="badge green" v-if="result.record?.top_class">{{ result.record.top_class }}</span>
        <span class="badge blue" v-if="result.record?.top_confidence != null">置信度 {{ (result.record.top_confidence * 100).toFixed(1) }}%</span>
        <span class="badge" :class="severityTone(sev.severity)" v-if="sev.severity">严重程度：{{ sev.severity }}</span>
        <span class="badge" :class="severityTone(sev.risk)" v-if="sev.risk">风险：{{ sev.risk }}</span>
      </div>
      <div class="metrics">
        <div class="m"><i>{{ result.record?.target_count ?? result.boxes?.length ?? 0 }}</i><span>检出目标</span></div>
        <div class="m"><i>{{ sev.ratio != null ? (sev.ratio * 100).toFixed(1) + '%' : '—' }}</i><span>病斑占比</span></div>
        <div class="m"><i>{{ result.record?.cost_ms ?? '—' }}<em>ms</em></i><span>推理耗时</span></div>
      </div>
      <div class="foot-note">
        <span>已存为记录 <b>#{{ result.record_id }}</b></span>
        <RouterLink to="/records">查看记录 →</RouterLink>
      </div>
    </div>

    <div class="card card-pad" v-if="result.knowledge?.length">
      <div class="card-title">图谱关联知识 <span class="sub">一跳事实</span></div>
      <div class="facts">
        <div v-for="(k, i) in result.knowledge" :key="i" class="fact">{{ k }}</div>
      </div>
    </div>

    <div class="card card-pad" v-if="result.boxes?.length">
      <div class="card-title">检出框明细</div>
      <table class="table">
        <thead><tr><th>类别</th><th>置信度</th><th>位置</th></tr></thead>
        <tbody>
          <tr v-for="(b, i) in result.boxes" :key="i">
            <td>{{ b.class_name }}</td>
            <td><span class="badge green">{{ (b.confidence * 100).toFixed(1) }}%</span></td>
            <td class="coords">({{ b.x1 }}, {{ b.y1 }}, {{ b.x2 }}, {{ b.y2 }})</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>

  <div v-else class="empty card">
    <div class="icon">🪴</div>
    左侧上传并识别图片后，这里显示标注图、严重程度与关联知识
  </div>
</template>

<style scoped>
.res { display: flex; flex-direction: column; gap: 14px; }
.result-img .img-wrap {
  background: #10160f; display: flex; align-items: center; justify-content: center;
  min-height: 300px;
}
.result-img img { max-width: 100%; max-height: 520px; width: 100%; object-fit: contain; }
.toggle { display: flex; background: #eef1ec; border-radius: 8px; padding: 2px; gap: 2px; }
.toggle button { border: none; background: transparent; padding: 3px 11px; font-size: 12px; border-radius: 6px; cursor: pointer; color: var(--text-2); }
.toggle button.on { background: #fff; color: var(--indigo-600); font-weight: 600; box-shadow: 0 1px 3px rgba(0,0,0,.1); }
.badges { display: flex; flex-wrap: wrap; gap: 7px; margin-bottom: 14px; }
.metrics { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.m { background: #f6f6fa; border: 1px solid #e9e9f2; border-radius: 10px; padding: 10px 6px; text-align: center; }
.m i { font-style: normal; font-size: 19px; font-weight: 700; color: var(--indigo-700); font-variant-numeric: tabular-nums; }
.m i em { font-style: normal; font-size: 10.5px; color: var(--text-3); margin-left: 1px; }
.m span { display: block; font-size: 11px; color: var(--text-3); margin-top: 3px; }
.foot-note { margin-top: 13px; font-size: 12.5px; color: var(--text-2); display: flex; justify-content: space-between; align-items: center; }
.facts { display: flex; flex-direction: column; gap: 7px; }
.fact { font-size: 12.8px; background: var(--indigo-50); border: 1px solid var(--indigo-100); color: var(--indigo-800); border-radius: 8px; padding: 7px 11px; line-height: 1.55; }
.coords { font-family: var(--mono); font-size: 12px; color: var(--text-3); }
.empty { color: var(--text-3); }
</style>
