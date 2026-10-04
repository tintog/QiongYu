<template>
  <div class="module-page risk-page">
    <header class="module-head">
      <div class="mh-left">
        <h2><AppIcon name="alert" /> 模块 9 · 预警与风险提示中心</h2>
        <p class="ph-desc">
          基于穹宇AI降水预报产品，按 24 小时累计降水量阈值自动判定降水强度等级，
          每6小时更新过去24小时的滑动累计，输出风险等级、峰值落区、达到大雨阈值的省级中心邻域排行与关注建议。
        </p>
      </div>
      <div class="mh-right">
        <span class="mh-chip">起报时次 {{ cycleLabel }}</span>
        <button class="btn btn-ghost" :disabled="loading" @click="load">
          <AppIcon name="refresh" /> {{ loading ? '加载中' : '刷新预警' }}
        </button>
      </div>
    </header>

    <div v-if="error" class="notice-banner notice-error"><AppIcon name="alert" /> {{ error }}</div>

    <section class="risk-metrics">
      <article class="metric">
        <span class="m-label">预警时效数</span>
        <strong class="m-value">{{ data.alarmCount ?? 0 }}</strong>
        <span class="m-sub">共 {{ data.alarms?.length || 0 }} 个预报时效发布</span>
      </article>
      <article class="metric">
        <span class="m-label">最高等级</span>
        <strong class="m-value" :class="levelClass(peakLevel)">{{ peakLevel }}</strong>
        <span class="m-sub">出现在 +{{ data.peak?.leadHour ?? '--' }}h（第{{ data.peak?.day ?? '--' }}天）</span>
      </article>
      <article class="metric">
        <span class="m-label">峰值雨量</span>
        <strong class="m-value">{{ fmt(data.peak?.maximum) }}<i>mm/24h</i></strong>
        <span class="m-sub">落区 {{ data.peak?.hotspot?.nearestRegion || '--' }}附近</span>
      </article>
      <article class="metric">
        <span class="m-label">影响省份</span>
        <strong class="m-value">{{ (data.peak?.ranking || []).length }}<i>个</i></strong>
        <span class="m-sub">峰值时效内达预警阈值的省份</span>
      </article>
    </section>

    <section class="risk-grid">
      <!-- 左：等级判定规则 -->
      <article class="panel">
        <header class="panel-head">
          <h3><AppIcon name="shield" /> 降水强度判定规则</h3>
          <span class="ph-hint">24h 累计</span>
        </header>
        <div class="rule-list">
          <div v-for="r in data.rules || []" :key="r.key" class="rule-item" :class="levelClass(r.level)">
            <span class="rule-badge">{{ r.level }}</span>
            <div class="rule-body">
              <div class="rule-threshold">≥ {{ fmt(r.threshold) }} mm / 24h</div>
              <p class="rule-advice">{{ r.advice }}</p>
            </div>
          </div>
        </div>
      </article>

      <!-- 中：风险分布 -->
      <article class="panel">
        <header class="panel-head">
          <h3><AppIcon name="chart" /> 各等级时效数分布</h3>
          <span class="ph-hint">按 24h 累计判定</span>
        </header>
        <div ref="barEl" class="risk-bar"></div>
        <div class="level-count">
          <div v-for="(n, lv) in levelCount" :key="lv" class="lc-item" :class="levelClass(lv)">
            <span class="lc-dot"></span>
            <span class="lc-name">{{ lv }}</span>
            <strong class="lc-num">{{ n }}</strong>
          </div>
        </div>
      </article>

      <!-- 右：峰值时刻画像 -->
      <article class="panel">
        <header class="panel-head">
          <h3><AppIcon name="target" /> 峰值时效画像</h3>
          <span class="ph-hint">最强预报时刻</span>
        </header>
        <div v-if="data.peak" class="peak-card">
          <div class="peak-head">
            <span class="risk-badge" :class="levelClass(data.peak.level)">{{ data.peak.level }} · {{ data.peak.levelName }}</span>
            <span class="peak-time">+{{ data.peak.leadHour }}h</span>
          </div>
          <div class="peak-time-full">{{ fmtTime(data.peak.validTime) }}（第 {{ data.peak.day }} 天）</div>
          <div class="peak-body">
            <div class="peak-kpi"><span>峰值雨量</span><strong>{{ fmt(data.peak.maximum) }} mm</strong></div>
            <div class="peak-kpi"><span>落区格点</span><strong>{{ data.peak.hotspot?.lon }}°E, {{ data.peak.hotspot?.lat }}°N</strong></div>
            <div class="peak-kpi"><span>最近省份</span><strong>{{ data.peak.hotspot?.nearestRegion || '--' }}</strong></div>
          </div>
          <p class="peak-advice">{{ data.peak.advice }}</p>
        </div>
        <div v-else class="empty-state">暂无峰值记录</div>
      </article>
    </section>

    <section class="risk-bottom">
      <!-- 左：预警清单 -->
      <article class="panel panel-grow">
        <header class="panel-head">
          <h3><AppIcon name="bell" /> 逐时效预警清单</h3>
          <div class="panel-tools">
            <div class="seg">
              <button v-for="f in filters" :key="f.key" :class="{ active: activeFilter === f.key }" @click="setFilter(f.key)">{{ f.label }}</button>
            </div>
          </div>
        </header>
        <div class="table-scroll">
          <table class="data-table">
            <thead>
              <tr>
                <th>时效</th><th>有效时间</th><th>等级</th><th>类型</th>
                <th class="num">峰值(mm)</th><th>落区</th><th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="a in filteredAlarms" :key="a.leadHour">
                <td><strong>+{{ a.leadHour }}h</strong><br><span class="dim">第{{ a.day }}天</span></td>
                <td>{{ fmtTime(a.validTime) }}</td>
                <td><span class="risk-badge" :class="levelClass(a.level)">{{ a.level }}</span></td>
                <td>{{ a.levelName }}</td>
                <td class="num">{{ fmt(a.maximum) }}</td>
                <td>{{ a.hotspot?.nearestRegion || '--' }}</td>
                <td>
                  <button class="btn btn-xs" @click="$emit('navigate', { view: 'field', lead: a.leadHour })">查看场</button>
                </td>
              </tr>
              <tr v-if="!filteredAlarms.length"><td colspan="7" class="empty-cell">当前筛选条件无预警记录</td></tr>
            </tbody>
          </table>
        </div>
      </article>

      <!-- 右：影响省份排行 -->
      <article class="panel risk-rank-panel">
        <header class="panel-head">
          <h3><AppIcon name="compare" /> 峰值时效影响省份</h3>
          <span class="ph-hint">Top {{ (data.peak?.ranking || []).length }}</span>
        </header>
        <div class="rank-list">
          <div v-for="(r, i) in data.peak?.ranking || []" :key="r.name" class="rank-row">
            <span class="rank-no" :class="{ top3: i < 3 }">{{ i + 1 }}</span>
            <div class="rank-main">
              <div class="rank-name">{{ r.name }} <em>{{ r.region }}</em></div>
              <div class="rank-bar"><i :style="{ width: pct(r.value) + '%' }"></i></div>
            </div>
            <span class="rank-val">{{ fmt(r.value) }}<i>mm</i></span>
          </div>
          <div v-if="!(data.peak?.ranking || []).length" class="empty-state">暂无省份记录</div>
        </div>
      </article>
    </section>

    <footer class="disclaimer-bar">
      <AppIcon name="info" /> {{ data.disclaimer || '阈值与等级为演示口径，不作为正式气象预警发布依据。' }}
    </footer>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import AppIcon from './AppIcon.vue'
