<template>
  <main class="page-surface">
    <header class="page-head rise-in">
      <div class="ph-left">
        <div class="ph-kicker"><i></i><span>Point Forecast · Module 05</span></div>
        <h2>单点预报详情</h2>
        <p class="ph-desc">
          针对任意经纬度格点，输出当前启用批次的可用逐6小时要素序列。
          降水展示逐日累计和有雨时段；风速展示逐日最大值；其他要素展示逐日样本平均值，
          用于面向具体站点的精细化解读。
        </p>
      </div>
      <div class="ph-right">
        <span class="module-tag"><b>05</b> 必备功能</span>
        <span class="required-tag must">核心必备</span>
      </div>
    </header>

    <!-- 查询条件 -->
    <section class="panel query-panel">
      <div class="panel-body query-body">
        <div class="field" style="width:150px">
          <label>省级行政区</label>
          <select v-model="province" @change="onProvinceChange">
            <option value="">请选择</option>
            <option v-for="p in provinceList" :key="p.name" :value="p.name">{{ p.name }}</option>
          </select>
        </div>
        <div class="field" style="width:130px">
          <label>经度 (°E)</label>
          <input v-model.number="lon" type="number" step="0.25" min="70" max="140" />
        </div>
        <div class="field" style="width:130px">
          <label>纬度 (°N)</label>
          <input v-model.number="lat" type="number" step="0.25" min="12" max="56" />
        </div>
        <div class="field" style="width:190px">
          <label>气象要素</label>
          <select v-model="variable">
            <option v-for="v in variables" :key="v.key" :value="v.key">{{ v.name }}（{{ v.unit }}）</option>
          </select>
        </div>
        <button class="btn primary" :disabled="loading" @click="loadPoint">
          <AppIcon name="search" :size="14" />查询预报
        </button>
        <div class="quick-picks">
          <span>快捷城市</span>
          <button v-for="city in quickCities" :key="city.name" class="chip" @click="pickCity(city)">{{ city.name }}</button>
        </div>
      </div>
    </section>

    <div v-if="loading" class="panel" style="flex:1;justify-content:center">
      <div class="skeleton" style="height:180px"></div>
      <p style="text-align:center;font-size:11px;color:var(--text-faint);margin-top:10px">
        正在读取该格点 60 个时效的预报序列…
      </p>
    </div>

    <div v-else-if="point.error" class="notice-banner notice-error">{{ point.error }}</div>
    <div v-else class="point-layout">
      <!-- 左：位置与摘要 -->
      <aside class="point-side">
        <section class="panel" style="flex:0 0 auto">
          <div class="panel-head">
            <div class="panel-title"><i class="bar"></i><h3>格点位置</h3></div>
            <span class="panel-sub">Grid Point</span>
          </div>
          <div class="panel-body">
            <div class="coord-box">
              <div class="cb-main">
                <span>最近网格点</span>
                <strong>{{ point.gridPoint?.lon ?? '--' }}°E<br />{{ point.gridPoint?.lat ?? '--' }}°N</strong>
              </div>
              <div class="cb-sub">
                <div><span>所属区域</span><strong>{{ point.region || '--' }}</strong></div>
                <div><span>请求坐标</span><strong>{{ point.requested?.lon }}°E，{{ point.requested?.lat }}°N</strong></div>
                <div><span>网格分辨率</span><strong>{{ point.gridPoint?.resolution ?? 0.25 }}°</strong></div>
              </div>
            </div>
            <div ref="miniMapEl" class="mini-map"></div>
          </div>
        </section>

        <section class="panel" style="flex:0 0 auto">
          <div class="panel-head">
            <div class="panel-title"><i class="bar"></i><h3>序列摘要</h3></div>
            <span class="panel-sub">{{ point.variable?.name }}</span>
          </div>
          <div class="panel-body">
            <div class="metric-grid cols-2">
              <div class="metric" style="--accent:#ff7a8a">
                <span>峰值</span><strong>{{ num(point.summary?.maximum) }}<em>{{ point.unit }}</em></strong>
                <small>{{ point.summary?.maximumTime ? formatShort(point.summary.maximumTime) : '--' }}</small>
              </div>
              <div class="metric" style="--accent:#5fd8ff">
                <span>{{ isPrecip ? '已加载时效累计' : '最低值' }}</span><strong>{{ num(isPrecip ? point.summary?.total : point.summary?.minimum) }}<em>{{ isPrecip ? 'mm' : point.unit }}</em></strong>
                <small>{{ isPrecip ? '全程累计量' : '全时段最小值' }}</small>
              </div>
              <div class="metric" style="--accent:#3fd8b0">
                <span>平均</span><strong>{{ num(point.summary?.average) }}<em>{{ point.unit }}</em></strong>
                <small>逐6小时均值</small>
              </div>
              <div class="metric" style="--accent:#ffc94d">
                <span>{{ isPrecip ? '有雨时段' : '有效样本' }}</span><strong>{{ (isPrecip ? point.summary?.rainyPeriods : point.summary?.sampleCount) ?? '--' }}<em>个</em></strong>
                <small>共 {{ point.series?.length || 0 }} 个时次</small>
              </div>
            </div>
            <div class="peak-note" v-if="point.summary?.maximumLead">
              <AppIcon name="alert" :size="12" />
              峰值出现在第 {{ Math.ceil(point.summary.maximumLead / 24) }} 天
              （+{{ String(point.summary.maximumLead).padStart(3, '0') }}h），
              强度 {{ num(point.summary.maximum) }} {{ point.unit }}。
            </div>
          </div>
        </section>

        <section class="panel" v-if="point.thresholds?.length">
          <div class="panel-head">
            <div class="panel-title"><i class="bar"></i><h3>分级时段统计</h3></div>
            <span class="panel-sub">Intensity Bands</span>
          </div>
          <div class="panel-body">
            <div ref="bandEl" class="band-chart"></div>
          </div>
        </section>
      </aside>

      <!-- 中：曲线 -->
      <section class="point-center">
        <section class="panel" style="flex:0 0 auto">
          <div class="panel-head">
            <div class="panel-title">
              <i class="bar"></i>
              <h3>逐6小时序列</h3>
              <span class="panel-sub">{{ point.series?.length || 0 }} Time Steps</span>
            </div>
            <div class="panel-extra">
              <div class="seg">
                <button :class="{ active: curveMode === 'lead' }" @click="curveMode = 'lead'">逐6小时</button>
                <button :class="{ active: curveMode === 'daily' }" @click="curveMode = 'daily'">{{ point.dailyLabel || '逐日统计' }}</button>
              </div>
            </div>
          </div>
          <div class="panel-body">
            <div ref="mainCurveEl" class="main-curve"></div>
          </div>
        </section>

        <section class="panel" style="flex:0 0 auto">
          <div class="panel-head">
            <div class="panel-title"><i class="bar"></i><h3>{{ point.dailyLabel || '逐日统计' }}</h3></div>
            <span class="panel-sub">Day 1—15</span>
          </div>
          <div class="panel-body">
            <div ref="dailyBarEl" class="daily-bar"></div>
          </div>
        </section>
      </section>

      <!-- 右：时序表 -->
      <aside class="point-side right">
        <section class="panel" style="flex:1">
          <div class="panel-head">
            <div class="panel-title"><i class="bar"></i><h3>时序明细</h3></div>
            <span class="panel-sub">{{ point.series?.length || 0 }} 条</span>
          </div>
          <div class="panel-body scroll-y">
            <table class="data-table">
              <thead>
                <tr><th>时效</th><th>有效时间</th><th style="text-align:right">数值</th></tr>
              </thead>
              <tbody>
                <tr v-for="row in point.series || []" :key="row.leadHour"
                    :class="{ highlight: row.leadHour === point.summary?.maximumLead }">
                  <td class="strong">+{{ String(row.leadHour).padStart(3, '0') }}h</td>
                  <td>{{ formatShort(row.validTime) }}</td>
                  <td class="num">{{ num(row.value) }}</td>
                </tr>
              </tbody>
            </table>
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
  mountChart, disposeChart, leadCurveOption, compareBarOption, donutOption, geoOption,
  formatShort, num,
} from '../chartKit'

