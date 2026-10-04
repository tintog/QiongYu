<template>
  <main class="page-surface">
    <!-- 页头 -->
    <header class="page-head rise-in">
      <div class="ph-left">
        <div class="ph-kicker"><i></i><span>National Situation · Module 01</span></div>
        <h2>全国降水态势总览</h2>
        <p class="ph-desc">
          基于穹宇AI降水预报模型 {{ info.modelProduct }} 逐6小时确定性产品，展示未来15天全国降水落区、
          强度分布与区域排行。当前有效时间 {{ formatFull(overviewData.validTime) }}，网格分辨率
          {{ info.spatialResolution }}，共 {{ timeline.length }} 个时次。
        </p>
      </div>
      <div class="ph-right">
        <span class="module-tag"><b>01</b> 必备功能</span>
        <span class="required-tag must">核心必备</span>
      </div>
    </header>

    <!-- 主体三栏 -->
    <div class="overview-layout">
      <!-- 左栏：统计 + 降雨分级 -->
      <aside class="ov-side">
        <section class="panel">
          <div class="panel-head">
            <div class="panel-title"><i class="bar"></i><h3>态势统计</h3></div>
            <span class="panel-sub">{{ overviewData.accumulationLabel }}</span>
          </div>
          <div class="panel-body">
            <div class="metric-grid cols-2">
              <div class="metric" style="--accent:#ff7a8a">
                <span>最大降水</span>
                <strong>{{ num(stat.maximum) }}<em>{{ overviewData.unit }}</em></strong>
                <small>{{ hotspot ? `位于${hotspot.nearestRegion}附近` : '当前时效' }}</small>
              </div>
              <div class="metric" style="--accent:#5fd8ff">
                <span>区域平均</span>
                <strong>{{ num(stat.average) }}<em>{{ overviewData.unit }}</em></strong>
                <small>全国有效格点均值</small>
              </div>
              <div class="metric" style="--accent:#3fd8b0">
                <span>有雨格点</span>
                <strong>{{ stat.wetGridCount ?? '--' }}<em>个</em></strong>
                <small>≥0.1 {{ overviewData.unit }} 的格点</small>
              </div>
              <div class="metric" style="--accent:#ffc94d">
                <span>强降水格点</span>
                <strong>{{ stat.heavyGridCount ?? '--' }}<em>个</em></strong>
                <small>≥20 {{ overviewData.unit }} 的格点</small>
              </div>
            </div>

            <div class="ramp-wrap" style="margin-top:14px">
              <div class="ramp-labels"><span>降水色标</span><span>{{ overviewData.unit }}</span></div>
              <div class="color-ramp">
                <i v-for="(c, i) in overviewData.palette || precipColors" :key="i" :style="{ background: c }"></i>
              </div>
              <div class="ramp-labels">
                <span>0.1</span><span>1</span><span>3</span><span>10</span><span>20</span><span>35</span><span>60</span><span>100+</span>
              </div>
            </div>

            <div class="hotspot-card" v-if="hotspot">
              <div class="hs-head">
                <span>当前时效降水中心</span>
                <span class="risk-badge" :class="`lv-${riskKeyOf(hotspot.value)}`">
                  <i></i>{{ hotspot.level }}
                </span>
              </div>
              <div class="hs-body">
                <div><span>中心位置</span><strong>{{ hotspot.lon }}°E，{{ hotspot.lat }}°N</strong></div>
                <div><span>邻近区域</span><strong>{{ hotspot.nearestRegion }}（约{{ hotspot.distanceDeg }}°）</strong></div>
                <div><span>峰值强度</span><strong>{{ num(hotspot.value) }} {{ overviewData.unit }}</strong></div>
              </div>
            </div>
          </div>
        </section>

        <section class="panel">
          <div class="panel-head">
            <div class="panel-title"><i class="bar"></i><h3>七大区域聚合</h3></div>
            <span class="panel-sub">Regional Aggregate</span>
          </div>
          <div class="panel-body scroll-y">
            <table class="data-table">
              <thead>
                <tr><th>区域</th><th style="text-align:right">最大</th><th style="text-align:right">平均</th><th style="text-align:right">有雨占比</th></tr>
              </thead>
              <tbody>
                <tr v-for="row in overviewData.bigRegions || []" :key="row.name">
                  <td class="strong">{{ row.name }}</td>
                  <td class="num">{{ num(row.maximum) }}</td>
                  <td class="num">{{ num(row.average, 2) }}</td>
                  <td class="num">{{ ((row.wetRatio || 0) * 100).toFixed(1) }}%</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </aside>

      <!-- 中栏：地图 + 时间轴 -->
      <section class="ov-center">
        <div class="map-toolbar">
          <div class="tb-group">
            <span class="tb-label">累计方式</span>
            <div class="seg">
              <button v-for="opt in accumulations" :key="opt.value"
                      :class="{ active: accumulation === opt.value }"
                      @click="setAccumulation(opt.value)">{{ opt.label }}</button>
            </div>
          </div>
          <div class="tb-group">
            <span class="tb-label">下钻</span>
            <select v-model="province" class="tb-select" @change="onProvinceChange">
              <option value="">全国</option>
              <option v-for="p in provinceList" :key="p.name" :value="p.name">{{ p.name }}</option>
            </select>
          </div>
          <div class="tb-group right">
            <button class="btn ghost sm" @click="resetView"><AppIcon name="locate" :size="13" />复位</button>
            <div class="seg">
              <button :class="{ active: baseMap === 'precip' }" @click="baseMap = 'precip'">降水色斑</button>
              <button :class="{ active: baseMap === 'plain' }" @click="baseMap = 'plain'">行政区</button>
            </div>
          </div>
        </div>

        <div class="map-stage">
          <div ref="mapEl" class="map-canvas"></div>

          <div v-if="loading" class="loading-veil"><div class="spinner"></div><span>正在加载 {{ overviewData.accumulationLabel }}…</span></div>

          <!-- 地图右上角实时时钟 -->
          <div class="map-hud">
            <div class="hud-row"><span>起报</span><strong>{{ formatShort(info.initialTime) }}</strong></div>
            <div class="hud-row"><span>有效</span><strong>{{ formatShort(overviewData.validTime) }}</strong></div>
            <div class="hud-row"><span>时效</span><strong>+{{ String(overviewData.leadHour || 0).padStart(3, '0') }}h</strong></div>
            <div class="hud-row"><span>时效序号</span><strong>{{ currentIndex }} / {{ Math.max(0, timeline.length - 1) }}</strong></div>
          </div>

          <!-- 图例 -->
          <div class="map-legend-box">
            <div class="ml-title">{{ overviewData.accumulationLabel }}（{{ overviewData.unit }}）</div>
            <div class="ml-ramp">
              <i v-for="(c, i) in overviewData.palette || precipColors" :key="i" :style="{ background: c }"></i>
            </div>
            <div class="ml-labels"><span>0.1</span><span>3</span><span>10</span><span>20</span><span>60+</span></div>
          </div>
        </div>

        <!-- 时间轴播放 -->
        <section class="panel timeline-panel">
          <div class="panel-head" style="margin-bottom:7px;padding-bottom:7px">
            <div class="panel-title">
              <i class="bar"></i><h3>时间轴播放</h3>
              <span class="panel-sub">{{ roundLabel }}</span>
            </div>
            <div class="panel-extra">
              <button class="btn ghost sm" @click="stepLead(-4)"><AppIcon name="prev" :size="12" /> -24h</button>
              <button class="btn ghost sm" @click="stepLead(-1)"><AppIcon name="prev" :size="12" /> -6h</button>
              <button class="btn primary sm" @click="togglePlay">
                <AppIcon :name="playing ? 'pause' : 'play'" :size="12" />{{ playing ? '暂停' : '播放' }}
              </button>
              <button class="btn ghost sm" @click="stepLead(1)">+6h <AppIcon name="next" :size="12" /></button>
              <button class="btn ghost sm" @click="stepLead(4)">+24h <AppIcon name="next" :size="12" /></button>
              <div class="seg" style="margin-left:4px">
                <button v-for="sp in speeds" :key="sp.value"
                        :class="{ active: playSpeed === sp.value }"
                        @click="playSpeed = sp.value">{{ sp.label }}</button>
              </div>
            </div>
          </div>
          <div class="panel-body">
            <div ref="stripEl" class="timeline-strip" @click="onStripClick"></div>
            <input
              class="timeline-range"
              type="range"
              :min="0"
              :max="Math.max(0, timeline.length - 1)"
              :value="currentIndex"
              @input="onRangeInput"
            />
            <div class="timeline-marks">
              <span v-for="mark in dayMarks" :key="mark.index" :style="{ left: mark.left }">{{ mark.label }}</span>
            </div>
            <div class="timeline-info">
              <span class="ti-cur">当前：<b>{{ timeline[currentIndex]?.label || '--' }}</b> · {{ formatFull(overviewData.validTime) }}</span>
              <span class="ti-range">起报 {{ formatFull(info.initialTime) }} → 末期 {{ formatFull(timeline[timeline.length - 1]?.validTime) }}</span>
            </div>
          </div>
        </section>
      </section>

      <!-- 右栏：排行 + 单点快览 -->
      <aside class="ov-side right">
        <section class="panel">
          <div class="panel-head">
            <div class="panel-title"><i class="bar"></i><h3>区域降水排行</h3></div>
            <span class="panel-sub">Top 12</span>
          </div>
          <div class="panel-body scroll-y">
            <div class="rank-list">
              <button v-for="(item, i) in rankedProvinces" :key="item.name"
                      class="rank-item"
                      :class="{ selected: selectedProvinceForPoint === item.name }"
                      @click="pickProvince(item)">
                <b :class="`rank-no n${i < 3 ? i + 1 : 'x'}`">{{ String(i + 1).padStart(2, '0') }}</b>
                <span class="rank-name">{{ item.name }}</span>
                <div class="rank-bar"><i :style="{ width: `${rankWidth(item.value)}%` }"></i></div>
                <strong>{{ num(item.value) }}</strong>
              </button>
            </div>
          </div>
        </section>

        <section class="panel" style="flex:1">
          <div class="panel-head">
            <div class="panel-title"><i class="bar"></i><h3>单点预报快览</h3></div>
            <span class="panel-sub">{{ pointData.region || '未选择' }}</span>
          </div>
          <div class="panel-body">
            <p class="point-coord">
              {{ pointData.region || '--' }} ·
              {{ pointData.gridPoint?.lon ?? '--' }}°E，{{ pointData.gridPoint?.lat ?? '--' }}°N
              <span class="coord-tag">0.25° 网格</span>
            </p>
            <div ref="pointEl" class="point-mini-chart"></div>
            <div class="mini-summary">
              <div><span>15天累计</span><strong>{{ num(pointData.summary?.total) }} mm</strong></div>
              <div><span>峰值</span><strong>{{ num(pointData.summary?.maximum) }} mm/6h</strong></div>
              <div><span>有雨时段</span><strong>{{ pointData.summary?.rainyPeriods ?? '--' }} 个</strong></div>
            </div>
            <button class="btn ghost sm full" @click="gotoPointDetail">
              <AppIcon name="search" :size="12" />查看单点详情
            </button>
          </div>
        </section>
      </aside>
    </div>
  </main>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import AppIcon from './AppIcon.vue'
