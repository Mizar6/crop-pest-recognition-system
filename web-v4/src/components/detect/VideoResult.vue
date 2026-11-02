<script setup>
import { RouterLink } from 'vue-router'
import { useVideoDetect } from '../../composables/detectVideo'

const { file, conf, task, reset } = useVideoDetect()
</script>

<template>
  <div v-if="task?.status === 'done' && task.result" class="res">
    <div class="card">
      <div class="card-title">
        标注结果
        <span class="badge green" v-if="task.result.top_class">{{ task.result.top_class }}</span>
      </div>
      <div class="video-wrap">
        <video :src="task.result.result_url" controls playsinline></video>
      </div>
    </div>

    <div class="card card-pad">
      <div class="badges">
        <span class="badge green" v-if="task.result.top_class">{{ task.result.top_class }}</span>
        <span class="badge blue">共 {{ task.result.class_count ?? task.result.classes?.length ?? 0 }} 类</span>
        <span class="badge">记录 #{{ task.result.record_id }}</span>
      </div>
      <div class="metrics">
        <div class="m"><i>{{ task.result.target_count ?? '—' }}</i><span>累计检出</span></div>
        <div class="m"><i>{{ task.result.cost_ms ?? '—' }}<em>ms</em></i><span>总耗时</span></div>
        <div class="m"><i>{{ task.result.class_count ?? task.result.classes?.length ?? 0 }}</i><span>病虫害类别</span></div>
      </div>
      <div class="foot-note">
        <span>源文件：{{ file?.name }}</span>
        <button class="btn sm" @click="task = null; reset()">再识别一个</button>
      </div>
    </div>

    <div class="card card-pad" v-if="task.result.classes?.length">
      <div class="card-title">检出类别明细 <span class="sub">按最高置信度排序</span></div>
      <table class="table">
        <thead><tr><th>类别</th><th>累计次数</th><th>最高置信度</th></tr></thead>
        <tbody>
          <tr v-for="c in task.result.classes" :key="c.class_name">
            <td>{{ c.class_name }}</td>
            <td>{{ c.count }}</td>
            <td><span class="badge green">{{ (c.max_conf * 100).toFixed(1) }}%</span></td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="card card-pad">
      <div class="card-title">任务信息 <span class="sub">异步任务</span></div>
      <div class="facts">
        <div class="fact">task_id：{{ task.taskId }}</div>
        <div class="fact">置信度阈值：{{ conf.toFixed(2) }}</div>
      </div>
    </div>
  </div>

  <div v-else class="empty card">
    <div class="icon">🎞️</div>
    左侧上传并提交视频后，这里显示标注视频与逐类检出统计
  </div>
</template>

<style scoped>
.res { display: flex; flex-direction: column; gap: 14px; }
.video-wrap {
  background: #10160f; display: flex; align-items: center; justify-content: center;
  min-height: 300px;
}
.video-wrap video { max-width: 100%; max-height: 520px; width: 100%; }
.badges { display: flex; flex-wrap: wrap; gap: 7px; margin-bottom: 14px; }
.metrics { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.m { background: #f6f6fa; border: 1px solid #e9e9f2; border-radius: 10px; padding: 10px 6px; text-align: center; }
.m i { font-style: normal; font-size: 19px; font-weight: 700; color: var(--indigo-700); font-variant-numeric: tabular-nums; }
.m i em { font-style: normal; font-size: 10.5px; color: var(--text-3); margin-left: 1px; }
.m span { display: block; font-size: 11px; color: var(--text-3); margin-top: 3px; }
.foot-note { margin-top: 13px; font-size: 12.5px; color: var(--text-2); display: flex; justify-content: space-between; align-items: center; }
.facts { display: flex; flex-direction: column; gap: 7px; }
.fact { font-size: 12.8px; background: var(--indigo-50); border: 1px solid var(--indigo-100); color: var(--indigo-800); border-radius: 8px; padding: 7px 11px; line-height: 1.55; word-break: break-all; }
.empty { color: var(--text-3); }
</style>
