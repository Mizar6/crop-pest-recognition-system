// 统一接口层
// 约定：响应 { code, msg, data }；业务错误也是 HTTP 200，必须判 code
// /api 与 /uploads 走 vite 代理到 127.0.0.1:8001

async function req(path, opts = {}) {
  const res = await fetch(path, opts)
  if (!res.ok) {
    let msg = `HTTP ${res.status}`
    try {
      const j = await res.json()
      if (j && j.msg) msg = j.msg
    } catch {}
    const err = new Error(msg)
    err.code = res.status
    throw err
  }
  const json = await res.json()
  if (!json || json.code !== 200) {
    const err = new Error((json && json.msg) || '接口返回异常')
    err.code = json ? json.code : 0
    throw err
  }
  return json.data
}

const enc = encodeURIComponent
const post = (path, body, headers) => req(path, { method: 'POST', body, headers })
const del = (path) => req(path, { method: 'DELETE' })

export const api = {
  // ── 健康检查（/ 未被 vite 代理，直连后端；CORS 已全开）──
  health: () => req('http://127.0.0.1:8001/'),

  // ── 检测 ──
  detectModel: () => req('/api/detect/model'),
  detectImage: (fd) => post('/api/detect/image', fd),
  detectVideo: (fd) => post('/api/detect/video', fd),
  videoProgress: (taskId) => req(`/api/detect/video/progress?task_id=${enc(taskId)}`),

  // ── 检测记录 ──
  recordPage: (p = {}) => {
    const qs = new URLSearchParams()
    qs.set('page', p.page ?? 1)
    qs.set('page_size', p.pageSize ?? 10)
    if (p.detectType) qs.set('detect_type', p.detectType)
    if (p.keyword) qs.set('keyword', p.keyword)
    return req(`/api/record/page?${qs}`)
  },
  recordDetail: (id) => req(`/api/record/${enc(id)}`),
  recordDelete: (id) => del(`/api/record/${enc(id)}`),
  recordExportUrl: '/api/record/export/excel',

  // ── 统计 ──
  statsOverview: () => req('/api/stats/overview'),
  statsTrend: (days = 14) => req(`/api/stats/trend?days=${days}`),
  statsTopClass: (limit = 10) => req(`/api/stats/top-class?limit=${limit}`),
  statsTypeRatio: () => req('/api/stats/type-ratio'),
  statsLatest: () => req('/api/stats/latest'),

  // ── AI 问答 ──
  chatHistory: (sessionId) => req(`/api/chat/history?session_id=${enc(sessionId)}`),
  chatClear: (sessionId) => del(`/api/chat/session/${enc(sessionId)}`),
  chatAsr: (fd) => post('/api/chat/asr', fd),
  chatSessions: () => req('/api/chat/sessions'),
  chatNewSession: (title) => post('/api/chat/sessions', JSON.stringify({ title }), { 'Content-Type': 'application/json' }),
  chatRenameSession: (id, title) => req('/api/chat/sessions/' + id, { method: 'PATCH', body: JSON.stringify({ title }), headers: { 'Content-Type': 'application/json' } }),
  chatDeleteSession: (id) => del('/api/chat/sessions/' + id),

  // ── 图鉴 ──
  libraryList: (q = '', crop = '', page = 1, size = 24) => req(`/api/library/list?q=${enc(q)}&crop=${enc(crop)}&page=${page}&size=${size}`),
  libraryDetail: (id) => req(`/api/library/${enc(id)}`),

  // ── 药剂 ──
  pesticideList: (q = '', page = 1, size = 24) => req(`/api/pesticide/list?q=${enc(q)}&page=${page}&size=${size}`),
  pesticideDetail: (name) => req(`/api/pesticide/${enc(name)}`),

  // ── 洞察 ──
  insight: () => req('/api/insight'),

  // ── 知识库 ──
  kbStats: () => req('/api/kb/stats'),
  kbDocuments: () => req('/api/kb/documents'),
  kbUpload: (fd) => post('/api/kb/upload', fd),
  kbDelete: (id) => del(`/api/kb/documents/${enc(id)}`),

  // ── 知识图谱 ──
  graphAll: () => req('/api/graph'),
  graphQuery: (q) => req(`/api/graph/query?q=${enc(q)}`),
  graphExtract: (docId = '', limit = 40) => {
    const qs = new URLSearchParams({ limit })
    if (docId) qs.set('doc_id', docId)
    return post(`/api/graph/extract?${qs}`)
  },

  // ── 模型管理 ──
  modelList: () => req('/api/model/list'),
  modelUpload: (fd) => post('/api/model/upload', fd),
  modelActivate: (id) => post(`/api/model/${enc(id)}/activate`),
  modelDelete: (id) => del(`/api/model/${enc(id)}`),
  trainUpload: (fd) => post('/api/train/datasets', fd),
  trainList: () => req('/api/train/datasets'),
  trainStart: (body) => post('/api/train/start', JSON.stringify(body), { 'Content-Type': 'application/json' }),
  trainTask: (id) => req('/api/train/' + id),
  trainCurves: (id) => req('/api/train/' + id + '/curves'),
  trainCancel: (id) => post('/api/train/' + id + '/cancel'),
}

/**
 * 问答 SSE：POST multipart，逐行解析 text/event-stream
 * onEvent(type, data) 逐事件回调；返回 { abort }
 */
export function chatAskStream({ message, sessionId, conf, file }, onEvent) {
  const fd = new FormData()
  if (message != null && message !== '') fd.append('message', message)
  if (sessionId) fd.append('session_id', sessionId)
  if (conf != null) fd.append('conf', conf)
  if (file) fd.append('file', file)

  const ctrl = new AbortController()
  ;(async () => {
    try {
      const res = await fetch('/api/chat/ask', {
        method: 'POST',
        body: fd,
        signal: ctrl.signal,
        headers: { Accept: 'text/event-stream' }
      })
      if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`)
      const reader = res.body.getReader()
      const decoder = new TextDecoder('utf-8')
      let buf = ''
      for (;;) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        let idx
        while ((idx = buf.indexOf('\n\n')) >= 0) {
          const raw = buf.slice(0, idx)
          buf = buf.slice(idx + 2)
          let eventName = ''
          const dataParts = []
          for (const line of raw.split('\n')) {
            if (line.startsWith('event:')) eventName = line.slice(6).trim()
            else if (line.startsWith('data:')) dataParts.push(line.slice(5).trim())
          }
          if (!dataParts.length) continue
          const dataLine = dataParts.join('\n')
          let payload = dataLine
          try {
            payload = JSON.parse(dataLine)
          } catch {
            payload = dataLine
          }
          onEvent(eventName || 'token', payload)
        }
      }
      onEvent('__end__', null)
    } catch (e) {
      if (e.name !== 'AbortError') onEvent('error', String(e.message || e))
      onEvent('__end__', null)
    }
  })()
  return { abort: () => ctrl.abort() }
}

export default api