const quickCities = [
  { name: '北京', lon: 116.41, lat: 39.9 },
  { name: '上海', lon: 121.47, lat: 31.23 },
  { name: '广州', lon: 113.28, lat: 23.13 },
  { name: '成都', lon: 104.07, lat: 30.67 },
  { name: '武汉', lon: 114.3, lat: 30.59 },
  { name: '哈尔滨', lon: 126.64, lat: 45.76 },
]

const props = defineProps({ selectedPoint: { type: Object, default: null } })
const provinceList = ref([])
const variables = ref([])
const province = ref(props.selectedPoint ? props.selectedPoint.name || '' : '浙江')
const lon = ref(props.selectedPoint?.lon ?? 120.15)
const lat = ref(props.selectedPoint?.lat ?? 30.28)
const variable = ref('tp')
const curveMode = ref('lead')
const point = ref({})
const loading = ref(false)
const isPrecip = computed(() => point.value.variable?.kind === 'precipitation')
let requestToken = 0
let mounted = false

const miniMapEl = ref(null)
const bandEl = ref(null)
const mainCurveEl = ref(null)
const dailyBarEl = ref(null)
let miniMapChart = null
let bandChart = null
let mainCurveChart = null
let dailyBarChart = null

/* ------------------------------------------------------------ 加载 */

