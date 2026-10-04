/**
 * 图表与可视化工具集
 *
 * 统一 ECharts 主题、降水色斑渲染、时间轴/曲线/柱状/环形等图表的 option 构造，
 * 保证 10 个模块的视觉语言一致。
 */

import * as echarts from 'echarts'
import chinaGeoJson from './assets/china.json'

/* 全局注册中国地图（name: 'china'）。
   所有地图类图表统一使用该名称，模块组件无需各自重复注册，
   避免出现 “Map china not exists” 报错。 */
export const CHINA_MAP_NAME = 'china'
let _mapRegistered = false
export function ensureChinaMap() {
  if (_mapRegistered) return true
  try {
    echarts.registerMap(CHINA_MAP_NAME, chinaGeoJson)
    _mapRegistered = true
    return true
  } catch (error) {
    console.warn('[chartKit] 中国地图注册失败：', error)
    return false
  }
}
ensureChinaMap()

/** 中国区域数据范围（与后端 CHINA_LON/LAT_MIN/MAX 对齐） */
export const CHINA_DOMAIN = [[70, 56], [140, 12]]
export const CHINA_DOMAIN_CENTER = [105, 34]

/* -------- 中国陆地范围判定（射线法，用于把填色场裁剪到国境内） -------- */
let _chinaRings = null
function chinaRings() {
  if (_chinaRings) return _chinaRings
  const rings = []
  const push = (coords) => { if (Array.isArray(coords) && coords.length > 3) rings.push(coords) }
  const geo = chinaGeoJson
  const walk = (feat) => {
    const g = feat?.geometry
    if (!g) return
    if (g.type === 'Polygon') g.coordinates.forEach(push)
    else if (g.type === 'MultiPolygon') g.coordinates.forEach((poly) => poly.forEach(push))
  }
  const features = geo?.features
    || (geo?.geometry ? [geo] : [])
    || Object.values(geo || {}).filter((v) => v && v.geometry)
  features.forEach(walk)
  _chinaRings = rings
  return rings
}

function pointInRing(lon, lat, ring) {
  let inside = false
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const xi = ring[i][0]; const yi = ring[i][1]
    const xj = ring[j][0]; const yj = ring[j][1]
    const intersect = (yi > lat) !== (yj > lat)
      && lon < ((xj - xi) * (lat - yi)) / (yj - yi + 1e-12) + xi
    if (intersect) inside = !inside
  }
  return inside
}

/** 判断经纬度是否落在中国陆地（含岛屿）范围内 */
export function isInChina(lon, lat) {
  const rings = chinaRings()
  if (!rings.length) return true
  for (let i = 0; i < rings.length; i += 1) {
    if (pointInRing(lon, lat, rings[i])) return true
  }
  return false
}

/** 深色大屏基准主题 */
export const CHART_THEME = {
  textColor: '#93b3d8',
  textStrong: '#e8f2ff',
  axisLine: 'rgba(88,148,216,0.28)',
  splitLine: 'rgba(88,148,216,0.12)',
  bg: 'transparent',
  cyan: '#5fd8ff',
  teal: '#3fd8b0',
  amber: '#ffc94d',
  orange: '#ff8f4d',
  red: '#ff5c6e',
  violet: '#a78bfa',
  blue: '#4a9eff',
}

/** 降水色标（低 → 高），与后端 PALETTES.precip 对齐。
 *  低值段保持明显蓝色，避免大面积弱降水区域呈现灰白、影响读图。 */
export const PRECIP_COLORS = [
  '#5aa9e6', '#3f8fd0', '#3ed69a', '#8fd44a', '#d9d84a',
  '#f2c14e', '#f08b3e', '#e84b5f', '#a03050',
]

/** 降水色标断点（mm/6h） */
export const PRECIP_BREAKS = [0.1, 1, 3, 10, 20, 35, 60, 100]

/**
 * 通用分级色带（低 → 高 9 档）。
 * 返回值数组下标即分级索引，供 rasterGridSeries 与图例共用。
 */
