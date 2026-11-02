<script setup>
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import api, { chatAskStream } from '../api/client'
import { toast } from '../composables/toast'
import { renderMd } from '../composables/md'
import { recordWav } from '../composables/asr'

const SESSION_KEY = 'hejian_session_id'
const sessionId = ref(localStorage.getItem(SESSION_KEY) || '')
const sessions = ref([])
const showSessions = ref(true)
const renaming = ref('')
const renameText = ref('')

const messages = ref([])
const input = ref('')
const attached = ref(null)
const attachPreview = ref('')
const sending = ref(false)
const streaming = ref(false)
const gotTokens = ref(false)
const pipeline = ref({ intent: null, detection: null })
const stage = ref('')
const toolStage = ref('')
const listEl = ref(null)
const detectInfo = ref(null)

const recording = ref(false)
const recSeconds = ref(0)
let stopRec = null
let recTimer = null

const canSend = computed(() => !sending.value && (!!input.value.trim() || !!attached.value))

function now() {
  return new Date().toLocaleTimeString('zh-CN', { hour12: false, hour: '2-digit', minute: '2-digit' })
}

function scrollBottom() {
  nextTick(() => {
    if (listEl.value) listEl.value.scrollTop = listEl.value.scrollHeight
  })
}

/* ── 会话 ─────────────────────────────── */
async function loadSessions() {
  try {
    const d = await api.chatSessions()
    sessions.value = d.items || []
    const cur = sessions.value.find((s) => s.id === sessionId.value)
    if (cur) sessionId.value = cur.id
  } catch {
    /* 后端未起时静默 */
  }
}

async function ensureSession() {
  if (sessionId.value) return sessionId.value
  try {
    const r = await api.chatNewSession('新对话')
    sessionId.value = r.id
    localStorage.setItem(SESSION_KEY, r.id)
    await loadSessions()
  } catch {}
  return sessionId.value
}

async function newSession() {
  if (sending.value) return toast.error('请等当前回答完成')
  try {
    const r = await api.chatNewSession('新对话')
    sessionId.value = r.id
    localStorage.setItem(SESSION_KEY, r.id)
    messages.value = []
    await loadSessions()
    toast.success('已新建对话')
  } catch (e) {
    toast.error(e.message)
  }
}

async function switchSession(id) {
  if (sending.value) return toast.error('请等当前回答完成')
  if (id === sessionId.value) return
  sessionId.value = id
  localStorage.setItem(SESSION_KEY, id)
  messages.value = []
  await loadHistory()
}

function startRename(s) {
  renaming.value = s.id
  renameText.value = s.title
}

async function commitRename(s) {
  const title = renameText.value.trim()
  renaming.value = ''
  if (!title || title === s.title) return
  try {
    await api.chatRenameSession(s.id, title)
    await loadSessions()
  } catch (e) {
    toast.error(e.message)
  }
}

async function removeSession(s) {
  if (!confirm(`确定删除对话「${s.title || '新对话'}」及其全部消息吗？`)) return
  try {
    await api.chatDeleteSession(s.id)
    if (s.id === sessionId.value) {
      messages.value = []
      sessionId.value = ''
      localStorage.removeItem(SESSION_KEY)
    }
    await loadSessions()
  } catch (e) {
    toast.error(e.message)
  }
}

async function loadHistory() {
  if (!sessionId.value) return
  try {
    const h = await api.chatHistory(sessionId.value)
    messages.value = (h || []).map((m) => ({
      role: m.role === 'ai' || m.role === 'assistant' ? 'assistant' : 'user',
      content: m.content,
      time: m.time || ''
    }))
    scrollBottom()
  } catch {}
}

/* ── 附件 ─────────────────────────────── */
function pickFile(f) {
  if (!f) return
  if (!/^image\//.test(f.type) && !/\.(jpe?g|png|bmp|webp)$/i.test(f.name)) {
    return toast.error('仅支持图片附件')
  }
  if (f.size > 20 * 1024 * 1024) return toast.error('图片不能超过 20MB')
  attached.value = f
  if (attachPreview.value) URL.revokeObjectURL(attachPreview.value)
  attachPreview.value = URL.createObjectURL(f)
}

