<template>
  <main class="page-surface">
    <header class="page-head rise-in">
      <div class="ph-left">
        <div class="ph-kicker"><i></i><span>Multi-Element Field · Module 04</span></div>
        <h2>多要素切换场</h2>
        <p class="ph-desc">
          穹宇AI模型同时输出地面与高空共 9 类气象要素场。可切换查看各要素在中国区域的空间分布、
          极值统计与风场结构，用于解释降水系统的动力与水汽条件。当前要素：
          <b>{{ field.name || '--' }}</b>，有效时间 {{ formatFull(field.validTime) }}。
        </p>
      </div>
      <div class="ph-right">
        <span class="module-tag"><b>04</b> 必备功能</span>
        <span class="required-tag must">核心必备</span>
      </div>
    </header>

    <div class="field-layout">
      <!-- 要素选择 -->
      <aside class="field-side">
        <section class="panel" style="flex:0 0 auto">
          <div class="panel-head">
            <div class="panel-title"><i class="bar"></i><h3>要素清单</h3></div>
            <span class="panel-sub">9 Variables</span>
          </div>
          <div class="panel-body">
            <div class="var-groups">
              <div v-for="group in groupedVariables" :key="group.label" class="var-group">
                <div class="vg-label">
                  <AppIcon :name="group.icon" :size="12" />
                  <span>{{ group.label }}</span>
                  <em>{{ group.items.length }}</em>
                </div>
                <button
                  v-for="item in group.items"
                  :key="item.key"
                  class="var-item"
                  :class="{ active: selected === item.key }"
                  @click="selectVariable(item.key)"
                >
                  <span class="vi-dot" :style="{ background: item.key === 'tp' ? '#5fd8ff' : '#4a9eff' }"></span>
                  <span class="vi-name">{{ item.name }}</span>
                  <em>{{ item.unit }}</em>
                </button>
              </div>
            </div>
          </div>
        </section>

        <section class="panel" v-if="field.description">
          <div class="panel-head">
            <div class="panel-title"><i class="bar"></i><h3>要素说明</h3></div>
          </div>
          <div class="panel-body">
            <p class="var-desc">{{ field.description }}</p>
            <div class="var-meta">
              <div><span>数据来源</span><strong>{{ field.kind === 'wind' ? 'U/V 分量合成' : field.name }}</strong></div>
              <div><span>所属文件</span><strong>{{ fieldKindLabel }}</strong></div>
              <div><span>单位口径</span><strong>{{ field.unit }}</strong></div>
            </div>
          </div>
        </section>
      </aside>

      <!-- 地图 -->
      <section class="field-center">
        <div class="map-toolbar">
          <div class="tb-group">
            <span class="tb-label">预报时效</span>
            <div class="seg">
              <button v-for="lv in leadPresets" :key="lv.value"
                      :class="{ active: leadHour === lv.value }"
                      @click="setLead(lv.value)">{{ lv.label }}</button>
            </div>
          </div>
          <div class="tb-group">
            <span class="tb-label">精细度</span>
            <div class="seg">
              <button v-for="s in strides" :key="s.value"
                      :class="{ active: stride === s.value }"
                      @click="setStride(s.value)">{{ s.label }}</button>
            </div>
          </div>
          <div class="tb-group right">
            <div class="seg">
              <button :class="{ active: showArrows }" :disabled="field.kind !== 'wind'" @click="showArrows = !showArrows">
                风向箭头
              </button>
            </div>
          </div>
        </div>

        <div class="map-stage">
          <div ref="mapEl" class="map-canvas"></div>
          <div v-if="loading" class="loading-veil"><div class="spinner"></div><span>加载 {{ field.name }}…</span></div>

          <div class="map-hud">
            <div class="hud-row"><span>要素</span><strong>{{ field.shortName || '--' }}</strong></div>
            <div class="hud-row"><span>有效</span><strong>{{ formatShort(field.validTime) }}</strong></div>
            <div class="hud-row"><span>时效</span><strong>+{{ String(field.leadHour || 0).padStart(3, '0') }}h</strong></div>
          </div>

          <div class="map-legend-box">
            <div class="ml-title">{{ field.name }}（{{ field.unit }}）</div>
            <div class="ml-ramp">
              <i v-for="(c, i) in field.palette || []" :key="i" :style="{ background: c }"></i>
            </div>
            <div class="ml-labels">
              <span>{{ num(field.statistics?.minimum) }}</span>
              <span>{{ num(field.statistics?.average) }}</span>
              <span>{{ num(field.statistics?.maximum) }}</span>
            </div>
          </div>
        </div>
      </section>

      <!-- 统计与趋势 -->
      <aside class="field-side right">
        <section class="panel" style="flex:0 0 auto">
          <div class="panel-head">
            <div class="panel-title"><i class="bar"></i><h3>要素统计</h3></div>
            <span class="panel-sub">{{ formatShort(field.validTime) }}</span>
          </div>
          <div class="panel-body">
            <div class="metric-grid cols-2">
              <div class="metric" style="--accent:#ff7a8a">
                <span>最大值</span><strong>{{ num(field.statistics?.maximum) }}<em>{{ field.unit }}</em></strong>
              </div>
              <div class="metric" style="--accent:#5fd8ff">
                <span>平均值</span><strong>{{ num(field.statistics?.average) }}<em>{{ field.unit }}</em></strong>
              </div>
              <div class="metric" style="--accent:#3fd8b0">
                <span>最小值</span><strong>{{ num(field.statistics?.minimum) }}<em>{{ field.unit }}</em></strong>
              </div>
              <div class="metric" style="--accent:#ffc94d">
                <span>P95</span><strong>{{ num(field.statistics?.p95) }}<em>{{ field.unit }}</em></strong>
              </div>
            </div>
          </div>
        </section>

        <section class="panel" style="flex:1">
          <div class="panel-head">
            <div class="panel-title"><i class="bar"></i><h3>逐时效趋势</h3></div>
            <span class="panel-sub">{{ pointRegion }}</span>
          </div>
          <div class="panel-body">
            <p class="point-coord">
              {{ pointRegion }} · {{ pointGrid.lon ?? '--' }}°E，{{ pointGrid.lat ?? '--' }}°N
            </p>
            <div ref="trendEl" class="trend-chart"></div>
            <div class="trend-note">
              在左侧地图点击任意格点，可查看该点全时效 {{ field.shortName }} 变化曲线。
            </div>
          </div>
        </section>
      </aside>
    </div>
  </main>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import AppIcon from './AppIcon.vue'