import { api } from '../api.js'
import { mountChart, disposeChart, formatShort, formatFull } from '../chartKit.js'

const props = defineProps({ info: { type: Object, default: () => ({}) } })
defineEmits(['navigate'])

const data = ref({})
const loading = ref(false)
const error = ref('')
const barEl = ref(null)
const activeFilter = ref('all')

const filters = [
  { key: 'all', label: '全部' },
  { key: 'high', label: '红/橙' },
  { key: 'mid', label: '黄' },
  { key: 'low', label: '蓝' },
]

const cycleLabel = computed(() => {
  const c = data.value.cycle
  if (!c || c.length < 10) return '--'
  return `${c.slice(0, 4)}-${c.slice(4, 6)}-${c.slice(6, 8)} ${c.slice(8, 10)}时`
})

const peakLevel = computed(() => data.value.peak?.level || '--')
const levelCount = computed(() => data.value.levelCount || {})

const filteredAlarms = computed(() => {
  const list = data.value.alarms || []
  if (activeFilter.value === 'all') return list
  const map = { high: ['红色', '橙色'], mid: ['黄色'], low: ['蓝色'] }
  const allow = map[activeFilter.value] || []
  return list.filter((a) => allow.includes(a.level))
})

function setFilter(k) { activeFilter.value = k }