import api from '../api'
import {
  mountChart, disposeChart, precipHeatSeries, geoOption, timelineStripOption,
  leadCurveOption, formatShort, formatFull, num, PRECIP_COLORS, colorForValue,
  CHINA_DOMAIN, CHINA_DOMAIN_CENTER,
} from '../chartKit'

const props = defineProps({ info: { type: Object, default: () => ({}) } })
const emit = defineEmits(['navigate', 'point-selected'])

const accumulations = [
  { value: '6h', label: '6小时' },
  { value: '24h', label: '24小时' },
  { value: 'total', label: '过程累计' },
]
const speeds = [
  { value: 1400, label: '1×' },
  { value: 800, label: '2×' },
  { value: 400, label: '4×' },
]
const precipColors = PRECIP_COLORS

const timeline = ref([])
const provinceList = ref([])
const currentIndex = ref(4)
const accumulation = ref('24h')
const province = ref('')
const baseMap = ref('precip')
const overviewData = ref({ points: [], statistics: {}, palette: precipColors })
const pointData = ref({})
const loading = ref(false)
const playing = ref(false)
const playSpeed = ref(1400)
const selectedProvinceForPoint = ref('')

const mapEl = ref(null)
const stripEl = ref(null)
const pointEl = ref(null)

let mapChart = null
let stripChart = null
let pointChart = null
let playTimer = null
let fetchToken = 0

