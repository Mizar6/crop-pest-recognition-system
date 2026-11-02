<script setup>
import ImageTab from '../components/detect/ImageTab.vue'
import ImageResult from '../components/detect/ImageResult.vue'
</script>

<template>
  <div class="page">
    <div class="page-head">
      <h1>图片识别</h1>
      <p>上传一张叶片照片，右侧显示标注图、严重程度与关联知识。</p>
    </div>

    <div class="split">
      <section class="col col--ops">
        <div class="card ops-block">
          <div class="block-head"><b>识别区</b><span class="b-sub">参数与提交</span></div>
          <ImageTab />
        </div>
      </section>

      <section class="col col--res">
        <div class="res-head"><b>结果区</b></div>
        <ImageResult />
      </section>
    </div>
  </div>
</template>

<style scoped>
.split { display: grid; grid-template-columns: 380px minmax(0, 1fr); gap: 18px; align-items: start; }
.col--ops { min-width: 0; }
.ops-block { padding: 14px; }
.block-head { display: flex; align-items: center; padding-bottom: 10px; margin-bottom: 12px; border-bottom: 1px solid var(--line); }
.block-head b { font-size: 14px; color: var(--text); }
.b-sub { margin-left: auto; font-size: 11.5px; color: var(--text-3); }
.col--res { display: flex; flex-direction: column; gap: 12px; min-width: 0; }
.res-head { background: #fff; border: 1px solid var(--line); border-radius: var(--radius); padding: 10px 14px; }
.res-head b { font-size: 14px; color: var(--text); }
@media (max-width: 1180px) { .split { grid-template-columns: 1fr; } }
</style>