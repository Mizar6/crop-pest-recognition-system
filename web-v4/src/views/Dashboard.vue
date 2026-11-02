<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api/client'
import EChart from '../components/EChart.vue'
import StatCard from '../components/StatCard.vue'
import { textStyle, categoryAxis, valueAxis, tooltipStyle, severityTone } from '../components/chartTheme'
import { toast } from '../composables/toast'

const router = useRouter()
const loading = ref(true)
const overview = ref({})
const days = ref(14)
const trend = ref({ labels: [], values: [] })
const topClass = ref([])
const typeRatio = ref([])
const latest = ref([])

const trendOption = computed(() => ({
  textStyle,
  tooltip: { trigger: 'axis', ...tooltipStyle },
  grid: { left: 40, right: 16, top: 24, bottom: 28 },
  xAxis: { type: 'category', data: trend.value.labels, ...categoryAxis, boundaryGap: false },
  yAxis: { type: 'value', minInterval: 1, ...valueAxis },
  series: [{
    type: 'line', data: trend.value.values, smooth: true,
    symbol: 'circle', symbolSize: 7,
    lineStyle: { width: 3, color: '#8c3a1e' },
    itemStyle: { color: '#8c3a1e', borderColor: '#fff', borderWidth: 2 },
    areaStyle: {
      color: {
        type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
        colorStops: [
          { offset: 0, color: 'rgba(90,95,216,.28)' },
          { offset: 1, color: 'rgba(90,95,216,0)' }
        ]
      }
    }
  }]
}))

const topOption = computed(() => {
  const list = [...topClass.value].reverse()
  return {
    textStyle,
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, ...tooltipStyle },
    grid: { left: 110, right: 40, top: 8, bottom: 24 },
    xAxis: { type: 'value', minInterval: 1, ...valueAxis },
    yAxis: { type: 'category', data: list.map((i) => i.name), ...categoryAxis, axisLabel: { ...textStyle, width: 96, overflow: 'truncate' } },
    series: [{
      type: 'bar', data: list.map((i) => i.value), barWidth: 14,
      itemStyle: { borderRadius: [0, 7, 7, 0], color: { type: 'linear', x: 0, y: 0, x2: 1, y2: 0, colorStops: [{ offset: 0, color: '#8c3a1e' }, { offset: 1, color: '#8c3a1e' }] } },
      label: { show: true, position: 'right', color: '#4c5b45', fontSize: 11.5 }
    }]
  }
})

const ratioOption = computed(() => ({
  textStyle,
  tooltip: { trigger: 'item', ...tooltipStyle, formatter: '{b}：{c} 次（{d}%）' },
  legend: { bottom: 0, textStyle, icon: 'circle', itemWidth: 8 },
  series: [{
    type: 'pie', radius: ['48%', '70%'], center: ['50%', '44%'],
    data: typeRatio.value,
    itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
    label: { show: false },
    emphasis: { scaleSize: 6 },
    color: ['#8c3a1e', '#4c5b45', '#4c5b45', '#d97706']
  }]
}))

async function load() {
  loading.value = true
  try {
    const [ov, tr, tc, ratio, lt] = await Promise.all([
      api.statsOverview(),
      api.statsTrend(days.value),
      api.statsTopClass(10),
      api.statsTypeRatio(),
      api.statsLatest()
    ])
    overview.value = ov
    trend.value = tr
    topClass.value = tc
    typeRatio.value = ratio
    latest.value = lt
  } catch (e) {
    toast.error('统计加载失败：' + e.message)
  } finally {
    loading.value = false
  }
}

async function switchDays(d) {
  days.value = d
  try { trend.value = await api.statsTrend(d) } catch (e) { toast.error(e.message) }
}