const stat = computed(() => overviewData.value.statistics || {})
const hotspot = computed(() => overviewData.value.hotspot)
const currentLead = computed(() => timeline.value[currentIndex.value]?.leadHour ?? 0)
const rankedProvinces = computed(() => (overviewData.value.ranking || []).slice(0, 12))
const roundLabel = computed(() => {
  const item = timeline.value[currentIndex.value]
  if (!item) return ''
  const day = Math.floor(item.leadHour / 24)
  const hour = item.leadHour % 24
  return `第${day}天 ${String(hour).padStart(2, '0')}时（+${String(item.leadHour).padStart(3, '0')}h）`
})
const dayMarks = computed(() => {
  const total = Math.max(1, timeline.value.length - 1)
  return timeline.value
    .filter((t) => t.leadHour % 24 === 0 && t.leadHour > 0)
    .map((t) => ({ index: t.index, left: `${(t.index / total) * 100}%`, label: `D${t.leadHour / 24}` }))
})

function riskKeyOf(value) {
  if (value >= 60) return 'red'
  if (value >= 35) return 'orange'
  if (value >= 20) return 'yellow'
  if (value >= 10) return 'blue'
  return 'green'
}

function rankWidth(value) {
  const max = Number(stat.value.maximum || 1)
  return Math.max(4, Math.min(100, (Number(value) / Math.max(0.001, max)) * 100))
}