function levelClass(lv) {
  return { 'lv-red': lv === '红色', 'lv-orange': lv === '橙色', 'lv-yellow': lv === '黄色', 'lv-blue': lv === '蓝色', 'lv-green': lv === '绿色' }
}
function fmt(v) { return v === undefined || v === null ? '--' : Number(v).toFixed(1) }
function fmtTime(v) { return formatFull(v) || '--' }
function pct(v) {
  const max = Math.max(...(data.value.peak?.ranking || []).map((r) => r.value || 0), 1)
  return Math.max(4, ((v || 0) / max) * 100)
}

async function load() {
  loading.value = true; error.value = ''
  try {
    data.value = await api.risk()
  } catch (e) {
    error.value = e.message || '预警数据加载失败'
  } finally {
    loading.value = false
  }
  // 数据就绪且 DOM 更新后再初始化图表
  await nextTick()
  renderBar()
}

function renderBar() {
  if (!barEl.value) return
  const order = ['红色', '橙色', '黄色', '蓝色']
  const colors = { 红色: '#ff4d5e', 橙色: '#ff9d3d', 黄色: '#ffd93d', 蓝色: '#3fa9ff' }
  const counts = order.map((lv) => levelCount.value[lv] || 0)
  const chart = mountChart(barEl.value)
  if (!chart) return
  chart.setOption({
    backgroundColor: 'transparent',
    grid: { left: 52, right: 24, top: 30, bottom: 34 },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (ps) => `${ps[0].axisValue}预警<br/>共 <b>${ps[0].value}</b> 个预报时效`,
    },
    xAxis: {
      type: 'category', data: order,
      axisLine: { lineStyle: { color: 'rgba(88,148,216,.4)' } },
      axisTick: { show: false },
      axisLabel: { color: '#93b3d8', fontSize: 11 },
    },
    yAxis: {
      type: 'value', name: '时效数',
      nameTextStyle: { color: '#61809f', fontSize: 10 },
      axisLabel: { color: '#93b3d8', fontSize: 10 },
      splitLine: { lineStyle: { color: 'rgba(88,148,216,.12)' } },
    },
    series: [{
      type: 'bar', data: counts, barWidth: '46%',
      itemStyle: {
        borderRadius: [4, 4, 0, 0],
        color: (p) => colors[order[p.dataIndex]],
        shadowBlur: 12, shadowColor: 'rgba(0,0,0,.35)',
      },
      label: { show: true, position: 'top', color: '#e8f2ff', fontSize: 12, fontWeight: 600 },
    }],
  }, true)
}

onMounted(load)
onBeforeUnmount(() => disposeChart(barEl.value))
watch(() => props.info?.revision, () => { load() })

defineExpose({ refresh: load })
</script>

<style scoped>
.risk-metrics { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; }
.risk-grid { display: grid; grid-template-columns: 1.05fr 1fr 1.1fr; gap: 14px; }
.risk-bottom { display: grid; grid-template-columns: 1.75fr 1fr; gap: 14px; }