export function gradeColors(palette) {
  if (Array.isArray(palette) && palette.length >= 2) return palette
  return PRECIP_COLORS
}

/** 在 [min, max] 区间内等分 n 段，返回各段下界（升序）。 */
export function equalBreaks(min, max, n = 9) {
  const lo = Number.isFinite(min) ? min : 0
  const hi = Number.isFinite(max) ? max : 1
  if (hi <= lo) return [lo]
  const step = (hi - lo) / n
  const out = []
  for (let i = 0; i < n; i += 1) out.push(Number((lo + step * i).toFixed(4)))
  return out
}

/**
 * 生成与 rasterGridSeries 分级完全一致的图例（visualMap piecewise）。
 * breaks 为各档下界（升序），colors 为对应颜色。
 */
export function gradeVisualMap(breaks, colors, unit = '') {
  const bs = Array.isArray(breaks) && breaks.length ? breaks : PRECIP_BREAKS
  const cs = gradeColors(colors)
  const pieces = bs.map((low, i) => {
    const high = i < bs.length - 1 ? bs[i + 1] : null
    const color = cs[Math.min(i + 1, cs.length - 1)]
    const fmt = (v) => (Math.abs(v) >= 100 || (v !== 0 && Math.abs(v) < 0.1) ? v.toExponential(0) : String(Number(v.toFixed(2))))
    const label = high == null ? `≥${fmt(low)} ${unit}` : `${fmt(low)}–${fmt(high)} ${unit}`
    const piece = { label, color, _low: low, _high: high }
    return piece
  })
  return {
    show: false,
    seriesIndex: 0,
    type: 'piecewise',
    pieces: pieces.map(({ _low, _high, ...rest }) => rest),
  }
}

export const RISK_COLORS = {
  red: '#ff5c6e',
  orange: '#ff9a4d',
  yellow: '#ffd24d',
  blue: '#55b8ff',
  green: '#3fd8b0',
}

/* -------------------------------------------------------------- 实例管理 */

const registry = new WeakMap()

export function mountChart(el) {
  if (!el) return null
  ensureChinaMap()
  let chart = registry.get(el)
  if (!chart) {
    chart = echarts.init(el, null, { renderer: 'canvas' })
    registry.set(el, chart)
  }
  return chart
}

export function disposeChart(el) {
  if (!el) return
  const chart = registry.get(el)
  if (chart) {
    chart.dispose()
    registry.delete(el)
  }
}

export function resizeAll() {
  window.dispatchEvent(new Event('resize'))
}

/* -------------------------------------------------------------- 颜色工具 */

/** 按值在色标中取色 */
export function colorForValue(value, breaks = PRECIP_BREAKS, colors = PRECIP_COLORS) {
  for (let i = breaks.length - 1; i >= 0; i -= 1) {
    if (value >= breaks[i]) return colors[Math.min(i + 1, colors.length - 1)]
  }
  return colors[0]
}

/** 生成 visualMap piecewise 配置（降水分级） */
export function precipVisualMap(unit = 'mm/6h', extra = {}) {
  const pieces = [
    { min: 100, label: `≥100 ${unit}`, color: '#a03050' },
    { min: 60, max: 100, label: `60–100 ${unit}`, color: '#e84b5f' },
    { min: 35, max: 60, label: `35–60 ${unit}`, color: '#f08b3e' },
    { min: 20, max: 35, label: `20–35 ${unit}`, color: '#f1d14f' },
    { min: 10, max: 20, label: `10–20 ${unit}`, color: '#b9db4a' },
    { min: 3, max: 10, label: `3–10 ${unit}`, color: '#3ed69a' },
    { min: 1, max: 3, label: `1–3 ${unit}`, color: '#38a6dc' },
    { min: 0.1, max: 1, label: `0.1–1 ${unit}`, color: '#7fc4f5' },
    { max: 0.1, label: `＜0.1 ${unit}`, color: '#cfe8ff' },
  ]
  return {
    show: false,
    seriesIndex: 0,
    type: 'piecewise',
    pieces,
    ...extra,
  }
}

