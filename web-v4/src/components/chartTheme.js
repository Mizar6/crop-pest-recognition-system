// ECharts 公共样式片段（档案册：纸张 + 赭红 + 橄榄）
export const textStyle = {
  color: '#6f6c5f',
  fontSize: 12,
  fontFamily: "'Noto Serif SC', 'Songti SC', 'Microsoft YaHei', serif"
}

export const categoryAxis = {
  axisLine: { lineStyle: { color: '#cfc7b4' } },
  axisTick: { show: false },
  axisLabel: textStyle,
  splitLine: { show: false }
}

export const valueAxis = {
  axisLine: { show: false },
  axisTick: { show: false },
  axisLabel: textStyle,
  splitLine: { lineStyle: { color: '#e8e2d2' } }
}

export const tooltipStyle = {
  backgroundColor: '#fffdf8',
  borderColor: '#e2ddce',
  borderWidth: 1,
  textStyle: { color: '#1b1a15', fontSize: 12.5 },
  extraCssText: 'border-radius: 0; box-shadow: 0 10px 30px -14px rgba(27,26,21,.35);'
}

// 赭红为主动色，橄榄、赭石、墨灰为辅
export const palette = ['#8c3a1e', '#4c5b45', '#a9772f', '#6b6a5e', '#b0765a', '#7a8a63', '#8e4b2f', '#3f4a38']

// 严重程度徽章色（轻 / 中 / 重）
export const severityTone = (s) => (s === '重' ? 'red' : s === '中' ? 'amber' : s === '轻' ? 'green' : 'gray')
// 风险等级徽章色
export const riskTone = (r) => (['极高', '高'].includes(r) ? 'red' : r === '中' ? 'amber' : r === '低' ? 'green' : 'gray')
