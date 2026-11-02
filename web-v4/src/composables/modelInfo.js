// 当前生效模型信息（全局单例）：切换模型后所有页面同步刷新
import { ref } from 'vue'
import api from '../api/client'

const info = ref(null)      // { model_name, file, class_num, imgsz, classes }
const loading = ref(false)
const error = ref('')

async function refresh() {
  loading.value = true
  error.value = ''
  try {
    info.value = await api.detectModel()
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
  return info.value
}

function label() {
  const i = info.value
  if (!i) return '模型加载中'
  const name = i.model_name || i.name || i.file || 'YOLO 模型'
  const cls = i.class_num ?? i.classes?.length
  return cls ? `${name} · ${cls} 类` : name
}

export function useModelInfo() {
  return { info, loading, error, refresh, label }
}