.rule-list { display: flex; flex-direction: column; gap: 10px; }
.rule-item { display: flex; gap: 12px; padding: 10px 12px; border-radius: 8px; background: rgba(12,32,50,.55); border-left: 3px solid currentColor; }
.rule-item.lv-red { color: #ff4d5e; }
.rule-item.lv-orange { color: #ff9d3d; }
.rule-item.lv-yellow { color: #ffd93d; }
.rule-item.lv-blue { color: #3fa9ff; }
.rule-badge { align-self: flex-start; padding: 3px 10px; border-radius: 999px; font-size: 12px; font-weight: 700; color: #06131f; background: currentColor; white-space: nowrap; }
.rule-body { flex: 1; min-width: 0; }
.rule-threshold { font-size: 12.5px; font-weight: 700; color: currentColor; margin-bottom: 3px; }
.rule-advice { margin: 0; font-size: 12.5px; line-height: 1.6; color: var(--text-dim); }

.risk-bar { height: 190px; }
.level-count { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-top: 8px; }
.lc-item { display: flex; align-items: center; gap: 6px; padding: 7px 9px; border-radius: 7px; background: rgba(12,32,50,.55); font-size: 12.5px; }
.lc-dot { width: 8px; height: 8px; border-radius: 50%; background: currentColor; }
.lc-item.lv-red { color: #ff4d5e; } .lc-item.lv-orange { color: #ff9d3d; }
.lc-item.lv-yellow { color: #ffd93d; } .lc-item.lv-blue { color: #3fa9ff; }
.lc-name { color: var(--text-dim); }
.lc-num { margin-left: auto; font-size: 15px; color: var(--text-main); }

.peak-card { display: flex; flex-direction: column; gap: 10px; }
.peak-head { display: flex; align-items: center; justify-content: space-between; }
.peak-time { font-size: 13px; font-weight: 700; color: var(--cyan); }
.peak-time-full { font-size: 12.5px; color: var(--text-dim); }
.peak-body { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.peak-kpi { display: flex; flex-direction: column; gap: 3px; padding: 8px 10px; border-radius: 7px; background: rgba(12,32,50,.55); }
.peak-kpi span { font-size: 11.5px; color: var(--text-dim); }
.peak-kpi strong { font-size: 13px; color: var(--text-main); }
.peak-advice { margin: 0; font-size: 12.5px; line-height: 1.65; color: var(--text-soft); padding: 9px 11px; border-radius: 7px; background: rgba(255,157,61,.08); border: 1px solid rgba(255,157,61,.22); }

.risk-badge { font-size: 11.5px; color: #06131f; }
.rank-list { display: flex; flex-direction: column; gap: 7px; max-height: 420px; overflow-y: auto; padding-right: 4px; }
.rank-row { display: flex; align-items: center; gap: 9px; }
.rank-no { width: 20px; height: 20px; flex: none; display: grid; place-items: center; font-size: 11px; font-weight: 700; border-radius: 5px; background: rgba(44,74,99,.7); color: #9fc4dc; }
.rank-no.top3 { background: linear-gradient(135deg, #2fe6d6, #1a8fa8); color: #041722; }
.rank-main { flex: 1; min-width: 0; }
.rank-name { font-size: 12.5px; color: var(--text-main); }
.rank-name em { font-style: normal; font-size: 11px; color: var(--text-dim); margin-left: 4px; }
.rank-bar { height: 4px; margin-top: 4px; border-radius: 2px; background: rgba(44,74,99,.6); overflow: hidden; }
.rank-bar i { display: block; height: 100%; border-radius: 2px; background: linear-gradient(90deg, #2fe6d6, #3fa9ff); }
.rank-val { font-size: 12.5px; color: var(--cyan); font-weight: 600; }
.rank-val i { font-style: normal; font-size: 10.5px; color: var(--text-dim); margin-left: 1px; }

.risk-rank-panel { display: flex; flex-direction: column; }
.table-scroll { flex: 1; overflow: auto; max-height: 460px; }
.empty-cell { text-align: center; color: var(--text-dim); padding: 22px 0; }
.dim { color: var(--text-dim); font-size: 11.5px; }
.disclaimer-bar { display: flex; align-items: center; gap: 8px; padding: 10px 14px; border-radius: 8px; font-size: 12.5px; color: #ffd08a; background: rgba(255,157,61,.08); border: 1px solid rgba(255,157,61,.2); }

@media (max-width: 1600px) {
  .risk-metrics { grid-template-columns: repeat(2, 1fr); }
  .risk-grid { grid-template-columns: 1fr 1fr; }
  .risk-bottom { grid-template-columns: 1fr; }
}
</style>
