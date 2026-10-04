<template>
  <main class="page-surface">
    <header class="page-head rise-in">
      <div class="ph-left">
        <div class="ph-kicker"><i></i><span>Multi-Model Comparison · Module 07</span></div>
        <h2>多模式对比分析</h2>
        <p class="ph-desc">
          将穹宇融合预报与对照模式（IFS 单链基线 / 前一日同起报时效）在同一时效、同一网格下逐格点比对，
          输出差值场与定量差异指标（MAE、RMSE、相关系数、强弱偏差格点数），
          用于刻画融合方案的改进幅度与预报日际连续性。
        </p>
      </div>
      <div class="ph-right">
        <span class="module-tag"><b>07</b> 增强功能</span>
        <span class="required-tag secondary">次要功能</span>
      </div>
    </header>

    <div v-if="loading" class="panel" style="flex:1;justify-content:center">
      <div class="skeleton" style="height:200px"></div>
      <p style="text-align:center;font-size:11px;color:var(--text-faint);margin-top:10px">
        正在读取多模式降水场并计算差值场…
      </p>
    </div>

    <div v-else-if="!data.available" class="empty-state">
      <AppIcon name="compare" :size="34" />
      <strong>暂无可对比的模式</strong>
      <span>{{ data.message || '未发现同日可用的对照产品目录。' }}</span>
    </div>

    <div v-else class="comp-layout">
      <!-- 控制条 -->
      <section class="panel control-panel">
        <div class="panel-body control-body">
          <div class="field" style="width:auto">
            <label>对比时效</label>
            <div class="seg">
              <button v-for="lv in leadPresets" :key="lv.value"
                      :class="{ active: leadHour === lv.value }"
                      @click="setLead(lv.value)">{{ lv.label }}</button>
            </div>
          </div>
          <div class="field" style="width:auto">
            <label>视图</label>
            <div class="seg">
              <button v-for="v in views" :key="v.key"
                      :class="{ active: view === v.key }"
                      @click="setView(v.key)">{{ v.label }}</button>
            </div>
          </div>
          <div v-if="diffs.length" class="field" style="width:auto">
            <label>差值对</label>
            <div class="seg">
              <button v-for="(d, i) in diffs" :key="i"
                      :class="{ active: activeDiff === i }"
                      @click="setDiff(i)">{{ d.leftLabel }} − {{ d.rightLabel }}</button>
            </div>
          </div>
          <div class="ctrl-meta">
            <span>起报 <b>{{ data.cycle }}</b></span>
            <span>时效 <b>+{{ String(data.leadHour || 0).padStart(3, '0') }}h</b></span>
            <span>模式数 <b>{{ data.modes?.length || 0 }}</b></span>
          </div>
        </div>
      </section>

      <!-- 地图区 -->
      <div class="map-row" :class="{ 'split-2': data.modes?.length > 1 && view !== 'diff' }">
        <div v-for="mode in visibleModes" :key="mode.key" class="map-cell">
          <div class="map-cell-head">
            <span class="mc-dot" :style="{ background: mode.color }"></span>
            <div>
              <strong>{{ mode.label }}</strong>
              <em>{{ mode.source }}</em>
            </div>
            <span class="mc-badge">{{ mode.product }}</span>
          </div>
          <div :ref="(el) => setModeEl(mode.key, el)" class="map-canvas"></div>
          <div class="map-cell-foot">
            <span>最大 <b>{{ num(mode.statistics?.maximum) }}</b></span>
            <span>平均 <b>{{ num(mode.statistics?.average, 2) }}</b></span>
            <span>强降水格点 <b>{{ mode.statistics?.heavyGridCount ?? '--' }}</b></span>
          </div>
        </div>

        <div v-if="view === 'diff' && activeDiffData" class="map-cell">
          <div class="map-cell-head">
            <span class="mc-dot" style="background:#ffc94d"></span>
            <div>
              <strong>差值场</strong>
              <em>{{ activeDiffData.leftLabel }} − {{ activeDiffData.rightLabel }}</em>
            </div>
            <span class="mc-badge">DIFF</span>
          </div>
          <div ref="diffMapEl" class="map-canvas"></div>
          <div class="map-cell-foot">
            <span>平均差 <b>{{ num(activeDiffData.meanDelta, 3) }}</b></span>
            <span>MAE <b>{{ num(activeDiffData.mae, 3) }}</b></span>
            <span>相关系数 <b>{{ num(activeDiffData.corr, 4) }}</b></span>
          </div>
        </div>
      </div>

      <!-- 指标与统计 -->
      <div class="bottom-row">
        <section class="panel">
          <div class="panel-head">
            <div class="panel-title"><i class="bar"></i><h3>模式指标对比</h3></div>
            <span class="panel-sub">Statistics</span>
          </div>
          <div class="panel-body scroll-y">
            <table class="data-table">
              <thead>
                <tr>
                  <th>模式</th>
                  <th>产品</th>
                  <th style="text-align:right">最大</th>
                  <th style="text-align:right">平均</th>
                  <th style="text-align:right">有雨格点</th>
                  <th style="text-align:right">强降水格点</th>
                  <th style="text-align:right">P95</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="m in data.modes || []" :key="m.key">
                  <td>
                    <span class="mc-dot inline" :style="{ background: m.color }"></span>
                    <span class="strong">{{ m.label }}</span>
                  </td>
                  <td>{{ m.source }}</td>
                  <td class="num">{{ num(m.statistics?.maximum) }}</td>
                  <td class="num">{{ num(m.statistics?.average, 2) }}</td>
                  <td class="num">{{ m.statistics?.wetGridCount ?? '--' }}</td>
                  <td class="num">{{ m.statistics?.heavyGridCount ?? '--' }}</td>
                  <td class="num">{{ num(m.statistics?.p95) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section class="panel">
          <div class="panel-head">
            <div class="panel-title"><i class="bar"></i><h3>差值定量指标</h3></div>
            <span class="panel-sub">{{ activeDiffData ? `${activeDiffData.leftLabel} − ${activeDiffData.rightLabel}` : '未选择' }}</span>
          </div>
          <div class="panel-body">
            <div v-if="activeDiffData" class="diff-metrics">
              <div class="dm-item"><span>平均差 (Mean Δ)</span><strong>{{ num(activeDiffData.meanDelta, 3) }}</strong><em>mm/6h 正为融合偏强</em></div>
              <div class="dm-item"><span>平均绝对差 (MAE)</span><strong>{{ num(activeDiffData.mae, 3) }}</strong><em>mm/6h</em></div>
              <div class="dm-item"><span>均方根差 (RMSE)</span><strong>{{ num(activeDiffData.rmse, 3) }}</strong><em>mm/6h</em></div>
              <div class="dm-item"><span>空间相关系数</span><strong>{{ num(activeDiffData.corr, 4) }}</strong><em>越接近 1 越一致</em></div>
              <div class="dm-item"><span>最大正差</span><strong>{{ num(activeDiffData.maxDelta, 2) }}</strong><em>mm/6h</em></div>
              <div class="dm-item"><span>融合偏强格点</span><strong>{{ activeDiffData.strongCount }}</strong><em>差值 ≥ 10 mm/6h</em></div>
              <div class="dm-item"><span>融合偏弱格点</span><strong>{{ activeDiffData.weakCount }}</strong><em>差值 ≤ −10 mm/6h</em></div>
              <div class="dm-item"><span>99 分位绝对差</span><strong>{{ num(activeDiffData.range, 2) }}</strong><em>mm/6h</em></div>
            </div>
            <div v-else class="empty-inline">请选择一组差值对以查看指标。</div>
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
  mountChart, disposeChart, rasterGridSeries, geoOption, num,
  PRECIP_BREAKS, PRECIP_COLORS, CHINA_DOMAIN, CHINA_DOMAIN_CENTER,
} from '../chartKit'

const leadPresets = [
  { value: 6, label: '+06h' },
  { value: 24, label: '+24h' },
  { value: 72, label: '+72h' },
  { value: 168, label: '+168h' },
  { value: 360, label: '+360h' },
]
const views = [
  { key: 'diff', label: '并排 + 差值' },
  { key: 'single', label: '单模式' },
]

const data = ref({ available: false, modes: [], diffs: [] })
const loading = ref(false)
const leadHour = ref(24)
const view = ref('diff')
const activeDiff = ref(0)

const modeEls = ref({})
const diffMapEl = ref(null)
const charts = {}

const diffs = computed(() => data.value.diffs || [])
const activeDiffData = computed(() => diffs.value[activeDiff.value] || null)
const visibleModes = computed(() => {
  if (view.value === 'single') return (data.value.modes || []).slice(0, 1)
  return data.value.modes || []
})

/* ------------------------------------------------------------ 渲染 */

function setModeEl(key, el) {
  if (el) modeEls.value[key] = el
}

function renderMaps() {
  ;(data.value.modes || []).forEach((mode) => {
    const el = modeEls.value[mode.key]
    if (!el) return
    const chart = mountChart(el)
    if (!chart) return
    charts[mode.key] = chart
    chart.setOption(
      {
        backgroundColor: 'transparent',
        tooltip: { trigger: 'item', confine: true },
        geo: geoOption({ zoom: 1.72, center: CHINA_DOMAIN_CENTER, roam: false }),
        series: [rasterGridSeries(mode.points, {
          id: `m-${mode.key}`, name: mode.label, unit: 'mm/6h',
          breaks: PRECIP_BREAKS, colors: PRECIP_COLORS, opacity: 0.88, z: 2,
        })],
      },
      true,
    )
  })

  if (view.value === 'diff' && activeDiffData.value && diffMapEl.value) {
    const chart = mountChart(diffMapEl.value)
    if (chart) {
      charts.diff = chart
      const d = activeDiffData.value
      const absMax = Math.max(1, Math.min(60, d.range || 10))
      // 差值场用「双向等距色阶」：以 0 为界，负值冷色 / 正值暖色，
      // 便于直观看出融合产品相对基准模式偏强或偏弱的区域。
      const half = 8
      const step = absMax / half
      const negColors = ['#4fb0e0', '#2b86c8', '#1f5fa8', '#164a86', '#0f3a6c', '#0b2f58', '#082647', '#061e39']
      const posColors = ['#a8623d', '#c9803f', '#e29a3c', '#f0ac35', '#f5b93a', '#f8c24a', '#f0873c', '#d63f52']
      const breaks = []
      for (let i = 0; i < half; i += 1) breaks.push(-absMax + step * i)
      const colors = [...negColors.slice(0, half), ...posColors.slice(0, half)]
      const diffCells = (d.points || []).map((p) => ({ value: p }))
      chart.setOption(
        {
          backgroundColor: 'transparent',
          tooltip: {
            trigger: 'item',
            confine: true,
            formatter: (p) => {
              const v = Number(p.value[2])
              const judge = v > 0 ? '融合偏强' : v < 0 ? '融合偏弱' : '一致'
              return `经度 ${p.value[0]}°E<br/>纬度 ${p.value[1]}°N<br/>差值 <b>${v.toFixed(2)}</b> mm/6h<br/>${judge}`
            },
          },
          geo: geoOption({ zoom: 1.72, center: CHINA_DOMAIN_CENTER, roam: false }),
          visualMap: { show: false, seriesIndex: 0, type: 'piecewise', pieces: [] },
          series: [
            {
              id: 'diff-field',
              name: '差值场',
              type: 'custom',
              coordinateSystem: 'geo',
              z: 2,
              data: diffCells,
              renderItem(params, apiObj) {
                const lon = apiObj.value(0)
                const lat = apiObj.value(1)
                const val = apiObj.value(2)
                const p0 = apiObj.coord([lon - 0.128, lat - 0.128])
                const p1 = apiObj.coord([lon + 0.128, lat + 0.128])
                if (!p0 || !p1) return null
                const x = Math.min(p0[0], p1[0])
                const y = Math.min(p0[1], p1[1])
                const w = Math.abs(p1[0] - p0[0])
                const h = Math.abs(p1[1] - p0[1])
                const idx = Math.max(0, Math.min(colors.length - 1, Math.round((val + absMax) / step) - 1))
                return {
                  type: 'rect',
                  shape: { x, y, width: Math.max(w, 0.5), height: Math.max(h, 0.5) },
                  style: { fill: colors[idx], opacity: 0.9 },
                }
              },
            },
          ],
        },
        true,
      )
      // breaks 仅用于图例对照（保持与上面渲染一致的分档）
      void breaks
    }
  }
}

/* ------------------------------------------------------------ 加载 */

async function load() {
  loading.value = true
  try {
    // 模式场用 2 抽稀降低载荷，差值场随之计算
    data.value = await api.comparison(leadHour.value, 2)
    activeDiff.value = 0
  } catch (error) {
    data.value = { available: false, message: error.message, modes: [], diffs: [] }
  } finally {
    loading.value = false
  }
  // 待 v-if 分支切换、图表容器挂载后再初始化 ECharts
  await nextTick()
  if (data.value.available) renderMaps()
}

function setLead(v) { leadHour.value = v; load() }
function setView(v) { view.value = v; nextTick(renderMaps) }
function setDiff(i) { activeDiff.value = i; nextTick(renderMaps) }

watch(view, () => nextTick(renderMaps))
watch(activeDiff, () => nextTick(renderMaps))

function onResize() {
  Object.values(charts).forEach((c) => c?.resize())
}

onMounted(() => {
  load()
  window.addEventListener('resize', onResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  Object.keys(charts).forEach((k) => {
    const el = k === 'diff' ? diffMapEl.value : modeEls.value[k]
    disposeChart(el)
  })
})

defineExpose({ refresh: load })
</script>

<style scoped>
.comp-layout {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.control-panel { flex: 0 0 auto; }
.control-body {
  flex-direction: row;
  align-items: flex-end;
  gap: 16px;
  flex-wrap: wrap;
}
.ctrl-meta { display: flex; align-items: center; gap: 14px; margin-left: auto; font-size: 10.5px; color: var(--text-faint); }
.ctrl-meta b { color: var(--cyan-soft); font-family: var(--font-mono); font-weight: 600; }

.map-row {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 12px;
}
.map-row.split-2 { grid-template-columns: 1fr 1fr; }

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
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 11px;
  border-bottom: 1px solid var(--line);
  background: rgba(6, 18, 40, 0.6);
  flex: 0 0 auto;
}
.map-cell-head > div { flex: 1; min-width: 0; }
.map-cell-head strong { display: block; font-size: 12px; color: var(--text); }
.map-cell-head em { display: block; margin-top: 2px; font-size: 9.5px; font-style: normal; color: var(--text-faint); }
.mc-dot { width: 7px; height: 7px; border-radius: 50%; flex: 0 0 7px; box-shadow: 0 0 8px currentColor; }
.mc-dot.inline { display: inline-block; margin-right: 6px; vertical-align: middle; }
.mc-badge {
  padding: 2px 7px;
  border-radius: 9px;
  border: 1px solid var(--line);
  background: rgba(74, 158, 255, 0.14);
  font-family: var(--font-mono);
  font-size: 9px;
  color: var(--cyan-soft);
}
.map-canvas { flex: 1; min-height: 200px; width: 100%; }
.map-cell-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 7px 11px;
  border-top: 1px solid var(--line);
  background: rgba(6, 18, 40, 0.6);
  font-size: 9.5px;
  color: var(--text-faint);
  flex: 0 0 auto;
}
.map-cell-foot b { color: var(--cyan-soft); font-family: var(--font-mono); font-weight: 600; }

.bottom-row {
  display: grid;
  grid-template-columns: 1.25fr 1fr;
  gap: 12px;
  min-height: 216px;
  flex: 0 0 auto;
}
.bottom-row .panel { min-height: 0; }

.diff-metrics {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 7px;
}
.dm-item {
  padding: 8px 10px;
  border: 1px solid var(--line);
  border-left: 2px solid var(--amber);
  border-radius: var(--radius-s);
  background: rgba(6, 18, 40, 0.5);
}
.dm-item span { display: block; font-size: 9px; color: var(--text-faint); }
.dm-item strong { display: block; margin-top: 4px; font-family: var(--font-mono); font-size: 14px; color: var(--amber); font-weight: 600; }
.dm-item em { display: block; margin-top: 3px; font-size: 9px; font-style: normal; color: var(--text-dim); }

.empty-inline { padding: 22px; text-align: center; font-size: 11px; color: var(--text-faint); }
</style>
