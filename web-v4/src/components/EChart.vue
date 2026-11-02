<script setup>
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  option: { type: Object, required: true },
  height: { type: String, default: '300px' }
})
const emit = defineEmits(['ready', 'click'])

const el = ref(null)
let chart = null
let ro = null

function render() {
  if (!el.value) return
  if (!chart) chart = echarts.init(el.value)
  // notMerge=true：布局切换不留旧坐标
  chart.setOption(props.option, true)
}

onMounted(() => {
  render()
  chart.on('click', (p) => emit('click', p))
  emit('ready', chart)
  el.value.__chart = chart // 调试句柄
  ro = new ResizeObserver(() => chart && chart.resize())
  ro.observe(el.value)
})
onBeforeUnmount(() => {
  ro && ro.disconnect()
  chart && chart.dispose()
  chart = null
})
watch(() => props.option, render, { deep: true })
</script>

<template>
  <div ref="el" :style="{ height, width: '100%' }"></div>
</template>