/* -------------------------------------------------------------- 地图 series */

/**
 * 规则网格标量场栅格渲染（geo 坐标系）。
 *
 * 为什么不用 ECharts 原生 heatmap：
 *   heatmap 在 geo 上是「核密度晕染」，会把稀疏点位扩散成整片色块，
 *   并把经纬度外侧一并填充，导致面板被大面积饱和色淹没。
 * 本实现按真实格距绘制每个格点的小矩形，形成规范的填色场，
 * 仅覆盖有值格点，边界贴合中国裁剪区。
 *
 * points: [[lon, lat, value], ...]（等经纬规则网格）
 * 颜色按 breaks 分级取自 colors；value < breaks[0] 的格点视为无有效降水，跳过不绘制。
 */
export function rasterGridSeries(points, {
  id = 'field',
  name = '要素场',
  breaks = PRECIP_BREAKS,
  colors = PRECIP_COLORS,
  unit = '',
  opacity = 0.9,
  z = 2,
  fillRatio = 1.02,
  clipToChina = true,
} = {}) {
  if (!points || !points.length) {
    return { id, name, type: 'custom', coordinateSystem: 'geo', data: [], renderItem: () => null, silent: true }
  }

  // 推断网格步长（取最小正间距，兼容 0.25° / 0.5° 产品）
  const lons = Array.from(new Set(points.map((p) => p[0]))).sort((a, b) => a - b)
  const lats = Array.from(new Set(points.map((p) => p[1]))).sort((a, b) => a - b)
  let dLon = 0.25
  let dLat = 0.25
  for (let i = 1; i < lons.length; i += 1) {
    const d = lons[i] - lons[i - 1]
    if (d > 1e-6) { dLon = d; break }
  }
  for (let i = 1; i < lats.length; i += 1) {
    const d = lats[i] - lats[i - 1]
    if (d > 1e-6) { dLat = d; break }
  }
  const halfLon = (dLon * fillRatio) / 2
  const halfLat = (dLat * fillRatio) / 2
  const minBreak = breaks[0]

  const cells = []
  for (let i = 0; i < points.length; i += 1) {
    const [lon, lat, value] = points[i]
    if (value == null || value < minBreak) continue
    // 默认裁剪到中国陆地范围，避免填色场铺满整个经纬度矩形、覆盖海洋与邻国
    if (clipToChina && !isInChina(lon, lat)) continue
    cells.push({ value: [lon, lat, value], color: colorForValue(value, breaks, colors) })
  }

  if (!cells.length) {
    return { id, name, type: 'custom', coordinateSystem: 'geo', data: [], renderItem: () => null, silent: true }
  }

  return {
    id,
    name,
    type: 'custom',
    coordinateSystem: 'geo',
    geoIndex: 0,
    z,
    silent: false,
    // 关掉自定义系列的默认裁剪延迟，让 rect 严格落在 geo 视窗内
    clip: true,
    data: cells,
    tooltip: {
      formatter: (p) =>
        `经度 ${p.value[0].toFixed(2)}°E<br/>纬度 ${p.value[1].toFixed(2)}°N<br/><b>${Number(p.value[2]).toFixed(1)}</b> ${unit}`,
    },
    renderItem(params, apiObj) {
      const lon = apiObj.value(0)
      const lat = apiObj.value(1)
      const p0 = apiObj.coord([lon - halfLon, lat - halfLat])
      const p1 = apiObj.coord([lon + halfLon, lat + halfLat])
      if (!p0 || !p1) return null
      const x = Math.min(p0[0], p1[0])
      const y = Math.min(p0[1], p1[1])
      const w = Math.abs(p1[0] - p0[0])
      const h = Math.abs(p1[1] - p0[1])
      const item = cells[params.dataIndex]
      return {
        type: 'rect',
        shape: { x, y, width: Math.max(w, 0.5), height: Math.max(h, 0.5) },
        style: { fill: item.color, opacity },
        silent: false,
      }
    },
  }
}

