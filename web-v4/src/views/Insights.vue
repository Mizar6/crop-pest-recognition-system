<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '../api/client'
import { toast } from '../composables/toast'
import EChart from '../components/EChart.vue'
import StatCard from '../components/StatCard.vue'
import { textStyle, categoryAxis, valueAxis, tooltipStyle } from '../components/chartTheme'

const loading = ref(true)
const data = ref(null)

const totals = computed(() => data.value?.totals || {})

const cropOption = computed(() => {
  const list = [...(data.value?.crop_coverage || [])].sort((a, b) => b.value - a.value)
  return {
    textStyle,
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, ...tooltipStyle },
    grid: { left: 70, right: 40, top: 8, bottom: 24 },
    xAxis: { type: 'value', minInterval: 1, ...valueAxis },
    yAxis: { type: 'category', data: list.map((i) => i.name).reverse(), ...categoryAxis },
    series: [{
      type: 'bar', data: list.map((i) => i.value).reverse(), barWidth: 13,
      itemStyle: { borderRadius: [0, 7, 7, 0], color: { type: 'linear', x: 0, y: 0, x2: 1, y2: 0, colorStops: [{ offset: 0, color: '#4c5b45' }, { offset: 1, color: '#2f6fb2' }] } },
      label: { show: true, position: 'right', color: '#5c6f57', fontSize: 11.5 }
    }]
  }
})

const catOption = computed(() => ({
  textStyle,
  tooltip: { trigger: 'item', ...tooltipStyle, formatter: '{b}：{c} 类（{d}%）' },
  legend: { bottom: 0, textStyle, icon: 'circle', itemWidth: 8 },
  color: ['#8c3a1e', '#b45309', '#4c5b45'],
  series: [{
    type: 'pie', radius: ['46%', '68%'], center: ['50%', '44%'],
    data: data.value?.categories || [],
    itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
    label: { show: true, formatter: '{b}\n{c}', ...textStyle },
    emphasis: { scaleSize: 5 }
  }]
}))

const trendOption = computed(() => {
  const list = data.value?.query_trend || []
  return {
    textStyle,
    tooltip: { trigger: 'axis', ...tooltipStyle },
    grid: { left: 40, right: 16, top: 24, bottom: 28 },
    xAxis: { type: 'category', data: list.map((i) => i.date), ...categoryAxis, boundaryGap: false },
    yAxis: { type: 'value', minInterval: 1, ...valueAxis },
    series: [{
      type: 'bar', data: list.map((i) => i.count), barWidth: '55%',
      itemStyle: { borderRadius: [6, 6, 0, 0], color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: '#7c5cd6' }, { offset: 1, color: '#b9a5ef' }] } }
    }]
  }
})

const completeness = computed(() => data.value?.completeness || [])
const toneMap = { 概述: 'green', 为害症状: 'blue', 防治方法: 'teal', 发生规律: 'red' }

onMounted(async () => {
  try { data.value = await api.insight() } catch (e) { toast.error(e.message) } finally { loading.value = false }
})
</script>

<template>
  <div class="page">
    <div class="page-head">
      <h1>数据洞察</h1>
      <p>知识库覆盖面、条目完整度与问答查询趋势</p>
    </div>

    <div v-if="loading" class="loading-row"><span class="spinner"></span>加载洞察数据…</div>

    <template v-else-if="data">
      <div class="grid t-grid">
        <StatCard label="病害条目" :value="totals.diseases ?? 0" icon="🦠" tone="red" sub="种" />
        <StatCard label="覆盖作物" :value="totals.crops ?? 0" icon="🌾" tone="green" sub="种" />
        <StatCard label="药剂" :value="totals.pesticides ?? 0" icon="🧪" tone="teal" sub="种" />
        <StatCard label="问答消息" :value="totals.queries ?? 0" icon="💬" tone="violet" sub="条" />
        <StatCard label="识别记录" :value="totals.detects ?? 0" icon="🔍" tone="blue" sub="条" />
      </div>

      <div class="grid two" style="margin-top: 16px">
        <div class="card card-pad">
          <div class="card-title">作物覆盖度 <span class="sub">每种作物的图鉴条目数</span></div>
          <EChart v-if="data.crop_coverage?.length" :option="cropOption" height="330px" />
          <div v-else class="empty"><div class="icon">🌾</div>暂无数据</div>
        </div>
        <div class="card card-pad">
          <div class="card-title">条目类别构成</div>
          <EChart v-if="data.categories?.length" :option="catOption" height="330px" />
          <div v-else class="empty"><div class="icon">📊</div>暂无数据</div>
        </div>
      </div>

      <div class="grid two" style="margin-top: 16px">
        <div class="card card-pad">
          <div class="card-title">字段完整度 <span class="sub">图鉴各字段有值的比例</span></div>
          <div class="comp-list">
            <div v-for="c in completeness" :key="c.name" class="comp-item">
              <div class="comp-head">
                <b>{{ c.name }}</b>
                <span class="badge" :class="toneMap[c.name] || 'gray'">{{ c.rate }}%</span>
              </div>
              <div class="progress" style="margin-top: 8px">
                <i :style="{ width: c.rate + '%', background: c.rate === 0 ? '#e4ebe2' : '' }"></i>
              </div>
              <div class="comp-sub">{{ c.value }} / {{ totals.diseases }} 条</div>
            </div>
          </div>
          <div v-if="completeness.some(c => c.rate === 0)" class="gap-note">
            💡「发生规律」字段暂未收录，属已知数据缺口
          </div>
        </div>
        <div class="card card-pad">
          <div class="card-title">问答查询趋势 <span class="sub">近 14 天消息数</span></div>
          <EChart v-if="data.query_trend?.length" :option="trendOption" height="330px" />
          <div v-else class="empty"><div class="icon">📈</div>暂无数据</div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.t-grid { grid-template-columns: repeat(5, 1fr); }
.two { grid-template-columns: 1fr 1fr; }
.comp-list { display: flex; flex-direction: column; gap: 14px; }
.comp-head { display: flex; justify-content: space-between; align-items: center; }
.comp-head b { font-size: 13.5px; }
.comp-sub { font-size: 11px; color: var(--text-3); margin-top: 4px; }
.gap-note { margin-top: 14px; font-size: 12px; color: var(--amber); background: var(--amber-bg); border-radius: 9px; padding: 9px 13px; }
@media (max-width: 1150px) { .t-grid { grid-template-columns: repeat(3, 1fr); } .two { grid-template-columns: 1fr; } }
</style>