const typeTone = { image: 'green', video: 'blue', realtime: 'violet' }
const typeText = { image: '图片', video: '视频', realtime: '实时' }

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-head">
      <h1>总览</h1>
      <p>识别量、病害分布与系统运行状况一览</p>
    </div>

    <div v-if="loading" class="loading-row"><span class="spinner"></span>加载统计数据…</div>

    <template v-else>
      <div class="grid stats-grid">
        <StatCard label="今日识别" :value="overview.detect_today ?? 0" icon="📆" tone="green" sub="次" />
        <StatCard label="累计识别" :value="overview.detect_total ?? 0" icon="🔍" tone="blue" sub="次" />
        <StatCard label="检出目标" :value="overview.target_total ?? 0" icon="🍃" tone="amber" sub="个病斑/叶片" />
        <StatCard label="病害类别" :value="overview.class_total ?? 0" icon="🦠" tone="violet" sub="种" />
      </div>

      <div class="grid two">
        <div class="card card-pad">
          <div class="card-title">
            识别趋势
            <div class="seg">
              <button v-for="d in [7, 14, 30]" :key="d" :class="{ on: days === d }" @click="switchDays(d)">{{ d }}天</button>
            </div>
          </div>
          <EChart :option="trendOption" height="280px" />
        </div>

        <div class="card card-pad">
          <div class="card-title">病害 TOP 10 <span class="sub">按检出次数</span></div>
          <EChart v-if="topClass.length" :option="topOption" height="280px" />
          <div v-else class="empty"><div class="icon">🌱</div>暂无检出数据</div>
        </div>
      </div>

      <div class="grid two">
        <div class="card card-pad">
          <div class="card-title">识别方式占比</div>
          <EChart v-if="typeRatio.length" :option="ratioOption" height="260px" />
          <div v-else class="empty"><div class="icon">📊</div>暂无数据</div>
        </div>

        <div class="card card-pad">
          <div class="card-title">
            最近识别
            <a class="btn sm" @click="router.push('/records')">查看全部 →</a>
          </div>
          <div class="latest" v-if="latest.length">
            <div v-for="r in latest" :key="r.id" class="latest-item" @click="router.push('/records')">
              <img v-if="r.source_url" :src="r.source_url" loading="lazy" alt="" />
              <div class="thumb-ph" v-else>🍃</div>
              <div class="info">
                <div class="row1">
                  <span class="badge" :class="typeTone[r.detect_type] || 'gray'">{{ typeText[r.detect_type] || r.detect_type }}</span>
                  <b class="cls">{{ r.top_class || '未检出' }}</b>
                </div>
                <div class="row2">{{ r.source_name }} · {{ r.detect_time }}</div>
              </div>
              <div class="conf" v-if="r.top_confidence != null">{{ (r.top_confidence * 100).toFixed(1) }}%</div>
            </div>
          </div>
          <div v-else class="empty"><div class="icon">📭</div>还没有识别记录，去<RouterLink to="/detect">智能识别</RouterLink>试试</div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.stats-grid { grid-template-columns: repeat(4, 1fr); }
.two { grid-template-columns: 1fr 1fr; margin-top: 0; }
.seg { display: flex; background: #f1ece0; border-radius: 9px; padding: 3px; gap: 2px; }
.seg button {
  border: none; background: transparent; padding: 3.5px 12px; font-size: 12px;
  border-radius: 7px; cursor: pointer; color: var(--text-2); transition: all .15s;
}
.seg button.on { background: #fff; color: var(--indigo-600); font-weight: 600; box-shadow: 0 1px 4px rgba(0,0,0,.08); }

.latest { display: flex; flex-direction: column; max-height: 260px; overflow-y: auto; }
.latest-item {
  display: flex; align-items: center; gap: 12px; padding: 8px 6px;
  border-radius: 10px; cursor: pointer; transition: background .12s;
}
.latest-item:hover { background: #f9f6ee; }
.latest-item img, .thumb-ph {
  width: 52px; height: 40px; border-radius: 8px; object-fit: cover; flex-shrink: 0;
  background: var(--indigo-50); display: flex; align-items: center; justify-content: center;
  border: 1px solid var(--line);
}
.thumb-ph { font-size: 18px; }
.info { flex: 1; min-width: 0; }
.row1 { display: flex; align-items: center; gap: 8px; }
.cls { font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.row2 { font-size: 11.5px; color: var(--text-3); margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.conf { font-size: 13px; font-weight: 600; color: var(--indigo-600); font-variant-numeric: tabular-nums; }
@media (max-width: 1100px) {
  .stats-grid { grid-template-columns: repeat(2, 1fr); }
  .two { grid-template-columns: 1fr; }
}
</style>