function removeAttach() {
  attached.value = null
  if (attachPreview.value) URL.revokeObjectURL(attachPreview.value)
  attachPreview.value = ''
}

/* ── 语音 ─────────────────────────────── */
async function toggleRec() {
  if (recording.value) {
    recording.value = false
    clearInterval(recTimer)
    const blob = stopRec ? await stopRec() : null
    if (!blob || blob.size < 2000) return toast.error('录音太短，请重试')
    try {
      const fd = new FormData()
      fd.append('file', blob, 'voice.wav')
      const r = await api.chatAsr(fd)
      if (r?.text) input.value = (input.value + ' ' + r.text).trim()
      else toast.error('没听清，请再说一次')
    } catch (e) {
      toast.error('语音识别失败：' + e.message)
    }
    return
  }
  try {
    recSeconds.value = 0
    stopRec = await recordWav({
      onStart: () => {
        recording.value = true
        recTimer = setInterval(() => { recSeconds.value += 1 }, 1000)
      }
    })
  } catch (e) {
    toast.error('无法打开麦克风：' + e.message)
  }
}

/* ── 发送 ─────────────────────────────── */
// ── 打字机：把上游的块状 token 平滑成逐字出现 ──
let pendingText = ''
let typer = null
let typerTarget = null

function startTypewriter() {
  if (typer) return
  typer = setInterval(() => {
    if (!typerTarget) return
    if (!pendingText) return
    // 每次吐 1 个字符，间隔 33ms ≈ 每秒 30 字
    const step = pendingText.length > 120 ? 3 : pendingText.length > 40 ? 2 : 1
    typerTarget.content += pendingText.slice(0, step)
    pendingText = pendingText.slice(step)
    scrollBottom()
  }, 33)
}

function stopTypewriter() {
  if (typer) { clearInterval(typer); typer = null }
}

async function send() {
  const text = input.value.trim()
  if ((!text && !attached.value) || sending.value) return
  await ensureSession()

  messages.value.push({
    role: 'user',
    content: text || '（请看这张叶片图片）',
    imageUrl: attachPreview.value,
    time: now()
  })
  input.value = ''
  const file = attached.value
  attached.value = null
  attachPreview.value = ''

  sending.value = true
  streaming.value = true
  gotTokens.value = false
  toolStage.value = ''
  pipeline.value = { intent: null, detection: null }
  stage.value = '判断问题中…'

  const reply = reactive({ role: 'assistant', content: '', time: now(), pipeline: null })
  typerTarget = reply
  pendingText = ''
  stopTypewriter()
  let pushed = false

  chatAskStream({ message: text, sessionId: sessionId.value, conf: 0.25, file }, (type, data) => {
    switch (type) {
      case 'meta':
        if (data?.session_id) {
          sessionId.value = data.session_id
          localStorage.setItem(SESSION_KEY, data.session_id)
        }
        if (data?.intent) pipeline.value.intent = data.intent
        break
      case 'detection':
        pipeline.value.detection = data === null ? 'none' : data
        break
      case 'tool':
        if (data?.status === 'running') {
          toolStage.value = data.name === 'get_weather' ? '查询天气' : '读取网页'
          stage.value = toolStage.value
        } else {
          toolStage.value = ''
        }
        break
      case 'token': {
        if (!pushed) {
          messages.value.push(reply)
          pushed = true
          gotTokens.value = true
        }
        // 上游一次给 2~16 字，先入缓冲，由打字机匀速吐出，视觉上才像逐字输出
        pendingText += data?.text ?? data ?? ''
        startTypewriter()
        stage.value = ''
        break
      }
      case 'error': {
        if (!pushed) {
          messages.value.push(reply)
          pushed = true
        }
        reply.content += `\n\n⚠️ ${data?.text ?? data}`
        stage.value = ''
        break
      }
      case 'done':
        reply.pipeline = { ...pipeline.value }
        break
      case '__end__':
        // 把缓冲里剩下的字全部吐完再收尾
        if (typerTarget && pendingText) {
          typerTarget.content += pendingText
          pendingText = ''
        }
        stopTypewriter()
        typerTarget = null
        streaming.value = false
        sending.value = false
        stage.value = ''
        toolStage.value = ''
        loadSessions()
        scrollBottom()
        break
    }
  })
}