/* ------------------------------------------------------------ 数据加载 */

async function loadOverview() {
  const token = ++fetchToken
  loading.value = true
  try {
    const data = await api.overview(currentLead.value, accumulation.value, 1)
    if (token !== fetchToken) return
    overviewData.value = data
    await nextTick()
    renderMap()
    renderStrip()
  } catch (error) {
    if (token === fetchToken) overviewData.value = { ...overviewData.value, error: error.message }
  } finally {
    if (token === fetchToken) loading.value = false
  }
}

async function loadPoint(lon, lat) {
  try {
    pointData.value = await api.point(lon, lat, 'tp')
    await nextTick()
    renderPoint()
  } catch { /* 单点失败不阻断主流程 */ }
}

/* ------------------------------------------------------------ 渲染 */

function renderMap() {
  mapChart = mountChart(mapEl.value) || mapChart
  if (!mapChart) return
  const points = baseMap.value === 'precip' ? overviewData.value.points || [] : []
  const series = []
  if (points.length) {
    series.push(precipHeatSeries(points, {
      name: '降水',
      unit: overviewData.value.unit || 'mm/6h',
      opacity: 0.88,
    }))
  }
  mapChart.setOption(
    {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'item', confine: true },
      geo: geoOption({ zoom: 1.72, center: CHINA_DOMAIN_CENTER, roam: false }),
      series,
    },
    true,
  )
  mapChart.off('click')
  mapChart.on('click', (params) => {
    if (params.value?.length >= 2) {
      loadPoint(params.value[0], params.value[1])
      emit('point-selected', { lon: params.value[0], lat: params.value[1] })
    }
  })
}

