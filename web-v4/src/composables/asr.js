// 录音 → 16kHz 单声道 WAV（后端 ASR 要求 WAV 16k）
export async function recordWav({ onStart, onStop } = {}) {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
  const ctx = new AudioContext()
  // 浏览器采样率降到 16k
  await ctx.audioWorklet === null // noop, 部分浏览器需要
  const source = ctx.createMediaStreamSource(stream)

  // 用 ScriptProcessor 采集（兼容性最好）
  const processor = ctx.createScriptProcessor(4096, 1, 1)
  const chunks = []
  processor.onaudioprocess = (e) => {
    chunks.push(new Float32Array(e.inputBuffer.getChannelData(0)))
  }
  source.connect(processor)
  processor.connect(ctx.destination)

  onStop && onStop()
  onStart && onStart()

  let stopped = false
  const stop = async () => {
    if (stopped) return
    stopped = true
    processor.disconnect()
    source.disconnect()
    stream.getTracks().forEach((t) => t.stop())

    // 合并
    const total = chunks.reduce((n, c) => n + c.length, 0)
    const pcm = new Float32Array(total)
    let off = 0
    for (const c of chunks) { pcm.set(c, off); off += c.length }

    // 重采样到 16k
    const ratio = ctx.sampleRate / 16000
    const outLen = Math.floor(pcm.length / ratio)
    const out = new Float32Array(outLen)
    for (let i = 0; i < outLen; i++) {
      const pos = i * ratio
      const i0 = Math.floor(pos)
      const frac = pos - i0
      const a = pcm[i0] ?? 0
      const b = pcm[i0 + 1] ?? a
      out[i] = a + (b - a) * frac
    }

    const blob = encodeWav(out, 16000)
    ctx.close()
    return blob
  }
  return stop
}

function encodeWav(samples, sampleRate) {
  const buffer = new ArrayBuffer(44 + samples.length * 2)
  const view = new DataView(buffer)
  const w = (offset, s) => { for (let i = 0; i < s.length; i++) view.setUint8(offset + i, s.charCodeAt(i)) }
  w(0, 'RIFF'); view.setUint32(4, 36 + samples.length * 2, true); w(8, 'WAVE')
  w(12, 'fmt '); view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true)
  view.setUint32(24, sampleRate, true); view.setUint32(28, sampleRate * 2, true)
  view.setUint16(32, 2, true); view.setUint16(34, 16, true)
  w(36, 'data'); view.setUint32(40, samples.length * 2, true)
  let off = 44
  for (let i = 0; i < samples.length; i++, off += 2) {
    const s = Math.max(-1, Math.min(1, samples[i]))
    view.setInt16(off, s < 0 ? s * 0x8000 : s * 0x7fff, true)
  }
  return new Blob([view], { type: 'audio/wav' })
}
