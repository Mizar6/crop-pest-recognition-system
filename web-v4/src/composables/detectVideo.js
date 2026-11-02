// 视频识别状态（模块级单例）：上传区与结果区共用同一份状态
import { computed, ref } from 'vue'
import api from '../api/client'
import { toast } from './toast'

const file = ref(null)
const previewUrl = ref('')
const conf = ref(0.25)
const task = ref(null) // { taskId, status, progress, result, error }
let pollTimer = null
const BUSY = ['submitting', 'pending', 'running']
const busy = computed(() => !!task.value && BUSY.includes(task.value.status))

function setPreview(f) {
  if (previewUrl.value) { URL.revokeObjectURL(previewUrl.value); previewUrl.value = '' }
  if (f) previewUrl.value = URL.createObjectURL(f)
}

function pick(f) {
  if (!f) return
  if (!/\.(mp4|avi|mov|mkv|wmv)$/i.test(f.name)) {
    toast.error('请选择 mp4 / avi / mov / mkv / wmv 视频')
    return
  }
  file.value = f
  task.value = null
  setPreview(f)
}

function reset() {
  file.value = null
  task.value = null
  setPreview(null)
  if (pollTimer) { clearTimeout(pollTimer); pollTimer = null }
}

async function submit() {
  if (!file.value || task.value) return
  task.value = { taskId: '', status: 'submitting', progress: 0, result: null, error: '' }
  try {
    const fd = new FormData()
    fd.append('file', file.value)
    fd.append('conf', conf.value)
    const { task_id } = await api.detectVideo(fd)
    task.value.taskId = task_id
    task.value.status = 'running'
    poll()
  } catch (e) {
    task.value = { taskId: '', status: 'error', progress: 0, result: null, error: '提交失败：' + e.message }
  }
}

async function poll() {
  if (!task.value?.taskId) return
  try {
    const p = await api.videoProgress(task.value.taskId)
    task.value.status = p.status
    task.value.progress = p.progress ?? 0
    if (p.status === 'done') {
      task.value.result = p
      toast.success('视频识别完成')
      return
    }
    if (p.status === 'error') {
      task.value.status = 'error'
      task.value.error = p.error || '识别失败'
      return
    }
    pollTimer = setTimeout(poll, 1000)
  } catch (e) {
    // 轮询失败时置为 error，恢复按钮，允许重试，避免一直"识别中"
    task.value.status = 'error'
    task.value.error = '查询进度失败：' + e.message + '（可重试）'
  }
}

export function useVideoDetect() {
  return { file, previewUrl, conf, task, busy, pick, submit, reset }
}

export function disposeVideoDetect() {
  if (pollTimer) { clearTimeout(pollTimer); pollTimer = null }
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
}