function renderStrip() {
  stripChart = mountChart(stripEl.value) || stripChart
  if (!stripChart || !timeline.value.length) return
  const series = timeline.value.map((t) => {
    const match = (overviewData.value.ranking || [])[0]
    return { ...t, value: match ? Math.max(0.1, match.value) : 0.1 }
  })
  stripChart.setOption(timelineStripOption(series, currentIndex.value, { unit: overviewData.value.unit }), true)
}

function renderPoint() {
  pointChart = mountChart(pointEl.value) || pointChart
  if (!pointChart || !pointData.value.series) return
  const series = pointData.value.series
  pointChart.setOption(
    leadCurveOption(
      [{ name: '逐6小时降水', color: '#5fd8ff', data: series.map((s) => s.value) }],
      {
        xLabels: series.map((s) => s.label || `+${s.leadHour}h`),
        yUnit: 'mm/6h',
        yName: 'mm/6h',
      },
    ),
    true,
  )
}

/* ------------------------------------------------------------ 交互 */

function setAccumulation(value) {
  accumulation.value = value
  loadOverview()
}

function onRangeInput(event) {
  currentIndex.value = Number(event.target.value)
}

function onStripClick(event) {
  const rect = event.currentTarget.getBoundingClientRect()
  const ratio = (event.clientX - rect.left) / rect.width
  currentIndex.value = Math.round(ratio * Math.max(0, timeline.value.length - 1))
}

function stepLead(delta) {
  const total = timeline.value.length
  if (!total) return
  currentIndex.value = (currentIndex.value + delta + total) % total
}

function togglePlay() {
  playing.value = !playing.value
}

async function playNext() {
  if (!playing.value) return
  stepLead(1)
  await loadOverview()
  if (!playing.value) return
  playTimer = setTimeout(playNext, playSpeed.value)
}

function onProvinceChange() {
  if (!province.value) {
    mapChart?.setOption({ geo: { center: [104.5, 36], zoom: 1.72 } })
    return
  }
  const item = provinceList.value.find((p) => p.name === province.value)
  if (item) {
    mapChart?.setOption({ geo: { center: [item.lon, item.lat], zoom: 3.1 } })
    loadPoint(item.lon, item.lat)
  }
}

function resetView() {
  province.value = ''
  mapChart?.setOption({ geo: { center: [104.5, 36], zoom: 1.72 } })
}

function pickProvince(item) {
  selectedProvinceForPoint.value = item.name
  province.value = item.name
  mapChart?.setOption({ geo: { center: [item.lon, item.lat], zoom: 3.1 } })
  loadPoint(item.lon, item.lat)
  emit('point-selected', { lon: item.lon, lat: item.lat, name: item.name })
}

function gotoPointDetail() {
  if (pointData.value?.requested) emit('point-selected', pointData.value.requested)
  else emit('navigate', { view: 'point' })
}

/* ------------------------------------------------------------ 生命周期 */

watch(currentIndex, () => loadOverview())
watch(accumulation, () => renderStrip())
watch(playing, (value) => {
  clearTimeout(playTimer)
  if (value) playTimer = setTimeout(playNext, 300)
})

function onResize() {
  mapChart?.resize()
  stripChart?.resize()
  pointChart?.resize()
}

async function bootstrap() {
  try {
    const [tl, prov] = await Promise.all([api.timeline(), api.provinces()])
    timeline.value = tl
    provinceList.value = prov
    // 默认定位到第 4 个时次（+24h）
    currentIndex.value = Math.min(4, Math.max(0, tl.length - 1))
    await loadOverview()
    renderStrip()
    const first = (overviewData.value.ranking || [])[0]
    await loadPoint(first?.lon ?? 113.3, first?.lat ?? 23.1)
  } catch (error) {
    overviewData.value = { ...overviewData.value, error: error.message }
  }
}

