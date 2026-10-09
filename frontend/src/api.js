import { sessionExpired } from './auth.js'
/**
 * 穹宇气象大模型演示系统 —— API 客户端
 *
 * 对应当前后端功能：
 *  1 态势总览  2 下钻联动  3 时间轴  4 多要素  5 单点预报
 *  检验看板、集合概率、风险预警、系统管理和数据导入
 */

const BASE = import.meta.env?.VITE_API_BASE || ''

async function request(path, { timeout = 60000 } = {}) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeout)
  try {
    const response = await fetch(`${BASE}${path}`, { signal: controller.signal, credentials: 'include' })
    const payload = await response.json().catch(() => ({}))
    if (response.status === 401) sessionExpired()
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
    credentials: 'include',
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined,
  })
  const payload = await response.json().catch(() => ({}))
  if (response.status === 401) sessionExpired()
  if (!response.ok) throw new Error(payload.detail || `请求失败（${response.status}）`)
  if (payload.code !== 0) throw new Error(payload.message || '接口返回异常')
  return payload.data
}

export const api = {
  login: body => post('/api/auth/login',body),
  me: () => request('/api/auth/me'),
  logout: () => post('/api/auth/logout'),
  users: () => request('/api/admin/users'),
  createUser: body => post('/api/admin/users',body),
  updateUser: body => post('/api/admin/users/update',body),
  logs: () => request('/api/admin/logs'),
  rejectImport: (id,reason) => post(`/api/admin/imports/${id}/reject`,{reason}),
  dataBatches: () => request('/api/data/batches'),
  createImport: (body) => post('/api/data/imports', body),
  importStatus: (id) => request(`/api/data/imports/${id}`),
  importPreview: (id) => request(`/api/data/imports/${id}/preview`, { timeout: 180000 }),
  updateImportMetadata: (id, body) => post(`/api/data/imports/${id}/metadata`, body),
  referenceOptions: (forecastId = '') => request(`/api/data/reference-options${forecastId ? '?forecast_id=' + encodeURIComponent(forecastId) : ''}`, { timeout: 180000 }),
  finalizeImport: (id) => post(`/api/data/imports/${id}/finalize`),
  activateBatch: (id) => post(`/api/data/batches/${encodeURIComponent(id)}/activate`),
  removeBatch: (id) => post(`/api/data/batches/${encodeURIComponent(id)}/remove`),
  uploadFile: (id, file, onProgress, signal) => new Promise((resolve, reject) => {
    if (signal?.aborted) { reject(new Error('上传已取消')); return }
    const xhr = new XMLHttpRequest()
    const abort = () => xhr.abort()
    signal?.addEventListener('abort', abort, { once: true })
    xhr.open('POST', `${BASE}/api/data/imports/${id}/files?filename=${encodeURIComponent(file.name)}`)
    xhr.withCredentials = true
    xhr.timeout = 180000
    xhr.setRequestHeader('Content-Type', 'application/octet-stream')
    xhr.upload.onprogress = (e) => { if (e.lengthComputable) onProgress?.(e.loaded / e.total) }
    xhr.onload = () => {
      signal?.removeEventListener('abort', abort)
      if (xhr.status === 401) sessionExpired()
      let payload
      try { payload = JSON.parse(xhr.responseText) } catch { reject(new Error('上传响应无法解析')); return }
      if (xhr.status >= 200 && xhr.status < 300 && payload.code === 0) resolve(payload.data)
      else reject(new Error(payload.detail || '上传失败'))
    }
    xhr.onerror = () => { signal?.removeEventListener('abort', abort); reject(new Error('上传连接中断，请重新创建导入任务')) }
    xhr.ontimeout = () => { signal?.removeEventListener('abort', abort); reject(new Error('单文件上传超时，请重新创建导入任务')) }
    xhr.onabort = () => { signal?.removeEventListener('abort', abort); reject(new Error('上传已取消；已接收文件保留在待处理任务，不会成为可用数据')) }
    xhr.send(file)
  }),
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
  verification: (leadHour = 24, params = {}) => request(`/api/module/verification?${new URLSearchParams({ lead_hour: leadHour, ...params })}`, { timeout: 180000 }),

  // 模块 8：集合与概率
  ensemble: (leadHour = 24, threshold = 10, stride = 2) =>
    request(`/api/module/ensemble?lead_hour=${leadHour}&threshold=${threshold}&stride=${stride}`),

  // 模块 9：风险预警
  risk: (stride = 2) => request(`/api/module/risk?stride=${stride}`),
}

export default api