/** 兼容旧调用：降水色斑（栅格渲染） */
export function precipHeatSeries(points, { id = 'precip', name = '降水', unit = 'mm/6h', breaks = PRECIP_BREAKS, colors = PRECIP_COLORS, opacity = 0.9, z = 2 } = {}) {
  return rasterGridSeries(points, { id, name, unit, breaks, colors, opacity, z })
}

/** 兼容旧调用：通用标量场（栅格渲染） */
export function scalarHeatSeries(points, { id = 'field', name = '要素场', unit = '', breaks = PRECIP_BREAKS, colors = PRECIP_COLORS, opacity = 0.9, z = 2 } = {}) {
  return rasterGridSeries(points, { id, name, unit, breaks, colors, opacity, z })
}


/** 风场箭头 */
export function windArrowSeries(arrows, unit = 'm/s') {
  return {
    id: 'wind-arrows',
    name: '风向风速',
    type: 'scatter',
    coordinateSystem: 'geo',
    symbol: 'path://M0,-7L4,5L0,2.4L-4,5Z',
    symbolSize: 10,
    z: 12,
    data: arrows.map((a) => ({
      value: [a.lon, a.lat, a.speed],
      symbolRotate: Math.atan2(a.u, a.v) * (180 / Math.PI),
      u: a.u,
      v: a.v,
      direction: a.direction,
      speed: a.speed,
    })),
    itemStyle: {
      color: 'rgba(232,242,255,0.86)',
      shadowBlur: 3,
      shadowColor: '#0a1e3d',
    },
    tooltip: {
      formatter: (p) =>
        `经度 ${p.value[0]}°E<br/>纬度 ${p.value[1]}°N<br/>风速 <b>${p.data.speed}</b> ${unit}<br/>` +
        `风向 ${p.data.direction}°<br/>U ${p.data.u} / V ${p.data.v}`,
    },
  }
}

/** 地理底图配置 */
/**
 * 中国区域地图 geo 配置。
 *
 * 关键点：使用 boundingCoords 把 geo 视窗锁定到中国范围网格（默认 70–140°E / 12–56°N），
 * 使「栅格填色场」与底图使用同一套经纬度投影，避免色斑超出面板或与省界错位。
 * 组件可通过 domain 覆盖该范围。
 */
export function geoOption({
  center = [104.5, 36],
  zoom = 1.4,
  roam = true,
  domain = null,
  silent = false,
} = {}) {
  const option = {
    map: 'china',
    roam,
    zoom,
    center,
    scaleLimit: { min: 0.9, max: 12 },
    itemStyle: {
      areaColor: 'rgba(16, 44, 84, 0.78)',
      borderColor: 'rgba(110, 178, 240, 0.72)',
      borderWidth: 0.9,
      shadowColor: 'rgba(60, 140, 220, 0.4)',
      shadowBlur: 12,
    },
    emphasis: {
      disabled: false,
      itemStyle: { areaColor: 'rgba(46, 110, 178, 0.72)' },
      label: { show: true, color: '#e8f2ff', fontSize: 10, backgroundColor: 'rgba(8,22,46,0.85)', padding: [2, 5], borderRadius: 3 },
    },
    label: { show: false },
    silent,
    select: { disabled: true },
  }
  // domain 目前仅用于记录数据范围，不再使用 boundingCoords
  // （ECharts 在同时设置 zoom/center 时会忽略 boundingCoords，导致栅格与底图错位）。
  option.__domain = domain || null
  return option
}

/* -------------------------------------------------------------- 曲线 / 柱状 */

