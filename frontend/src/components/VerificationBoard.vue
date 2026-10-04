<template>
  <main class="page-surface">
    <header class="page-head rise-in">
      <div class="ph-left">
        <div class="ph-kicker"><i></i><span>Verification Board · Module 06</span></div>
        <h2>预报检验看板</h2>
        <p class="ph-desc">
          真实检验需接入与预报有效时间及累计时段匹配的降水实况，以 TS、POD、FAR、BIAS 分级评分与 MAE、RMSE、CORR 连续量指标评估
          0—15 天各时效的预报能力。支持全部时效与分时段（1—3 天 / 4—10 天 / 11—15 天）统计切换，
          并可追溯预测与参考场来源。
        </p>
      </div>
      <div class="ph-right">
        <span class="module-tag"><b>06</b> 必备功能</span>
        <span class="required-tag must">核心必备</span>
      </div>
    </header>

    <div v-if="loading" class="panel" style="flex:1;justify-content:center">
      <div class="skeleton" style="height:210px;width:100%"></div>
      <p style="text-align:center;font-size:11px;color:var(--text-faint);margin-top:12px">
        正在检查预报与实况的配对条件…
      </p>
    </div>

    <div v-else-if="!data.available" class="empty-state">
      <AppIcon name="chart" :size="34" />
      <strong>检验指标暂不可用</strong>
      <span>{{ data.message || '未发现有效时间与累计时段匹配的降水实况。' }}</span>
    </div>

    <div v-else class="verify-layout">
      <!-- 顶部总体指标 -->
      <section class="verify-top">
        <div class="vt-metrics">
          <div class="vt-card">
            <span>MAE 平均绝对误差</span>
            <strong>{{ num(data.overall?.mae, 3) }}</strong>
            <em>mm/6h · 越小越好</em>
          </div>
          <div class="vt-card">
            <span>RMSE 均方根误差</span>
            <strong>{{ num(data.overall?.rmse, 3) }}</strong>
            <em>mm/6h · 越小越好</em>
          </div>
          <div class="vt-card accent-teal">
            <span>CORR 相关系数</span>
            <strong>{{ num(data.overall?.corr, 3) }}</strong>
            <em>越大越好</em>
          </div>
          <div class="vt-card accent-amber">
            <span>BIAS 偏差</span>
            <strong>{{ num(data.overall?.bias, 3) }}</strong>
            <em>mm/6h · 接近 0 最优</em>
          </div>
          <div class="vt-card accent-violet">
            <span>参考场来源</span>
            <strong class="small">{{ data.referenceCycle || '--' }}</strong>
            <em>同分辨率预报场</em>
          </div>
        </div>

        <div class="vt-seg">
          <div class="seg">
            <button v-for="seg in segments" :key="seg.key"
                    :class="{ active: activeSegment === seg.key }"
                    @click="activeSegment = seg.key">{{ seg.label }}</button>
          </div>
          <div class="seg">
            <button v-for="m in metrics" :key="m.key"
                    :class="{ active: activeMetric === m.key }"
                    @click="activeMetric = m.key">{{ m.label }}</button>
          </div>
        </div>
      </section>

      <!-- 主曲线 -->
      <section class="panel verify-curve">
        <div class="panel-head">
          <div class="panel-title">
            <i class="bar"></i>
            <h3>{{ activeMetricDef.label }} 逐时效曲线</h3>
            <span class="panel-sub">{{ activeSegmentDef.label }}</span>
          </div>
          <div class="panel-extra">
            <span class="hint-chip">{{ activeMetricDef.hint }}</span>
          </div>
        </div>
        <div class="panel-body">
          <div ref="curveEl" class="verify-chart"></div>
        </div>
      </section>

      <div class="verify-bottom">
        <!-- 分级检验 -->
        <section class="panel">
          <div class="panel-head">
            <div class="panel-title"><i class="bar"></i><h3>分级降水检验</h3></div>
            <span class="panel-sub">Threshold Scores</span>
          </div>
          <div class="panel-body scroll-y">
            <table class="data-table">
              <thead>
                <tr>
                  <th>阈值</th>
                  <th style="text-align:right">TS</th>
                  <th style="text-align:right">POD</th>
                  <th style="text-align:right">FAR</th>
                  <th style="text-align:right">BIAS</th>
                  <th style="text-align:right">命中</th>
                  <th style="text-align:right">空报</th>
                  <th style="text-align:right">漏报</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in data.levels || []" :key="row.label">
                  <td class="strong">{{ row.label }}</td>
                  <td class="num">{{ num(row.ts, 3) }}</td>
                  <td class="num">{{ num(row.pod, 3) }}</td>
                  <td class="num">{{ num(row.far, 3) }}</td>
                  <td class="num">{{ num(row.bias, 2) }}</td>
                  <td class="num">{{ row.hits }}</td>
                  <td class="num">{{ row.falseAlarms }}</td>
                  <td class="num">{{ row.misses }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <!-- 分时段统计 -->
        <section class="panel">
          <div class="panel-head">
            <div class="panel-title"><i class="bar"></i><h3>分时段统计</h3></div>
            <span class="panel-sub">Segment Stats</span>
          </div>
          <div class="panel-body">
            <div ref="segEl" class="seg-chart"></div>
          </div>
        </section>
      </div>

      <!-- 追溯与说明 -->
      <section class="panel trace-panel">
        <div class="panel-head">
          <div class="panel-title"><i class="bar"></i><h3>数据追溯与口径说明</h3></div>
          <span class="panel-sub">Traceability</span>
        </div>
        <div class="panel-body trace-body">
          <div class="trace-grid">
            <div><span>检验起报时次</span><strong>{{ data.cycle }}</strong></div>
            <div><span>参考场时次</span><strong>{{ data.referenceCycle || '--' }}</strong></div>
            <div><span>检验样本组数</span><strong>{{ data.sampleGrids }} 组时效</strong></div>
            <div><span>检验网格分辨率</span><strong>{{ data.gridResolution }}</strong></div>
            <div><span>参与检验要素</span><strong>6小时累计降水 TP</strong></div>
            <div><span>单位口径</span><strong>mm/6h（competition）</strong></div>
          </div>
          <p class="trace-note">
            <AppIcon name="info" :size="12" />
            {{ data.referenceNote }} 当前页面展示的为「预报—参考场」配对的相对检验结果，
            用于演示完整的指标计算链路与产品化能力，不代表竞赛最终评分。
          </p>
        </div>
      </section>
    </div>
  </main>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import AppIcon from './AppIcon.vue'
import api from '../api'
import { mountChart, disposeChart, leadCurveOption, compareBarOption, num } from '../chartKit'

const metrics = [
  { key: 'mae', label: 'MAE', hint: '平均绝对误差，单位 mm/6h，越小越好' },
  { key: 'rmse', label: 'RMSE', hint: '均方根误差，对大误差更敏感，越小越好' },
  { key: 'corr', label: 'CORR', hint: '空间相关系数，越大越好' },
  { key: 'bias', label: 'BIAS', hint: '平均偏差，接近 0 表示无明显系统性偏差' },
]
const segments = [
  { key: 'all', label: '全部时效', low: 0, high: 999 },
  { key: 'd13', label: '1—3 天', low: 0, high: 72 },
  { key: 'd410', label: '4—10 天', low: 72, high: 240 },
  { key: 'd1115', label: '11—15 天', low: 240, high: 361 },
]

const data = ref({ available: false })
const loading = ref(false)
const activeMetric = ref('mae')
const activeSegment = ref('all')

const curveEl = ref(null)
const segEl = ref(null)
let curveChart = null
let segChart = null

const activeMetricDef = computed(() => metrics.find((m) => m.key === activeMetric.value) || metrics[0])
const activeSegmentDef = computed(() => segments.find((s) => s.key === activeSegment.value) || segments[0])

const segmentedRows = computed(() => {
  const rows = data.value.series || []
  const seg = activeSegmentDef.value
  return rows.filter((r) => r.leadHour > seg.low && r.leadHour <= seg.high)
})

/* ------------------------------------------------------------ 渲染 */

function renderCurve() {
  curveChart = mountChart(curveEl.value) || curveChart
  if (!curveChart) return
  const rows = segmentedRows.value
  if (!rows.length) {
    curveChart.clear()
    return
  }
  const metric = activeMetric.value
  const series = [{
    name: activeMetricDef.value.label,
    color: metric === 'bias' ? '#a78bfa' : '#5fd8ff',
    data: rows.map((r) => r[metric]),
  }]
  const markLine = metric === 'bias'
    ? { silent: true, symbol: 'none', lineStyle: { color: 'rgba(255,201,77,0.6)', type: 'dashed' }, data: [{ yAxis: 0, label: { formatter: '零偏差', color: '#ffc94d', fontSize: 9 } }] }
    : null
  curveChart.setOption(
    leadCurveOption(series, {
      xLabels: rows.map((r) => `D${r.day}`),
      yUnit: metric === 'corr' ? '' : 'mm/6h',
      yName: activeMetricDef.value.label,
      markLine,
    }),
    true,
  )
}

function renderSegments() {
  segChart = mountChart(segEl.value) || segChart
  if (!segChart) return
  const rows = data.value.segments || []
  segChart.setOption(
    compareBarOption(
      rows.map((r) => r.label),
      [
        { name: 'MAE', color: '#5fd8ff', colorEnd: '#2f86c8', gradient: true, data: rows.map((r) => r.mae), label: (p) => Number(p.value).toFixed(2) },
        { name: 'RMSE', color: '#ff9a4d', colorEnd: '#c96a2c', gradient: true, data: rows.map((r) => r.rmse), label: (p) => Number(p.value).toFixed(2) },
      ],
      { yUnit: 'mm/6h' },
    ),
    true,
  )
}

/* ------------------------------------------------------------ 加载 */

async function load() {
  loading.value = true
  try {
    data.value = await api.verification(24)
  } catch (error) {
    data.value = { available: false, message: error.message }
  } finally {
    loading.value = false
  }
  // 先让 v-if 分支切换、图表容器挂载到 DOM，再初始化 ECharts，
  // 否则容器尚不存在会导致图表静默不渲染。
  await nextTick()
  if (data.value.available) {
    renderCurve()
    renderSegments()
  }
}

watch([activeMetric, activeSegment], () => renderCurve())

function onResize() {
  curveChart?.resize()
  segChart?.resize()
}

onMounted(() => {
  load()
  window.addEventListener('resize', onResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  disposeChart(curveEl.value)
  disposeChart(segEl.value)
})

defineExpose({ refresh: load })
</script>

<style scoped>
.verify-layout {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow-y: auto;
  padding-right: 2px;
}

.verify-top { display: grid; gap: 10px; }
.vt-metrics {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 9px;
}
.vt-card {
  position: relative;
  padding: 11px 13px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: linear-gradient(150deg, rgba(16, 40, 76, 0.85), rgba(8, 22, 46, 0.9));
  overflow: hidden;
  transition: border-color 0.2s, transform 0.2s;
}
.vt-card::before {
  content: "";
  position: absolute;
  top: 0; left: 0;
  width: 2px; height: 100%;
  background: var(--accent, var(--cyan));
  box-shadow: 0 0 10px var(--accent, var(--cyan));
}
.vt-card:hover { border-color: var(--line-strong); transform: translateY(-1px); }
.vt-card.accent-teal { --accent: #3fd8b0; }
.vt-card.accent-amber { --accent: #ffc94d; }
.vt-card.accent-violet { --accent: #a78bfa; }
.vt-card > span { display: block; font-size: 9.5px; color: var(--text-faint); letter-spacing: 0.05em; }
.vt-card > strong {
  display: block;
  margin-top: 7px;
  font-family: var(--font-mono);
  font-size: 22px;
  font-weight: 600;
  color: var(--accent, var(--cyan));
  line-height: 1.1;
}
.vt-card > strong.small { font-size: 14px; }
.vt-card > em { display: block; margin-top: 5px; font-size: 9.5px; font-style: normal; color: var(--text-dim); }

.vt-seg { display: flex; align-items: center; justify-content: space-between; gap: 14px; flex-wrap: wrap; }

.verify-curve { flex: 0 0 auto; }
.verify-chart { height: 216px; width: 100%; }

.hint-chip {
  padding: 3px 9px;
  border-radius: 10px;
  border: 1px solid var(--line);
  background: rgba(6, 18, 40, 0.6);
  font-size: 9.5px;
  color: var(--text-faint);
}

.verify-bottom {
  display: grid;
  grid-template-columns: 1.35fr 1fr;
  gap: 12px;
  min-height: 260px;
}
.verify-bottom .panel { min-height: 0; }
.seg-chart { flex: 1; min-height: 190px; }

.trace-panel { flex: 0 0 auto; }
.trace-body { gap: 10px; }
.trace-grid {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 8px;
}
.trace-grid > div {
  padding: 8px 10px;
  border: 1px solid var(--line);
  border-left: 2px solid var(--blue);
  border-radius: var(--radius-s);
  background: rgba(6, 18, 40, 0.5);
}
.trace-grid span { display: block; font-size: 9px; color: var(--text-faint); }
.trace-grid strong { display: block; margin-top: 5px; font-size: 11px; color: var(--text); font-weight: 500; font-family: var(--font-mono); }

.trace-note {
  display: flex;
  align-items: flex-start;
  gap: 7px;
  margin: 0;
  padding: 9px 11px;
  border-radius: var(--radius-s);
  border: 1px solid rgba(255, 201, 77, 0.24);
  border-left: 3px solid var(--amber);
  background: rgba(60, 45, 10, 0.3);
  font-size: 10.5px;
  line-height: 1.7;
  color: #ffe2a3;
}
</style>
