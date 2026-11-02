// 实时检测状态（模块级单例）：识别区与结果区共用摄像头、WebSocket 与检出流
import { ref, onBeforeUnmount } from 'vue'

const videoEl = ref(null)
const overlayEl = ref(null)
const captureEl = ref(null)

const running = ref(false)
const wsOk = ref(false)
const saveRecord = ref(false)
const conf = ref(0.3)
const costMs = ref(null)
const fps = ref(0)
const logs = ref([])
const errText = ref('')

const COLORS = ['#5a5fd8', '#0d9488', '#2f6fb2', '#7c5cd6', '#d97706', '#d23632', '#b53fa0', '#5f7d1e']

let ws = null
let stream = null
let loopTimer = null
let busy = false
let respCount = 0
let fpsTimer = null

async function start() {
  errText.value = ''
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 960 }, height: { ideal: 720 } }, audio: false
    })
  } catch (e) {
    errText.value = '无法打开摄像头：' + e.message
    return
  }
  const v = videoEl.value
  if (v) {
    v.srcObject = stream
    await v.play().catch(() => {})
  }

  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  ws = new WebSocket(`${proto}://${location.hostname}:8001/api/detect/realtime`)

  ws.onopen = () => {
    wsOk.value = true
    running.value = true
    busy = false
    scheduleNext(120)
    fpsTimer = setInterval(() => { fps.value = respCount; respCount = 0 }, 1000)
  }

  ws.onmessage = (e) => {
    busy = false
    respCount++
    let data
    try { data = JSON.parse(e.data) } catch { return scheduleNext(80) }
    if (data.code !== 200) return scheduleNext(200)
    costMs.value = data.cost_ms
    drawBoxes(data.boxes || [])
    if (data.boxes?.length) {
      const best = data.boxes.reduce((a, b) => (b.confidence > a.confidence ? b : a))
      logs.value.unshift({
        name: best.class_name,
        conf: best.confidence,
        count: data.boxes.length,
        saved: !!data.record_id,
        time: new Date().toLocaleTimeString('zh-CN', { hour12: false })
      })
      if (logs.value.length > 30) logs.value.pop()
    }
    scheduleNext(70)
  }

  ws.onerror = () => { errText.value = 'WebSocket 连接失败，请确认后端 8001 已启动' }
  ws.onclose = () => {
    wsOk.value = false
    if (running.value) { running.value = false; errText.value = '连接已断开' }
    cleanupLoop()
  }
}

function scheduleNext(delay) {
  loopTimer = setTimeout(sendFrame, delay)
}

function sendFrame() {
  if (!running.value || !ws || ws.readyState !== 1 || busy) return
  const v = videoEl.value
  const c = captureEl.value
  if (!v || !c || !v.videoWidth) return scheduleNext(150)
  if (c.width !== v.videoWidth) {
    c.width = v.videoWidth
    c.height = v.videoHeight
    const ov = overlayEl.value
    if (ov) { ov.width = v.videoWidth; ov.height = v.videoHeight }
  }
  c.getContext('2d').drawImage(v, 0, 0)
  const dataUrl = c.toDataURL('image/jpeg', 0.7)
  busy = true
  try {
    ws.send(JSON.stringify({ image: dataUrl, conf: conf.value, save: saveRecord.value }))
  } catch {
    busy = false
  }
  setTimeout(() => { busy = false }, 3000)
}

function drawBoxes(boxes) {
  const ov = overlayEl.value
  if (!ov) return
  const ctx = ov.getContext('2d')
  ctx.clearRect(0, 0, ov.width, ov.height)
  ctx.font = '600 15px "Microsoft YaHei", sans-serif'
  ctx.textBaseline = 'top'
  boxes.forEach((b, i) => {
    const color = COLORS[(b.class_id ?? i) % COLORS.length]
    ctx.lineWidth = 2.5
    ctx.strokeStyle = color
    ctx.strokeRect(b.x1, b.y1, b.x2 - b.x1, b.y2 - b.y1)
    const label = `${b.class_name} ${(b.confidence * 100).toFixed(0)}%`
    const tw = ctx.measureText(label).width + 12
    const ly = b.y1 > 24 ? b.y1 - 22 : b.y1 + 2
    ctx.fillStyle = color
    ctx.fillRect(b.x1, ly, tw, 22)
    ctx.fillStyle = '#fff'
    ctx.fillText(label, b.x1 + 6, ly + 3)
  })
}

function stop() {
  running.value = false
  cleanupLoop()
  if (ws) { try { ws.close() } catch {} ws = null }
  if (stream) { stream.getTracks().forEach((t) => t.stop()); stream = null }
  wsOk.value = false
  const ov = overlayEl.value
  if (ov) ov.getContext('2d').clearRect(0, 0, ov.width, ov.height)
}

function cleanupLoop() {
  if (loopTimer) { clearTimeout(loopTimer); loopTimer = null }
  if (fpsTimer) { clearInterval(fpsTimer); fpsTimer = null }
}

export function useRealtimeDetect() {
  return { videoEl, overlayEl, captureEl, running, wsOk, saveRecord, conf, costMs, fps, logs, errText, start, stop }
}