function stopGen() {
  streaming.value = false
  sending.value = false
  stage.value = ''
  toast.info('已停止生成')
}

onMounted(async () => {
  await loadSessions()
  if (sessionId.value) await loadHistory()
  try {
    detectInfo.value = await api.detectModel()
  } catch {}
})
</script>
<template>
  <div class="chat-page">
    <!-- 左：会话（档案索引） -->
    <aside class="index" :class="{ open: showSessions }">
      <div class="index-head">
        <span class="mono">CONVERSATIONS</span>
        <button class="ghost-sm" @click="newSession">＋</button>
      </div>
      <div class="index-list">
        <button
          v-for="s in sessions" :key="s.id"
          class="entry" :class="{ on: s.id === sessionId }"
          @click="switchSession(s.id)"
        >
          <template v-if="renaming === s.id">
            <input v-model="renameText" class="entry-input" @click.stop
                   @keyup.enter="commitRename(s)" @blur="commitRename(s)" />
          </template>
          <template v-else>
            <span class="entry-title">{{ s.title || '新对话' }}</span>
            <span class="entry-ops">
              <button class="mini" title="重命名" @click.stop="startRename(s)">✎</button>
              <button class="mini" title="删除" @click.stop="removeSession(s)">✕</button>
            </span>
          </template>
        </button>
        <p v-if="!sessions.length" class="index-empty">还没有对话</p>
      </div>
    </aside>

    <!-- 右：对话主体 -->
    <main class="thread">
      <header class="thread-head">
        <button class="burger" title="对话列表" @click="showSessions = !showSessions">☰</button>
        <div class="titles">
          <h1>植保问答</h1>
          <p class="mono">SPECIMEN · {{ messages.length ? `共 ${messages.length} 条` : '未开始' }}</p>
        </div>
      </header>

      <div ref="listEl" class="records">
        <!-- 空态 -->
        <div v-if="!messages.length && !streaming" class="starter">
          <div class="starter-mark">禾</div>
          <p class="mono">FIELD CONSULTATION</p>
          <h2>把症状说清楚，我来判断</h2>
          <div class="prompts">
            <button v-for="q in [
              '玉米叶片出现黄褐色条纹斑是什么病？',
              '番茄晚疫病该用什么药防治？',
              '如何预防苹果锈病？'
            ]" :key="q" class="prompt" @click="input = q">{{ q }}</button>
          </div>
        </div>

        <!-- 记录 -->
        <article v-for="(m, i) in messages" :key="i" class="record" :class="m.role">
          <div class="record-meta">
            <span class="mono">{{ m.role === 'user' ? 'ASK' : 'ANSWER' }}</span>
            <span class="dot"></span>
            <span class="mono time">{{ m.time }}</span>
          </div>

          <div class="record-body">
            <div v-if="m.pipeline" class="traces">
              <span v-if="m.pipeline.intent" class="trace">
                {{ m.pipeline.intent.intent === 'diagnosis' ? '病害诊断' : '知识咨询' }}
              </span>
              <span v-if="m.pipeline.detection && m.pipeline.detection !== 'none'" class="trace trace--det">
                {{ m.pipeline.detection.class_name }}
                {{ (m.pipeline.detection.confidence * 100).toFixed(0) }}%
              </span>
            </div>

            <img v-if="m.imageUrl" :src="m.imageUrl" class="attach" alt="附件" />

            <div v-if="m.role === 'assistant'" class="prose" v-html="renderMd(m.content)"></div>
            <p v-else class="said">{{ m.content }}</p>
          </div>
        </article>

        <!-- 思考中 -->
        <article v-if="streaming && !gotTokens" class="record assistant">
          <div class="record-meta"><span class="mono">WORKING</span></div>
          <div class="record-body">
            <div class="steps">
              <div class="step" :class="{ done: pipeline.intent }">
                <i></i><span>判断问题类型</span>
                <em v-if="pipeline.intent">{{ pipeline.intent.intent === 'diagnosis' ? '病害诊断' : '知识咨询' }}</em>
              </div>
              <div class="step" :class="{ done: pipeline.detection !== null }"
                   v-if="pipeline.intent?.intent === 'diagnosis' || (pipeline.detection && pipeline.detection !== 'none')">
                <i></i><span>识别叶片</span>
                <em v-if="pipeline.detection && pipeline.detection !== 'none'">
                  {{ pipeline.detection.class_name }} · {{ (pipeline.detection.confidence * 100).toFixed(0) }}%
                </em>
                <em v-else class="pending">分析中</em>
              </div>
              <div class="step" :class="{ done: !!toolStage }">
                <i></i><span>调用工具</span>
                <em v-if="toolStage">{{ toolStage }}</em>
              </div>
            </div>
          </div>
        </article>
      </div>

      <!-- 输入 -->
      <footer class="composer">
        <div v-if="attached" class="pending-attach">
          <img :src="attachPreview" alt="待发送" />
          <button @click="removeAttach">移除</button>
        </div>
        <div class="composer-box">
          <button class="tool" title="上传叶片照片" @click="$refs.file.click()">＋</button>
          <input ref="file" type="file" accept="image/*" hidden @change="pickFile($event.target.files[0])" />
          <button class="tool" :class="{ rec: recording }" title="语音提问" @click="toggleRec">
            {{ recording ? `●${recSeconds}s` : '🎤' }}
          </button>
          <textarea
            v-model="input" rows="1" class="say"
            placeholder="描述症状，或直接提问…"
            @keydown.enter.exact.prevent="send"
          ></textarea>
          <button v-if="streaming" class="send stop" @click="stopGen">停止</button>
          <button v-else class="send" :disabled="!canSend" @click="send">发送</button>
        </div>
        <p class="fineprint">回答由大模型生成，仅供参考；重要防治决策请咨询当地农技站。</p>
      </footer>
    </main>
  </div>