/** 逐时效曲线（可多条） */
export function leadCurveOption(series, {
  xLabels, yUnit = '', showArea = true, height = null, yName = '', markLine = null,
} = {}) {
  return {
    grid: { left: 46, right: 16, top: 24, bottom: 30 },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(8,22,46,0.94)',
      borderColor: 'rgba(95,216,255,0.35)',
      textStyle: { color: '#e8f2ff', fontSize: 11 },
      axisPointer: { type: 'line', lineStyle: { color: 'rgba(95,216,255,0.5)' } },
      valueFormatter: (v) => (v == null ? '--' : `${Number(v).toFixed(2)} ${yUnit}`),
    },
    legend: series.length > 1
      ? {
          show: true, top: 0, right: 4,
          itemWidth: 10, itemHeight: 6, itemGap: 12,
          textStyle: { color: CHART_THEME.textColor, fontSize: 10 },
        }
      : { show: false },
    xAxis: {
      type: 'category',
      data: xLabels,
      boundaryGap: false,
      axisLine: { lineStyle: { color: CHART_THEME.axisLine } },
      axisTick: { show: false },
      axisLabel: { color: CHART_THEME.textColor, fontSize: 10, interval: Math.max(0, Math.floor(xLabels.length / 8) - 1) },
    },
    yAxis: {
      type: 'value',
      name: yName,
      nameTextStyle: { color: CHART_THEME.textColor, fontSize: 9, padding: [0, 0, 4, 0] },
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: CHART_THEME.textColor, fontSize: 10 },
      splitLine: { lineStyle: { color: CHART_THEME.splitLine } },
    },
    series: series.map((s) => ({
      name: s.name,
      type: 'line',
      smooth: 0.28,
      showSymbol: false,
      symbolSize: 5,
      lineStyle: { width: 2, color: s.color },
      itemStyle: { color: s.color },
      areaStyle: showArea
        ? {
            opacity: 0.16,
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: s.color },
              { offset: 1, color: 'rgba(0,0,0,0)' },
            ]),
          }
        : undefined,
      data: s.data,
      markLine: s.markLine || markLine || undefined,
    })),
  }
}

/** 分组柱状对比 */
export function compareBarOption(categories, series, { yUnit = '', horizontal = false } = {}) {
  return {
    grid: { left: horizontal ? 92 : 48, right: 18, top: series.length > 1 ? 28 : 16, bottom: 26 },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(8,22,46,0.94)',
      borderColor: 'rgba(95,216,255,0.35)',
      textStyle: { color: '#e8f2ff', fontSize: 11 },
      axisPointer: { type: 'shadow' },
      valueFormatter: (v) => (v == null ? '--' : `${Number(v).toFixed(2)} ${yUnit}`),
    },
    legend: series.length > 1
      ? { show: true, top: 0, right: 4, itemWidth: 10, itemHeight: 6, textStyle: { color: CHART_THEME.textColor, fontSize: 10 } }
      : { show: false },
    xAxis: horizontal
      ? { type: 'value', axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: CHART_THEME.textColor, fontSize: 10 }, splitLine: { lineStyle: { color: CHART_THEME.splitLine } } }
      : { type: 'category', data: categories, axisLine: { lineStyle: { color: CHART_THEME.axisLine } }, axisTick: { show: false }, axisLabel: { color: CHART_THEME.textColor, fontSize: 10 } },
    yAxis: horizontal
      ? { type: 'category', data: categories, axisLine: { lineStyle: { color: CHART_THEME.axisLine } }, axisTick: { show: false }, axisLabel: { color: CHART_THEME.textColor, fontSize: 10 } }
      : { type: 'value', axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: CHART_THEME.textColor, fontSize: 10 }, splitLine: { lineStyle: { color: CHART_THEME.splitLine } } },
    series: series.map((s) => ({
      name: s.name,
      type: 'bar',
      barMaxWidth: horizontal ? 12 : 20,
      itemStyle: {
        borderRadius: horizontal ? [0, 3, 3, 0] : [3, 3, 0, 0],
        color: s.gradient
          ? new echarts.graphic.LinearGradient(horizontal ? 0 : 0, horizontal ? 0 : 0, horizontal ? 1 : 0, horizontal ? 0 : 1, [
              { offset: 0, color: s.color },
              { offset: 1, color: s.colorEnd || s.color },
            ])
          : s.color,
      },
      label: s.label
        ? { show: true, position: horizontal ? 'right' : 'top', color: CHART_THEME.textStrong, fontSize: 10, formatter: s.label }
        : { show: false },
      data: s.data,
    })),
  }
}