async function loadPoint() {
  const token = ++requestToken
  for (const el of [miniMapEl.value, bandEl.value, mainCurveEl.value, dailyBarEl.value]) disposeChart(el)
  loading.value = true
  try {
    const result = await api.point(Number(lon.value), Number(lat.value), variable.value)
    if (token !== requestToken) return
    point.value = result
  } catch (error) {
    if (token === requestToken) point.value = { error: error.message, series: [] }
  } finally {
    if (token === requestToken) loading.value = false
  }
  if (token !== requestToken) return
  // 待 v-if / v-else 分支切换、图表容器挂载后再初始化 ECharts
  await nextTick()
  if (!point.value?.error) {
    renderMiniMap()
    renderMainCurve()
    renderDailyBar()
    renderBands()
  }
}

/* ------------------------------------------------------------ 渲染 */

function renderMiniMap() {
  miniMapChart = mountChart(miniMapEl.value) || miniMapChart
  if (!miniMapChart) return
  const gp = point.value.gridPoint || {}
  const lonv = Number(lon.value)
  const latv = Number(lat.value)
  miniMapChart.setOption(
    {
      backgroundColor: 'transparent',
      tooltip: { show: false },
      geo: geoOption({ center: [lonv, latv], zoom: 2.6, roam: false }),
      series: [
        {
          type: 'effectScatter',
          coordinateSystem: 'geo',
          symbolSize: 9,
          rippleEffect: { scale: 3, brushType: 'stroke' },
          itemStyle: { color: '#ff5c6e', shadowBlur: 12, shadowColor: '#ff5c6e' },
          label: {
            show: true,
            formatter: `请求点\n${lonv}°E, ${latv}°N`,
            position: 'right',
            color: '#e8f2ff',
            fontSize: 9,
            lineHeight: 13,
            backgroundColor: 'rgba(8,22,46,0.86)',
            padding: [3, 6],
            borderRadius: 3,
          },
          data: [{ value: [lonv, latv] }],
        },
        {
          type: 'scatter',
          coordinateSystem: 'geo',
          symbol: 'rect',
          symbolSize: 5,
          itemStyle: { color: '#5fd8ff', borderColor: '#04121f', borderWidth: 1 },
          data: [{ value: [gp.lon, gp.lat] }],
        },
      ],
    },
    true,
  )
}

function renderMainCurve() {
  mainCurveChart = mountChart(mainCurveEl.value) || mainCurveChart
  if (!mainCurveChart || !point.value.series?.length) return

  if (curveMode.value === 'daily') {
    const daily = point.value.daily || []
    mainCurveChart.setOption(
      compareBarOption(
        daily.map((d) => `第${d.day}天`),
        [{ name: point.value.dailyLabel, color: '#5fd8ff', colorEnd: '#2f86c8', gradient: true, data: daily.map((d) => d.value) }],
        { yUnit: point.value.dailyUnit },
      ),
      true,
    )
    return
  }

  const series = point.value.series
  const peak = point.value.summary?.maximumLead
  mainCurveChart.setOption(
    leadCurveOption(
      [{
        name: point.value.variable?.name || '要素',
        color: '#5fd8ff',
        data: series.map((s) => s.value),
        markLine: peak
          ? {
              silent: true,
              symbol: 'none',
              lineStyle: { color: 'rgba(255,92,110,0.65)', type: 'dashed' },
              data: [{ xAxis: series.findIndex((s) => s.leadHour === peak), label: { formatter: '峰值', color: '#ff7a8a', fontSize: 9 } }],
            }
          : null,
      }],
      { xLabels: series.map((s) => `+${s.leadHour}h`), yUnit: point.value.unit, yName: point.value.unit },
    ),
    true,
  )
}

function renderDailyBar() {
  dailyBarChart = mountChart(dailyBarEl.value) || dailyBarChart
  if (!dailyBarChart) return
  const daily = point.value.daily || []
  dailyBarChart.setOption(
    compareBarOption(
      daily.map((d) => `D${d.day}`),
      [{
        name: point.value.dailyLabel,
        color: '#3fd8b0',
        colorEnd: '#1f9d7c',
        gradient: true,
        data: daily.map((d) => d.value),
      }],
      { yUnit: point.value.dailyUnit },
    ),
    true,
  )
}

function renderBands() {
  bandChart = mountChart(bandEl.value) || bandChart
  if (!bandChart) return
  const rows = (point.value.thresholds || []).filter((r) => r.count > 0)
  bandChart.setOption(
    donutOption(
      rows.map((r) => ({ name: r.label, value: r.count, itemStyle: { color: r.color } })),
      {
        centerValue: String(point.value.summary?.rainyPeriods ?? 0),
        centerText: '有雨时段数',
        radius: ['48%', '72%'],
      },
    ),
    true,
  )
}

