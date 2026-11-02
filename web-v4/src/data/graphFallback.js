export const graphData = {
  nodes: [
    { id: 'c:corn', name: '玉米', category: 0 },
    { id: 'c:tomato', name: '番茄', category: 0 },
    { id: 'c:apple', name: '苹果', category: 0 },
    { id: 'd:rust', name: '普通锈病', category: 1 },
    { id: 'd:blight', name: '大斑病', category: 1 },
    { id: 'd:late', name: '晚疫病', category: 1 },
    { id: 'd:scab', name: '黑星病', category: 1 },
    { id: 's:1', name: '黄褐色疱斑', category: 2 },
    { id: 's:2', name: '梭形大斑', category: 2 },
    { id: 's:3', name: '水渍状暗斑', category: 2 },
    { id: 'm:1', name: '三唑酮', category: 3 },
    { id: 'm:2', name: '戊唑醇', category: 3 },
    { id: 'm:3', name: '烯酰吗啉', category: 3 },
    { id: 'p:1', name: '选用抗锈品种', category: 4 },
    { id: 'p:2', name: '清除病残体', category: 4 }
  ],
  links: [
    { source: 'c:corn', target: 'd:rust', value: '患' },
    { source: 'c:corn', target: 'd:blight', value: '患' },
    { source: 'c:tomato', target: 'd:late', value: '患' },
    { source: 'c:apple', target: 'd:scab', value: '患' },
    { source: 'd:rust', target: 's:1', value: '表现为' },
    { source: 'd:blight', target: 's:2', value: '表现为' },
    { source: 'd:late', target: 's:3', value: '表现为' },
    { source: 'd:rust', target: 'm:1', value: '用药' },
    { source: 'd:blight', target: 'm:2', value: '用药' },
    { source: 'd:late', target: 'm:3', value: '用药' },
    { source: 'd:rust', target: 'p:1', value: '措施' },
    { source: 'd:blight', target: 'p:2', value: '措施' }
  ],
  categories: [{ name: '作物' }, { name: '病害' }, { name: '症状' }, { name: '药剂' }, { name: '措施' }]
}