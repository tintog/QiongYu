<template>
  <main class="page-surface">
    <header class="page-head rise-in">
      <div class="ph-left">
        <div class="ph-kicker"><i></i><span>Ensemble Probability · Module 08</span></div>
        <h2>集合与概率预报</h2>
        <p class="ph-desc">
          基于当前起报时间的集合预报产品 {{ info.ensembleProduct || '暂无同起报数据' }} 的 {{ info.ensembleMembers || '可用' }} 个成员场，
          统计降水达到指定阈值的概率分布、集合平均、离散度与 90 分位包络，
          用于表达预报不确定性并支撑概率化决策。
        </p>
      </div>
      <div class="ph-right">
        <span class="module-tag"><b>08</b> 增强功能</span>
        <span class="required-tag bonus">加分项</span>
      </div>
    </header>

    <div v-if="loading" class="panel" style="flex:1;justify-content:center">
      <div class="skeleton" style="height:200px"></div>
      <p style="text-align:center;font-size:11px;color:var(--text-faint);margin-top:10px">
        正在读取当前批次集合成员并统计概率场，请稍候…
      </p>
    </div>

    <div v-else-if="!data.available" class="empty-state">
      <AppIcon name="layers" :size="34" />
      <strong>集合预报产品不可用</strong>
      <span>{{ data.message || '未发现集合预报产品目录，请确认 ens 数据已同步。' }}</span>
    </div>

    <div v-else class="ens-layout">
      <!-- 控制条 -->
      <section class="panel control-panel">
        <div class="panel-body control-body">
          <div class="field" style="width:auto">
            <label>预报时效</label>
            <div class="seg">
              <button v-for="lv in leadPresets" :key="lv.value"
                      :class="{ active: leadHour === lv.value }"
                      @click="setLead(lv.value)">{{ lv.label }}</button>
            </div>
          </div>
          <div class="field" style="width:auto">
            <label>降水阈值</label>
            <div class="seg">
              <button v-for="t in thresholds" :key="t.value"
                      :class="{ active: threshold === t.value }"
                      @click="setThreshold(t.value)">{{ t.label }}</button>
            </div>
          </div>
          <div class="field" style="width:auto">
            <label>显示场</label>
            <div class="seg">
              <button v-for="f in fields" :key="f.key"
                      :class="{ active: activeField === f.key }"
                      @click="activeField = f.key">{{ f.label }}</button>
            </div>
          </div>
          <div class="ctrl-meta">
            <span>起报 <b>{{ data.cycle }}</b></span>
            <span>成员数 <b>{{ data.memberCount }}</b></span>
            <span>时效 <b>+{{ String(data.leadHour || 0).padStart(3, '0') }}h</b></span>
          </div>
        </div>
      </section>

      <!-- 地图区 -->
      <div class="ens-main">
        <div class="map-cell">
          <div class="map-cell-head">
            <span class="mc-dot" :style="{ background: fieldDef.color }"></span>
            <div>
              <strong>{{ fieldDef.label }}</strong>
              <em>{{ fieldDef.desc }}</em>
            </div>
            <span class="mc-badge">{{ fieldDef.unit }}</span>
          </div>
          <div ref="mapEl" class="map-canvas"></div>
          <div class="map-cell-foot">
            <span>最大 <b>{{ num(currentField?.statistics?.maximum) }}</b></span>
            <span>平均 <b>{{ num(currentField?.statistics?.average, 2) }}</b></span>
            <span>有效格点 <b>{{ currentField?.statistics?.gridCount ?? '--' }}</b></span>
          </div>
        </div>

        <aside class="ens-side">
          <!-- 概率分档 -->
          <section class="panel" style="flex:0 0 auto">
            <div class="panel-head">
              <div class="panel-title"><i class="bar"></i><h3>概率分档面积</h3></div>
              <span class="panel-sub">≥{{ threshold }} mm/6h</span>
            </div>
            <div class="panel-body">
              <div class="band-list">
                <div v-for="band in data.band || []" :key="band.label" class="band-row">
                  <span class="band-label">{{ band.label }}</span>
                  <div class="band-bar">
                    <i :style="{ width: `${Math.max(1.2, band.ratio * 100)}%`, background: band.color }"></i>
                  </div>
                  <span class="band-ratio">{{ (band.ratio * 100).toFixed(1) }}%</span>
                  <span class="band-count">{{ band.gridCount }}</span>
                </div>
              </div>
              <p class="band-note">
                以全国有效格点为分母，统计达到各概率档位的格点占比。<br />
                占比越高代表该档概率覆盖范围越广。
              </p>
            </div>
          </section>

          <!-- 概率分层图 -->
          <section class="panel" style="flex:1">
            <div class="panel-head">
              <div class="panel-title"><i class="bar"></i><h3>概率分布直方图</h3></div>
              <span class="panel-sub">Histogram</span>
            </div>
            <div class="panel-body">
              <div ref="histEl" class="hist-chart"></div>
            </div>
          </section>
        </aside>
      </div>

      <!-- 底部统计 -->
      <div class="bottom-row">
        <section class="panel">
          <div class="panel-head">
            <div class="panel-title"><i class="bar"></i><h3>集合统计场指标</h3></div>
            <span class="panel-sub">21 Members</span>
          </div>
          <div class="panel-body scroll-y">
            <table class="data-table">
              <thead>
                <tr><th>统计场</th><th>含义</th><th style="text-align:right">最大</th><th style="text-align:right">平均</th><th style="text-align:right">单位</th></tr>
              </thead>
              <tbody>
                <tr v-for="row in statRows" :key="row.key">
                  <td class="strong">{{ row.name }}</td>
                  <td>{{ row.desc }}</td>
                  <td class="num">{{ num(row.stats?.maximum) }}</td>
                  <td class="num">{{ num(row.stats?.average, 2) }}</td>
                  <td>{{ row.unit }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section class="panel">
          <div class="panel-head">
            <div class="panel-title"><i class="bar"></i><h3>集合方法说明</h3></div>
            <span class="panel-sub">Method</span>
          </div>
          <div class="panel-body">
            <div class="method-list">
              <div class="method-item">
                <span class="mi-idx">01</span>
                <div><strong>成员来源</strong><p>盘古轻量级集合 V2.0，共 21 个成员，含 1 个控制成员与 20 个扰动成员。</p></div>
              </div>
              <div class="method-item">
                <span class="mi-idx">02</span>
                <div><strong>概率定义</strong><p>Prob = 达到阈值的成员数 / 21，以百分比表示；阈值可在 3—25 mm/6h 间切换。</p></div>
              </div>
              <div class="method-item">
                <span class="mi-idx">03</span>
                <div><strong>离散度</strong><p>成员场标准差，反映模式对该时效预报的信心水平；离散度越大不确定性越高。</p></div>
              </div>
              <div class="method-item">
                <span class="mi-idx">04</span>
                <div><strong>90 分位包络</strong><p>成员场的 90 百分位，刻画较强降水可能达到的上界，适合风险上沿评估。</p></div>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  </main>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import AppIcon from './AppIcon.vue'
import api from '../api'
import {
  mountChart, disposeChart, geoOption, compareBarOption, num,
  rasterGridSeries, equalBreaks, gradeVisualMap, PRECIP_COLORS,
  CHINA_DOMAIN, CHINA_DOMAIN_CENTER,
} from '../chartKit'

const leadPresets = [
  { value: 24, label: '+24h' },
  { value: 72, label: '+72h' },
  { value: 168, label: '+168h' },
]
// 本产品为「6 小时累计降水」场，量级远小于日累计，
// 故阈值预设按 6h 口径设置；默认取 0.5mm 以兼顾覆盖率与信息量。
const thresholds = [
  { value: 0.1, label: '0.1 mm' },
  { value: 0.5, label: '0.5 mm' },
  { value: 1, label: '1 mm' },
  { value: 2, label: '2 mm' },
]
const fields = [
  { key: 'probability', label: '概率', color: '#5fd8ff', unit: '%', desc: '达到阈值的集合成员比例' },
  { key: 'mean', label: '集合平均', color: '#3fd8b0', unit: 'mm/6h', desc: '21 个成员的算术平均场' },
  { key: 'spread', label: '离散度', color: '#a78bfa', unit: 'mm/6h', desc: '成员场标准差，越大越不确定' },
  { key: 'p90', label: '90分位', color: '#ff9a4d', unit: 'mm/6h', desc: '成员场 90 百分位，风险上沿' },
  { key: 'pmax', label: '成员最大', color: '#ff5c6e', unit: 'mm/6h', desc: '成员中的极值，极端情形参考' },
]

/** 概率场专用色带（0% 近乎透明 → 100% 强警示红） */
const PROB_PALETTE = ['#33517f', '#3a72b0', '#3f9dd0', '#46c1b0', '#8fd35c', '#f2c14e', '#ef8a41', '#e04f5f']

const props = defineProps({ info: { type: Object, default: () => ({}) } })

const data = ref({ available: false })
const loading = ref(false)
const leadHour = ref(24)
const threshold = ref(0.5)
const activeField = ref('probability')

const mapEl = ref(null)
const histEl = ref(null)
let mapChart = null
let histChart = null

const fieldDef = computed(() => fields.find((f) => f.key === activeField.value) || fields[0])
const currentField = computed(() => data.value[activeField.value] || {})

const statRows = computed(() => [
  { key: 'probability', name: '概率场', desc: `达到 ≥${data.value.threshold} mm/6h 的成员比例`, stats: data.value.probability?.statistics, unit: '%' },
  { key: 'mean', name: '集合平均', desc: '所有成员的算术平均', stats: data.value.mean?.statistics, unit: 'mm/6h' },
  { key: 'spread', name: '离散度', desc: '成员场标准差', stats: data.value.spread?.statistics, unit: 'mm/6h' },
])

/* ------------------------------------------------------------ 渲染 */

function renderMap() {
  mapChart = mountChart(mapEl.value) || mapChart
  if (!mapChart) return
  const field = currentField.value
  if (!field?.points?.length) {
    mapChart.clear()
    return
  }
  const isProb = activeField.value === 'probability'
  const absMax = isProb ? 100 : Math.max(1, Math.min(80, field.statistics?.p99 || 40))
  // 按当前显示场选用色带：概率场用「低透明蓝 → 高亮红」的警示色带，
  // 雨量类场沿用气象降水色带，便于跨模块保持一致的读图习惯。
  const palette = isProb ? PROB_PALETTE
    : (Array.isArray(data.value.palette) && data.value.palette.length ? data.value.palette : PRECIP_COLORS)

  // 概率场固定 0–100% 分档；雨量类场按分位数上限等分；
  // 离散度（spread）等无合理 0 下界的场用其自身范围等分。
  const breaks = isProb
    ? equalBreaks(0, 100, palette.length)
    : equalBreaks(field.statistics?.minimum ?? 0, absMax, palette.length)

  mapChart.setOption(
    {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'item',
        confine: true,
        formatter: (p) => {
          const v = Number(p.value[2])
          const suffix = isProb ? '%' : ' mm/6h'
          return `经度 ${p.value[0]}°E<br/>纬度 ${p.value[1]}°N<br/>${fieldDef.value.label} <b>${v.toFixed(1)}</b>${suffix}`
        },
      },
      geo: geoOption({ zoom: 1.72, center: CHINA_DOMAIN_CENTER, roam: false }),
      visualMap: gradeVisualMap(breaks, palette, isProb ? '%' : 'mm/6h'),
      series: [rasterGridSeries(field.points, {
        id: 'ens-field', name: fieldDef.value.label, unit: isProb ? '%' : 'mm/6h',
        breaks, colors: palette, opacity: 0.9, z: 2,
      })],
    },
    true,
  )
}

