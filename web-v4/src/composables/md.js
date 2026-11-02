// 极简 Markdown 渲染：标题 / 粗体 / 行内代码 / 列表 / 换行（先转义 HTML）
function esc(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

export function renderMd(src) {
  if (!src) return ''
  const lines = esc(src).split('\n')
  const out = []
  let inList = false
  for (const raw of lines) {
    const line = raw
    const li = line.match(/^\s*(?:[-*•]|\d+[.、)] )\s+(.*)$/)
    if (li) {
      if (!inList) { out.push('<ul>'); inList = true }
      out.push(`<li>${inline(li[1])}</li>`)
      continue
    }
    if (inList) { out.push('</ul>'); inList = false }
    const h = line.match(/^(#{1,4})\s+(.*)$/)
    if (h) { out.push(`<h${h[1].length + 2}>${inline(h[2])}</h${h[1].length + 2}>`); continue }
    if (line.trim() === '') { out.push(''); continue }
    out.push(`<p>${inline(line)}</p>`)
  }
  if (inList) out.push('</ul>')
  return out.join('\n')
}

function inline(s) {
  return s
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>')
}