/** 环形占比图 */
export function donutOption(items, { centerText = '', centerValue = '', radius = ['52%', '74%'] } = {}) {
  return {
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(8,22,46,0.94)',
      borderColor: 'rgba(95,216,255,0.35)',
      textStyle: { color: '#e8f2ff', fontSize: 11 },
      formatter: (p) => `${p.name}<br/><b>${p.value}</b>（${p.percent}%）`,
    },
    graphic: centerValue
      ? [
          { type: 'text', left: 'center', top: '42%', style: { text: centerValue, fill: CHART_THEME.textStrong, fontSize: 20, fontWeight: 600, fontFamily: 'monospace' } },
          { type: 'text', left: 'center', top: '56%', style: { text: centerText, fill: CHART_THEME.textColor, fontSize: 9 } },
        ]
      : undefined,
    series: [
      {
        type: 'pie',
        radius,
        center: ['50%', '52%'],
        avoidLabelOverlap: true,
        label: { show: true, color: CHART_THEME.textColor, fontSize: 10, formatter: '{b}\n{d}%' },
        labelLine: { length: 8, length2: 6, lineStyle: { color: CHART_THEME.axisLine } },
        itemStyle: { borderColor: 'rgba(8,22,46,0.9)', borderWidth: 2 },
        data: items,
      },
    ],
  }
}

/* -------------------------------------------------------------- 时间轴 */

/** 时间轴带状图：展示 61 个时次的降水强度背景 */
export function timelineStripOption(series, currentIndex, { unit = 'mm/6h' } = {}) {
  return {
    grid: { left: 0, right: 0, top: 2, bottom: 2 },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(8,22,46,0.94)',
      borderColor: 'rgba(95,216,255,0.35)',
      textStyle: { color: '#e8f2ff', fontSize: 10 },
      formatter: (params) => {
        const p = params?.[0]
        if (!p) return ''
        const item = series[p.dataIndex]
        return `${item.label} · ${formatShort(item.validTime)}<br/><b>${Number(p.value).toFixed(1)}</b> ${unit}`
      },
    },
    xAxis: {
      type: 'category',
      data: series.map((s) => s.label),
      show: false,
      boundaryGap: false,
    },
    yAxis: { type: 'value', show: false, min: 0, max: 1 },
    series: [
      {
        type: 'bar',
        barCategoryGap: '12%',
        data: series.map((s, i) => ({
          value: 1,
          itemStyle: {
            color: colorForValue(s.value),
            opacity: i === currentIndex ? 1 : 0.62,
            borderRadius: 1,
          },
        })),
        silent: false,
      },
      {
        type: 'scatter',
        symbolSize: [3, 22],
        data: series.map((s, i) => ({
          value: [i, 0.5],
          itemStyle: { color: i === currentIndex ? '#ffffff' : 'transparent' },
        })),
        silent: true,
        z: 5,
      },
    ],
  }
}

/* -------------------------------------------------------------- 格式化 */

export function formatShort(iso) {
  if (!iso) return '--'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '--'
  const pad = (n) => String(n).padStart(2, '0')
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}时`
}

export function formatFull(iso) {
  if (!iso) return '--'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '--'
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

export function formatClock(iso) {
  if (!iso) return '--:--:--'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '--:--:--'
  const pad = (n) => String(n).padStart(2, '0')
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

export function formatDateOnly(iso) {
  if (!iso) return '--'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '--'
  const week = ['日', '一', '二', '三', '四', '五', '六'][d.getDay()]
  return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日 星期${week}`
}

export function num(value, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '--'
  return Number(value).toFixed(digits)
}