import api from '../api'
import {
  mountChart, disposeChart, scalarHeatSeries, windArrowSeries, geoOption,
  leadCurveOption, formatShort, formatFull, num,
  PRECIP_BREAKS, PRECIP_COLORS, equalBreaks, gradeVisualMap,
  CHINA_DOMAIN, CHINA_DOMAIN_CENTER,
} from '../chartKit'

const leadPresets = [
  { value: 6, label: '+06h' },
  { value: 24, label: '+24h' },
  { value: 72, label: '+72h' },
  { value: 168, label: '+168h' },
  { value: 360, label: '+360h' },
]
const strides = [
  { value: 1, label: '0.25°' },
  { value: 2, label: '0.5°' },
  { value: 4, label: '1.0°' },
]

const variables = ref([])
const selected = ref('tp')
const leadHour = ref(24)
const stride = ref(1)
const showArrows = ref(true)
const field = ref({ palette: [] })
const loading = ref(false)
const pointRegion = ref('未选择格点')
const pointGrid = ref({})

const mapEl = ref(null)
const trendEl = ref(null)
let mapChart = null
let trendChart = null
let token = 0

const groupedVariables = computed(() => {
  const surface = variables.value.filter((v) => v.file === 'SURFACE')
  const high = variables.value.filter((v) => v.file === 'PLEVELS')
  return [
    { label: '地面要素', icon: 'globe', items: surface },
    { label: '高空要素', icon: 'layers', items: high },
  ].filter((g) => g.items.length)
})

