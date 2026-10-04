/**
 * 穹宇气象大模型演示系统 —— API 客户端
 *
 * 对应后端 10 大功能模块：
 *  1 态势总览  2 下钻联动  3 时间轴  4 多要素  5 单点预报
 *  6 检验看板  7 多模式对比  8 集合概率  9 风险预警  10 系统管理
 */

const BASE = import.meta.env?.VITE_API_BASE || ''

async function request(path, { timeout = 60000 } = {}) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeout)
  try {
    const response = await fetch(`${BASE}${path}`, { signal: controller.signal })
    const payload = await response.json().catch(() => ({}))
    if (!response.ok) {
      throw new Error(payload.detail || `请求失败（${response.status}）`)
    }
    if (payload.code !== 0) {
      throw new Error(payload.message || '接口返回异常')
    }
    return payload.data
  } catch (error) {
    if (error.name === 'AbortError') throw new Error('请求超时，数据加载较慢，请稍后重试')
    throw error
  } finally {
    clearTimeout(timer)
  }
}

async function post(path, body) {
  const response = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined,
  })
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(payload.detail || `请求失败（${response.status}）`)
  if (payload.code !== 0) throw new Error(payload.message || '接口返回异常')
  return payload.data
}

export const api = {
  // 健康与实时
  health: () => request('/api/health', { timeout: 8000 }),
  realtimeStatus: () => request('/api/realtime/status', { timeout: 15000 }),
  triggerScan: () => post('/api/realtime/scan'),

  // 模块 10：系统与任务管理
  systemInfo: () => request('/api/module/system'),
  lineage: () => request('/api/module/lineage'),
  quality: () => request('/api/module/quality'),

  // 模块 1：全国态势总览
  overview: (leadHour = 24, accumulation = '24h', stride = 1) =>
    request(`/api/module/overview?lead_hour=${leadHour}&accumulation=${accumulation}&stride=${stride}`),

  // 模块 2：多级下钻联动
  provinces: () => request('/api/module/provinces'),
  drilldown: (province, leadHour = 24, stride = 1) =>
    request(`/api/module/drilldown?province=${encodeURIComponent(province)}&lead_hour=${leadHour}&stride=${stride}`),

  // 模块 3：时间轴
  timeline: () => request('/api/module/timeline'),
  cycles: () => request('/api/module/cycles'),

  // 模块 4：多要素切换
  variables: () => request('/api/module/variables'),
  variableField: (key, leadHour = 24, stride = 1) =>
    request(`/api/module/variable?key=${encodeURIComponent(key)}&lead_hour=${leadHour}&stride=${stride}`),

  // 模块 5：单点预报详情
  point: (lon, lat, variable = 'tp') =>
    request(`/api/module/point?lon=${lon}&lat=${lat}&variable=${encodeURIComponent(variable)}`),

  // 模块 6：检验看板
  verification: (leadHour = 24) => request(`/api/module/verification?lead_hour=${leadHour}`),

  // 模块 7：多模式对比
  comparison: (leadHour = 24, stride = 2) =>
    request(`/api/module/comparison?lead_hour=${leadHour}&stride=${stride}`),

  // 模块 8：集合与概率
  ensemble: (leadHour = 24, threshold = 10, stride = 2) =>
    request(`/api/module/ensemble?lead_hour=${leadHour}&threshold=${threshold}&stride=${stride}`),

  // 模块 9：风险预警
  risk: (stride = 2) => request(`/api/module/risk?stride=${stride}`),
}

export default api