</template>

<style scoped>
/* ── 版式基线 ────────────────────────────────── */
.chat-page {
  --paper: #f5f2ea;
  --card: #fffdf8;
  --ink: #1b1a15;
  --ink-2: #4a473d;
  --muted: #6f6c5f;
  --line: #e2ddce;
  --line-soft: #efeadc;
  --accent: #8c3a1e;
  --indigo: #8c3a1e;

  display: grid;
  grid-template-columns: 244px minmax(0, 1fr);
  gap: 18px;
  height: calc(100vh - 56px);
  padding: 18px 22px 22px;
  background: var(--paper);
}

.mono {
  font-family: ui-monospace, "SFMono-Regular", Consolas, monospace;
  font-size: 9.5px;
  letter-spacing: .18em;
  text-transform: uppercase;
  color: var(--muted);
}

/* ── 左：会话索引 ────────────────────────────── */
.index {
  background: var(--card);
  border: 1px solid var(--line);
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.index-head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 14px 10px;
  border-bottom: 1px solid var(--line-soft);
}
.ghost-sm {
  width: 24px; height: 24px; border: 1px solid var(--line);
  background: transparent; cursor: pointer; color: var(--ink-2);
  font-size: 13px; line-height: 1;
}
.ghost-sm:hover { border-color: var(--accent); color: var(--accent); }