onMounted(() => {
  bootstrap()
  window.addEventListener('resize', onResize)
})

onBeforeUnmount(() => {
  clearTimeout(playTimer)
  window.removeEventListener('resize', onResize)
  disposeChart(mapEl.value)
  disposeChart(stripEl.value)
  disposeChart(pointEl.value)
})

defineExpose({ refresh: bootstrap, loadOverview })
</script>

<style scoped>
.overview-layout {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(268px, 20%) minmax(560px, 1fr) minmax(290px, 22%);
  gap: 12px;
}

.ov-side {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 0;
}

.ov-center {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 0;
}

.metric-grid.cols-2 { grid-template-columns: 1fr 1fr; }

/* 工具栏 */
.map-toolbar {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
  padding: 9px 13px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: linear-gradient(120deg, rgba(15, 38, 72, 0.8), rgba(8, 22, 46, 0.86));
}
.tb-group { display: flex; align-items: center; gap: 8px; }
.tb-group.right { margin-left: auto; }
.tb-label { font-size: 10px; color: var(--text-faint); letter-spacing: 0.08em; white-space: nowrap; }
.tb-select {
  height: 28px;
  padding: 0 8px;
  border: 1px solid var(--line);
  border-radius: var(--radius-s);
  background: rgba(6, 18, 40, 0.85);
  color: var(--text);
  font-size: 11.5px;
  outline: none;
}
.tb-select option { background: #0b1f3f; }

/* 地图 */
.map-stage {
  position: relative;
  flex: 1;
  min-height: 320px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  overflow: hidden;
  background:
    radial-gradient(ellipse 62% 55% at 50% 48%, rgba(32, 92, 168, 0.22), transparent 72%),
    linear-gradient(165deg, rgba(10, 28, 58, 0.9), rgba(5, 14, 33, 0.95));
}
.map-canvas { width: 100%; height: 100%; }

.map-hud {
  position: absolute;
  top: 10px; right: 10px;
  z-index: 4;
  display: grid;
  gap: 3px;
  padding: 8px 10px;
  border: 1px solid var(--line);
  border-radius: var(--radius-s);
  background: rgba(6, 18, 40, 0.82);
  backdrop-filter: blur(4px);
}
.hud-row { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
.hud-row span { font-size: 9px; color: var(--text-faint); letter-spacing: 0.06em; }
.hud-row strong { font-family: var(--font-mono); font-size: 11px; color: var(--cyan-soft); font-weight: 600; }

.map-legend-box {
  position: absolute;
  left: 10px; bottom: 10px;
  z-index: 4;
  width: 236px;
  padding: 8px 10px;
  border: 1px solid var(--line);
  border-radius: var(--radius-s);
  background: rgba(6, 18, 40, 0.84);
  backdrop-filter: blur(4px);
}
.ml-title { font-size: 10px; color: var(--text-dim); margin-bottom: 5px; letter-spacing: 0.04em; }
.ml-ramp { display: flex; height: 9px; border-radius: 2px; overflow: hidden; border: 1px solid rgba(88, 148, 216, 0.3); }
.ml-ramp i { flex: 1; }
.ml-labels {
  display: flex;
  justify-content: space-between;
  margin-top: 3px;
  font-family: var(--font-mono);
  font-size: 8.5px;
  color: var(--text-faint);
}

/* 降水中心卡 */
.hotspot-card {
  margin-top: 12px;
  padding: 10px 11px;
  border: 1px solid var(--line);
  border-left: 3px solid var(--amber);
  border-radius: var(--radius-s);
  background: rgba(6, 18, 40, 0.6);
}
.hs-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; font-size: 10.5px; color: var(--text-dim); }
.hs-body { display: grid; gap: 4px; margin-top: 8px; }
.hs-body > div { display: flex; justify-content: space-between; gap: 10px; }
.hs-body span { font-size: 10px; color: var(--text-faint); }
.hs-body strong { font-size: 10.5px; color: var(--text); font-weight: 500; font-family: var(--font-mono); }

/* 时间轴 */
.timeline-panel { flex: 0 0 auto; }
.timeline-strip { width: 100%; height: 26px; cursor: pointer; }
.timeline-range {
  width: 100%;
  height: 16px;
  margin: 2px 0 0;
  appearance: none;
  background: transparent;
  outline: none;
}
.timeline-range::-webkit-slider-runnable-track {
  height: 3px;
  border-radius: 2px;
  background: linear-gradient(90deg, rgba(95, 216, 255, 0.55), rgba(74, 158, 255, 0.3));
}
.timeline-range::-webkit-slider-thumb {
  appearance: none;
  width: 13px; height: 13px;
  margin-top: -5px;
  border-radius: 50%;
  border: 2px solid #04121f;
  background: var(--cyan);
  box-shadow: 0 0 10px rgba(95, 216, 255, 0.8);
  cursor: pointer;
}

.timeline-marks { position: relative; height: 12px; }
.timeline-marks span {
  position: absolute;
  transform: translateX(-50%);
  font-family: var(--font-mono);
  font-size: 8.5px;
  color: var(--text-faint);
}

.timeline-info {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 5px;
  font-size: 10.5px;
  color: var(--text-dim);
}
.ti-cur b { color: var(--cyan-soft); font-family: var(--font-mono); }
.ti-range { color: var(--text-faint); font-size: 10px; }

/* 排行 */
.rank-list { display: grid; gap: 3px; }
.rank-item {
  display: grid;
  grid-template-columns: 22px 54px 1fr 48px;
  gap: 7px;
  align-items: center;
  width: 100%;
  padding: 5px 4px;
  border-radius: var(--radius-s);
  border: 1px solid transparent;
  background: transparent;
  text-align: left;
  transition: background 0.16s, border-color 0.16s;
}
.rank-item:hover { background: rgba(74, 158, 255, 0.1); }
.rank-item.selected { border-color: rgba(95, 216, 255, 0.42); background: rgba(95, 216, 255, 0.1); }
.rank-no {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--text-faint);
  text-align: center;
}
.rank-no.n1 { color: #ff7a8a; }
.rank-no.n2 { color: #ffb45c; }
.rank-no.n3 { color: #ffd85c; }
.rank-name { font-size: 11.5px; color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.rank-bar { height: 5px; border-radius: 3px; background: rgba(12, 34, 66, 0.9); overflow: hidden; }
.rank-bar i {
  display: block;
  height: 100%;
  border-radius: 3px;
  background: linear-gradient(90deg, #38a6dc, #5fd8ff);
  box-shadow: 0 0 8px rgba(95, 216, 255, 0.4);
}
.rank-item strong { font-family: var(--font-mono); font-size: 10.5px; color: var(--cyan-soft); text-align: right; }

/* 单点快览 */
.point-coord { margin: 0 0 8px; font-size: 10.5px; color: var(--text-dim); display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.coord-tag {
  padding: 2px 6px;
  border-radius: 8px;
  border: 1px solid var(--line);
  font-size: 9px;
  color: var(--text-faint);
}
.point-mini-chart { flex: 1; min-height: 108px; }
.mini-summary {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 6px;
  margin: 8px 0;
}
.mini-summary > div {
  padding: 7px 8px;
  border: 1px solid var(--line);
  border-radius: var(--radius-s);
  background: rgba(6, 18, 40, 0.55);
}
.mini-summary span { display: block; font-size: 9px; color: var(--text-faint); }
.mini-summary strong { display: block; margin-top: 4px; font-family: var(--font-mono); font-size: 11.5px; color: var(--cyan-soft); }
.btn.full { width: 100%; }
</style>