const fieldKindLabel = computed(() => (variables.value.find((v) => v.key === selected.value)?.file === 'PLEVELS' ? 'PLEVELS（等压面）' : 'SURFACE（地面）'))

/* ------------------------------------------------------------ 加载 */

async function loadField() {
  const myToken = ++token
  loading.value = true
  try {
    const data = await api.variableField(selected.value, leadHour.value, stride.value)
    if (myToken !== token) return
    field.value = data
    await nextTick()
    renderMap()
  } catch (error) {
    if (myToken === token) field.value = { ...field.value, error: error.message, palette: [] }
  } finally {
    if (myToken === token) loading.value = false
  }
}

async function loadTrend(lon, lat) {
  try {
    const data = await api.point(lon, lat, selected.value)
    pointRegion.value = data.region || '所选格点'
    pointGrid.value = data.gridPoint || {}
    await nextTick()
    renderTrend(data)
  } catch { /* 忽略 */ }
}

/* ------------------------------------------------------------ 渲染 */

function renderMap() {
  mapChart = mountChart(mapEl.value) || mapChart
  if (!mapChart) return
  const series = []
  const stat = field.value.statistics || {}
  const palette = field.value.palette || PRECIP_COLORS
  // 非降水要素（气温/气压/风/高度）可为负值且量纲各异，
  // 按其自身取值范围做等分色阶；降水要素沿用气象分级阈值。
  const isPrecip = field.value.kind === 'precipitation'
  const breaks = isPrecip
    ? PRECIP_BREAKS
    : equalBreaks(stat.minimum ?? 0, stat.maximum ?? 1, palette.length)
  if (field.value.points?.length) {
    series.push(scalarHeatSeries(field.value.points, {
      name: field.value.name,
      unit: field.value.unit,
      breaks,
      colors: palette,
      opacity: 0.88,
      z: 2,
    }))
  }
  if (showArrows.value && field.value.kind === 'wind' && field.value.arrows?.length) {
    series.push(windArrowSeries(field.value.arrows, field.value.unit))
  }
  mapChart.setOption(
    {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'item', confine: true },
      // 锁定 geo 视窗到数据范围，保证栅格填色与底图严格对齐、且不溢出面板
      geo: geoOption({ zoom: 1.72, center: CHINA_DOMAIN_CENTER, roam: false }),
      visualMap: gradeVisualMap(breaks, palette, field.value.unit),
      series,
    },
    true,
  )
  mapChart.off('click')
  mapChart.on('click', (params) => {
    if (params.value?.length >= 2) loadTrend(params.value[0], params.value[1])
  })
}

function renderTrend(data) {
  trendChart = mountChart(trendEl.value) || trendChart
  if (!trendChart) return
  trendChart.setOption(
    leadCurveOption(
      [{ name: data.variable?.shortName || '要素', color: '#5fd8ff', data: data.series.map((s) => s.value) }],
      { xLabels: data.series.map((s) => `+${s.leadHour}h`), yUnit: data.unit, yName: data.unit },
    ),
    true,
  )
}

/* ------------------------------------------------------------ 交互 */

function selectVariable(key) {
  selected.value = key
  showArrows.value = true
  loadField()
}

function setLead(value) { leadHour.value = value; loadField() }
function setStride(value) { stride.value = value; loadField() }

function onResize() {
  mapChart?.resize()
  trendChart?.resize()
}