function renderHist() {
  histChart = mountChart(histEl.value) || histChart
  if (!histChart) return
  const rows = data.value.band || []
  histChart.setOption(
    compareBarOption(
      rows.map((r) => r.label),
      [{
        name: '格点占比 (%)',
        color: '#5fd8ff',
        colorEnd: '#2f86c8',
        gradient: true,
        data: rows.map((r) => Number((r.ratio * 100).toFixed(2))),
      }],
      { yUnit: '%' },
    ),
    true,
  )
}

/* ------------------------------------------------------------ 加载 */

async function load() {
  loading.value = true
  try {
    data.value = await api.ensemble(leadHour.value, threshold.value, 2)
  } catch (error) {
    data.value = { available: false, message: error.message }
  } finally {
    loading.value = false
  }
  // 待 v-if 分支切换、图表容器挂载后再初始化 ECharts
  await nextTick()
  if (data.value.available) {
    renderMap()
    renderHist()
  }
}

function setLead(v) { leadHour.value = v; load() }
function setThreshold(v) { threshold.value = v; load() }

watch(activeField, () => nextTick(renderMap))

function onResize() {
  mapChart?.resize()
  histChart?.resize()
}

onMounted(() => {
  load()
  window.addEventListener('resize', onResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  disposeChart(mapEl.value)
  disposeChart(histEl.value)
})

defineExpose({ refresh: load })
</script>

<style scoped>
.ens-layout {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.control-panel { flex: 0 0 auto; }
.control-body { flex-direction: row; align-items: flex-end; gap: 16px; flex-wrap: wrap; }
.ctrl-meta { display: flex; align-items: center; gap: 14px; margin-left: auto; font-size: 10.5px; color: var(--text-faint); }
.ctrl-meta b { color: var(--cyan-soft); font-family: var(--font-mono); font-weight: 600; }

.ens-main {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(520px, 1fr) minmax(288px, 24%);
  gap: 12px;
}

.map-cell {
  position: relative;
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  overflow: hidden;
  background:
    radial-gradient(ellipse 62% 55% at 50% 48%, rgba(32, 92, 168, 0.2), transparent 72%),
    linear-gradient(165deg, rgba(10, 28, 58, 0.9), rgba(5, 14, 33, 0.95));
}
.map-cell-head {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 11px; border-bottom: 1px solid var(--line);
  background: rgba(6, 18, 40, 0.6); flex: 0 0 auto;
}
.map-cell-head > div { flex: 1; min-width: 0; }
.map-cell-head strong { display: block; font-size: 12px; }
.map-cell-head em { display: block; margin-top: 2px; font-size: 9.5px; font-style: normal; color: var(--text-faint); }
.mc-dot { width: 7px; height: 7px; border-radius: 50%; flex: 0 0 7px; }
.mc-badge {
  padding: 2px 7px; border-radius: 9px; border: 1px solid var(--line);
  background: rgba(74, 158, 255, 0.14); font-family: var(--font-mono); font-size: 9px; color: var(--cyan-soft);
}
.map-canvas { flex: 1; min-height: 210px; width: 100%; }
.map-cell-foot {
  display: flex; align-items: center; justify-content: space-between;
  padding: 7px 11px; border-top: 1px solid var(--line);
  background: rgba(6, 18, 40, 0.6); font-size: 9.5px; color: var(--text-faint); flex: 0 0 auto;
}
.map-cell-foot b { color: var(--cyan-soft); font-family: var(--font-mono); font-weight: 600; }

.ens-side { display: flex; flex-direction: column; gap: 12px; min-height: 0; }

.band-list { display: grid; gap: 6px; }
.band-row {
  display: grid;
  grid-template-columns: 52px 1fr 48px 52px;
  gap: 7px;
  align-items: center;
}
.band-label { font-size: 10.5px; color: var(--text-dim); font-family: var(--font-mono); }
.band-bar { height: 7px; border-radius: 4px; background: rgba(12, 34, 66, 0.9); overflow: hidden; }
.band-bar i { display: block; height: 100%; border-radius: 4px; box-shadow: 0 0 8px rgba(95, 216, 255, 0.25); }
.band-ratio { font-family: var(--font-mono); font-size: 10px; color: var(--cyan-soft); text-align: right; }
.band-count { font-family: var(--font-mono); font-size: 9.5px; color: var(--text-faint); text-align: right; }
.band-note { margin: 11px 0 0; font-size: 9.5px; line-height: 1.7; color: var(--text-faint); }

.hist-chart { flex: 1; min-height: 148px; width: 100%; }

.bottom-row {
  display: grid;
  grid-template-columns: 1.15fr 1fr;
  gap: 12px;
  min-height: 208px;
  flex: 0 0 auto;
}
.bottom-row .panel { min-height: 0; }

.method-list { display: grid; gap: 8px; }
.method-item { display: flex; gap: 9px; padding-bottom: 8px; border-bottom: 1px solid rgba(88, 148, 216, 0.1); }
.method-item:last-child { border-bottom: none; padding-bottom: 0; }
.mi-idx {
  flex: 0 0 20px;
  height: 20px;
  display: grid;
  place-items: center;
  border-radius: 5px;
  border: 1px solid rgba(95, 216, 255, 0.3);
  background: rgba(95, 216, 255, 0.1);
  font-family: var(--font-mono);
  font-size: 9px;
  color: var(--cyan-soft);
}
.method-item > div { min-width: 0; }
.method-item strong { display: block; font-size: 11.5px; color: var(--text); }
.method-item p { margin: 4px 0 0; font-size: 10px; line-height: 1.65; color: var(--text-dim); }
</style>