/* ------------------------------------------------------------ 交互 */

function onProvinceChange() {
  const item = provinceList.value.find((p) => p.name === province.value)
  if (item) {
    lon.value = item.lon
    lat.value = item.lat
    loadPoint()
  }
}

function pickCity(city) {
  lon.value = city.lon
  lat.value = city.lat
  province.value = city.name
  loadPoint()
}

function applyPoint(payload) {
  if (!payload || !Number.isFinite(Number(payload.lon)) || !Number.isFinite(Number(payload.lat))) return
  lon.value = Number(payload.lon)
  lat.value = Number(payload.lat)
  province.value = payload.name || ''
  if (mounted) return loadPoint()
}
watch(() => props.selectedPoint, (payload) => applyPoint(payload))

watch(curveMode, () => renderMainCurve())
watch(variable, () => loadPoint())

function onResize() {
  miniMapChart?.resize()
  bandChart?.resize()
  mainCurveChart?.resize()
  dailyBarChart?.resize()
}

onMounted(async () => {
  try {
    const [prov, vars] = await Promise.all([api.provinces(), api.variables()])
    provinceList.value = prov
    variables.value = vars
  } catch { /* 忽略 */ }
  mounted = true
  await loadPoint()
  window.addEventListener('resize', onResize)
})

onBeforeUnmount(() => {
  mounted = false
  requestToken++
  window.removeEventListener('resize', onResize)
  disposeChart(miniMapEl.value)
  disposeChart(bandEl.value)
  disposeChart(mainCurveEl.value)
  disposeChart(dailyBarEl.value)
})

defineExpose({ refresh: loadPoint, applyPoint })
</script>

<style scoped>
.query-panel { flex: 0 0 auto; }
.query-body {
  flex-direction: row;
  align-items: flex-end;
  gap: 12px;
  flex-wrap: wrap;
}
.quick-picks { display: flex; align-items: center; gap: 6px; margin-left: auto; }
.quick-picks > span { font-size: 10px; color: var(--text-faint); }
.chip {
  padding: 4px 10px;
  border-radius: 12px;
  border: 1px solid var(--line);
  background: rgba(6, 18, 40, 0.6);
  color: var(--text-dim);
  font-size: 11px;
  transition: all 0.16s;
}
.chip:hover { border-color: var(--cyan); color: var(--cyan-soft); background: rgba(95, 216, 255, 0.12); }

.point-layout {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(268px, 21%) minmax(520px, 1fr) minmax(216px, 16%);
  gap: 12px;
}
.point-side { display: flex; flex-direction: column; gap: 12px; min-height: 0; }
.point-center { display: flex; flex-direction: column; gap: 12px; min-height: 0; }
.metric-grid.cols-2 { grid-template-columns: 1fr 1fr; }

.coord-box {
  display: grid;
  gap: 9px;
  padding: 11px;
  border: 1px solid var(--line);
  border-radius: var(--radius-s);
  background: rgba(6, 18, 40, 0.55);
}
.cb-main { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.cb-main span { font-size: 10px; color: var(--text-faint); }
.cb-main strong {
  font-family: var(--font-mono);
  font-size: 14px;
  color: var(--cyan);
  font-weight: 600;
  text-align: right;
  line-height: 1.35;
}
.cb-sub { display: grid; gap: 4px; padding-top: 8px; border-top: 1px solid rgba(88, 148, 216, 0.12); }
.cb-sub > div { display: flex; justify-content: space-between; gap: 10px; }
.cb-sub span { font-size: 9.5px; color: var(--text-faint); }
.cb-sub strong { font-size: 10.5px; color: var(--text); font-weight: 500; font-family: var(--font-mono); }

.mini-map {
  width: 100%;
  height: 168px;
  margin-top: 10px;
  border: 1px solid var(--line);
  border-radius: var(--radius-s);
  overflow: hidden;
  background: radial-gradient(ellipse 66% 60% at 50% 50%, rgba(32, 92, 168, 0.2), transparent 72%), rgba(5, 14, 33, 0.8);
}

.peak-note {
  display: flex;
  align-items: flex-start;
  gap: 7px;
  margin-top: 11px;
  padding: 8px 10px;
  border-radius: var(--radius-s);
  border: 1px solid rgba(255, 92, 110, 0.24);
  border-left: 3px solid var(--red);
  background: rgba(66, 16, 26, 0.32);
  font-size: 10.5px;
  line-height: 1.65;
  color: #ffc4cb;
}

.band-chart { height: 178px; width: 100%; }
.main-curve { height: 232px; min-height: 232px; width: 100%; }
.daily-bar { height: 148px; width: 100%; }

.data-table tbody tr.highlight { background: rgba(255, 92, 110, 0.13); }
.data-table tbody tr.highlight td.strong { color: #ff9aa6; }
</style>