.index-list { overflow-y: auto; padding: 6px; display: flex; flex-direction: column; gap: 2px; }
.entry {
  position: relative; text-align: left; width: 100%;
  border: 0; background: transparent; cursor: pointer;
  padding: 9px 10px; border-left: 2px solid transparent;
  color: var(--ink-2); font-size: 12.5px; line-height: 1.5;
}
.entry:hover { background: #f7f4ec; }
.entry.on { border-left-color: var(--accent); background: #f9f5ec; color: var(--ink); }
.entry-title { display: block; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; padding-right: 34px; }
.entry-ops { position: absolute; right: 6px; top: 8px; display: none; gap: 1px; }
.entry:hover .entry-ops { display: inline-flex; }
.mini {
  border: 0; background: transparent; cursor: pointer;
  font-size: 11px; color: var(--muted); padding: 2px 4px;
}
.mini:hover { color: var(--accent); }
.entry-input {
  width: 100%; border: 1px solid var(--accent); background: #fff;
  padding: 3px 6px; font-size: 12.5px; font-family: inherit;
}
.index-empty { font-size: 12px; color: var(--muted); text-align: center; padding: 16px 0; }

/* ── 右：对话 ────────────────────────────────── */
.thread {
  background: var(--card);
  border: 1px solid var(--line);
  display: flex; flex-direction: column; min-height: 0;
}

.thread-head {
  display: flex; align-items: center; gap: 14px;
  padding: 16px 26px 14px;
  border-bottom: 2px solid var(--ink);
}
.burger {
  width: 28px; height: 28px; border: 1px solid var(--line);
  background: transparent; cursor: pointer; color: var(--ink-2);
  display: none; line-height: 1;
}
.titles h1 {
  font-family: "Noto Serif SC", "Songti SC", serif;
  font-size: 21px; font-weight: 700; letter-spacing: -.01em; color: var(--ink);
  line-height: 1.2;
}
.titles p { margin-top: 5px; }

/* 记录区 */
.records {
  flex: 1; overflow-y: auto;
  padding: 26px 34px 12px;
  display: flex; flex-direction: column; gap: 26px;
  background:
    repeating-linear-gradient(180deg, transparent 0 31px, rgba(0,0,0,.018) 31px 32px);
}

.starter { margin: auto; text-align: center; max-width: 420px; padding: 20px 0; }
.starter-mark {
  width: 54px; height: 54px; margin: 0 auto 18px;
  border: 1.5px solid var(--ink); color: var(--ink);
  font-family: "Noto Serif SC", serif; font-size: 24px;
  display: grid; place-items: center;
}
.starter h2 {
  font-family: "Noto Serif SC", serif; font-size: 19px; font-weight: 600;
  color: var(--ink); margin: 10px 0 20px; letter-spacing: -.01em;
}
.prompts { display: flex; flex-direction: column; gap: 8px; }
.prompt {
  border: 1px solid var(--line); background: #fff;
  padding: 10px 14px; text-align: left; cursor: pointer;
  font-size: 13px; color: var(--ink-2); font-family: inherit;
  transition: border-color .15s, color .15s;
}
.prompt:hover { border-color: var(--accent); color: var(--accent); }

/* 单条记录 */
.record { display: flex; flex-direction: column; gap: 7px; }
.record-meta { display: flex; align-items: center; gap: 8px; }
.record-meta .dot { width: 3px; height: 3px; background: var(--muted); }
.record.user .record-meta { flex-direction: row-reverse; }
.record.user .record-body { align-self: flex-end; text-align: right; }

.record-body { max-width: 76%; }
.record.user .record-body { max-width: 66%; background: #f9f4e6; border: 1px solid #ecdfc0; padding: 12px 16px; }
.record.assistant .record-body {
  border-left: 2px solid var(--accent);
  padding: 2px 0 2px 16px;
}

.traces { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px; }
.trace {
  font-size: 10.5px; color: var(--muted);
  border: 1px solid var(--line-soft); padding: 1px 7px;
}
.trace--det { color: var(--accent); border-color: #e8cdbf; }

.said { font-size: 13.5px; line-height: 1.85; color: var(--ink); white-space: pre-wrap; }
.attach { max-width: 240px; border: 1px solid var(--line); margin-bottom: 8px; }

.prose {
  font-size: 14px; line-height: 1.95; color: var(--ink-2);
}
.prose :deep(p) { margin: 0 0 12px; }
.prose :deep(p:last-child) { margin-bottom: 0; }
.prose :deep(strong) { color: var(--ink); font-weight: 600; }
.prose :deep(ul), .prose :deep(ol) { margin: 6px 0 12px; padding-left: 20px; }
.prose :deep(li) { margin: 3px 0; }
.prose :deep(h1), .prose :deep(h2), .prose :deep(h3) {
  font-family: "Noto Serif SC", serif; color: var(--ink);
  font-size: 15px; margin: 16px 0 8px;
}
.prose :deep(code) {
  font-family: ui-monospace, Consolas, monospace; font-size: 12.5px;
  background: #f5f2ea; padding: 1px 5px;
}

/* 思考步骤 */
.steps { display: flex; flex-direction: column; gap: 7px; }
.step {
  display: flex; align-items: center; gap: 9px;
  font-size: 12.5px; color: var(--muted);
}
.step i {
  width: 6px; height: 6px; border: 1px solid var(--muted);
  border-radius: 50%; flex: none;
}
.step.done { color: var(--ink-2); }
.step.done i { background: var(--accent); border-color: var(--accent); }
.step em { font-style: normal; font-size: 11.5px; color: var(--accent); }
.step em.pending { color: var(--muted); }

/* 输入区 */
.composer { border-top: 1px solid var(--line); padding: 14px 22px 12px; background: var(--card); }
.pending-attach {
  display: flex; align-items: center; gap: 10px; margin-bottom: 10px;
  font-size: 12px; color: var(--muted);
}
.pending-attach img { width: 54px; height: 54px; object-fit: cover; border: 1px solid var(--line); }
.pending-attach button { border: 0; background: none; cursor: pointer; color: var(--accent); font-size: 12px; }

.composer-box {
  display: flex; align-items: flex-end; gap: 8px;
  border: 1px solid var(--line); background: #fff; padding: 8px 10px;
}
.composer-box:focus-within { border-color: var(--accent); }
.tool {
  width: 30px; height: 30px; border: 0; background: transparent;
  cursor: pointer; font-size: 15px; color: var(--muted); flex: none;
}
.tool:hover { color: var(--accent); }
.tool.rec { color: #c0392b; }
.say {
  flex: 1; border: 0; outline: none; resize: none;
  font-family: inherit; font-size: 13.5px; line-height: 1.7;
  color: var(--ink); padding: 6px 2px; max-height: 120px;
  background: transparent;
}
.say::placeholder { color: var(--muted); }
.send {
  height: 32px; padding: 0 18px; border: 0; cursor: pointer;
  background: var(--accent); color: #fff; font-size: 12.5px;
  letter-spacing: .04em; flex: none;
}
.send:hover { background: #6f2d17; }
.send:disabled { background: #cfc6b6; cursor: not-allowed; }
.send.stop { background: #4a473d; }

.fineprint { font-size: 10.5px; color: var(--muted); text-align: center; margin-top: 9px; }

/* 响应式 */
@media (max-width: 1080px) {
  .chat-page { grid-template-columns: minmax(0, 1fr); padding: 12px; }
  .index { display: none; }
  .index.open {
    display: flex; position: fixed; left: 12px; top: 78px; bottom: 12px;
    width: 240px; z-index: 60; box-shadow: 0 8px 28px rgba(0,0,0,.12);
  }
  .burger { display: block; }
  .records { padding: 18px 16px 10px; }
  .record-body { max-width: 100%; }
}

@media (prefers-reduced-motion: reduce) {
  * { transition: none !important; }
}
</style>
