// 图片识别状态（模块级单例）：上传区与结果区共用同一份状态
import { ref, onBeforeUnmount } from 'vue'
import api from '../api/client'
import { toast } from './toast'

const file = ref(null)
const previewUrl = ref('')
const conf = ref(0.25)
const loading = ref(false)
const result = ref(null)
const showSource = ref(false)

function pick(f) {
  if (!f) return
  if (!/\.(jpe?g|png|bmp|webp)$/i.test(f.name) && !/^image\//.test(f.type)) {
    toast.error('请选择 jpg / png / bmp / webp 图片')
    return
  }
  if (f.size > 20 * 1024 * 1024) { toast.error('图片不能超过 20MB'); return }
  file.value = f
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
  previewUrl.value = URL.createObjectURL(f)
  result.value = null
  showSource.value = false
}

async function submit() {
  if (!file.value || loading.value) return
  loading.value = true
  try {
    const fd = new FormData()
    fd.append('file', file.value)
    fd.append('conf', conf.value)
    result.value = await api.detectImage(fd)
  } catch (e) {
    toast.error('识别失败：' + e.message)
  } finally {
    loading.value = false
  }
}

function reset() {
  file.value = null
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
  previewUrl.value = ''
  result.value = null
  showSource.value = false
}

export function useImageDetect() {
  return { file, previewUrl, conf, loading, result, showSource, pick, submit, reset }
}

export function disposeImageDetect() {
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
}