onMounted(async () => {
  try {
    variables.value = await api.variables()
  } catch { /* 忽略 */ }
  await loadField()
  await loadTrend(113.3, 23.1)
  window.addEventListener('resize', onResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  disposeChart(mapEl.value)
  disposeChart(trendEl.value)
})

defineExpose({ refresh: loadField })
</script>

<style scoped>
.field-layout {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(228px, 17%) minmax(560px, 1fr) minmax(258px, 20%);
  gap: 12px;
}
.field-side { display: flex; flex-direction: column; gap: 12px; min-height: 0; }
.field-center { display: flex; flex-direction: column; gap: 12px; min-height: 0; }
.metric-grid.cols-2 { grid-template-columns: 1fr 1fr; }

.var-groups { display: grid; gap: 12px; }
.var-group { display: grid; gap: 3px; }
.vg-label {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 3px 2px 6px;
  font-size: 10px;
  color: var(--text-faint);
  letter-spacing: 0.1em;
}
.vg-label em {
  margin-left: auto;
  padding: 1px 6px;
  border-radius: 8px;
  background: rgba(74, 158, 255, 0.16);
  color: var(--cyan-soft);
  font-style: normal;
  font-family: var(--font-mono);
  font-size: 9px;
}
.var-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 7px 9px;
  border: 1px solid transparent;
  border-radius: var(--radius-s);
  background: rgba(6, 18, 40, 0.5);
  color: var(--text-dim);
  font-size: 11.5px;
  text-align: left;
  transition: all 0.16s;
}
.var-item:hover { border-color: var(--line); color: var(--text); background: rgba(74, 158, 255, 0.1); }
.var-item.active {
  border-color: rgba(95, 216, 255, 0.5);
  background: rgba(95, 216, 255, 0.13);
  color: var(--cyan-soft);
  font-weight: 600;
}
.vi-dot { width: 5px; height: 5px; border-radius: 50%; flex: 0 0 5px; }
.vi-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.var-item em { font-style: normal; font-size: 9.5px; color: var(--text-faint); font-family: var(--font-mono); }

.var-desc { margin: 0; font-size: 11px; line-height: 1.75; color: var(--text-dim); }
.var-meta { display: grid; gap: 6px; margin-top: 10px; }
.var-meta > div { display: flex; justify-content: space-between; gap: 10px; padding-bottom: 5px; border-bottom: 1px solid rgba(88, 148, 216, 0.1); }
.var-meta span { font-size: 10px; color: var(--text-faint); }
.var-meta strong { font-size: 10.5px; color: var(--text); font-weight: 500; text-align: right; }

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
.seg button:disabled { opacity: 0.38; cursor: not-allowed; }

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
  position: absolute; top: 10px; right: 10px; z-index: 4;
  display: grid; gap: 3px; padding: 8px 10px;
  border: 1px solid var(--line); border-radius: var(--radius-s);
  background: rgba(6, 18, 40, 0.82); backdrop-filter: blur(4px);
}
.hud-row { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
.hud-row span { font-size: 9px; color: var(--text-faint); }
.hud-row strong { font-family: var(--font-mono); font-size: 11px; color: var(--cyan-soft); font-weight: 600; }
.map-legend-box {
  position: absolute; left: 10px; bottom: 10px; z-index: 4; width: 236px;
  padding: 8px 10px; border: 1px solid var(--line); border-radius: var(--radius-s);
  background: rgba(6, 18, 40, 0.84); backdrop-filter: blur(4px);
}
.ml-title { font-size: 10px; color: var(--text-dim); margin-bottom: 5px; }
.ml-ramp { display: flex; height: 9px; border-radius: 2px; overflow: hidden; border: 1px solid rgba(88, 148, 216, 0.3); }
.ml-ramp i { flex: 1; }
.ml-labels {
  display: flex; justify-content: space-between; margin-top: 3px;
  font-family: var(--font-mono); font-size: 8.5px; color: var(--text-faint);
}

.point-coord { margin: 0 0 8px; font-size: 10.5px; color: var(--text-dim); }
.trend-chart { flex: 1; min-height: 150px; }
.trend-note { margin-top: 7px; font-size: 9.5px; color: var(--text-faint); line-height: 1.6; }
</style>
