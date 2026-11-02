import { reactive } from 'vue'

const state = reactive({ list: [] })
let seq = 0

export function toast(msg, type = 'info', duration = 3200) {
  const id = ++seq
  state.list.push({ id, msg, type })
  setTimeout(() => {
    const i = state.list.findIndex((t) => t.id === id)
    if (i >= 0) state.list.splice(i, 1)
  }, duration)
}
toast.success = (m) => toast(m, 'success')
toast.error = (m) => toast(m, 'error', 4200)
toast.info = (m) => toast(m, 'info')

export const toastState = state
