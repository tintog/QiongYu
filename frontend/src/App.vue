<template>
  <div class="app-shell">
    <!-- 顶栏 -->
    <header class="topbar">
      <div class="brand">
        <div class="brand-mark">穹</div>
        <div class="brand-text">
          <h1>穹宇气象大模型演示系统</h1>
          <p>0—15天逐6小时降水预报 · {{ info.modelProduct || 'AIMB V3.3' }} 双链融合产品</p>
        </div>
      </div>

      <nav class="main-nav">
        <button
          v-for="m in modules"
          :key="m.key"
          :class="{ active: view === m.key }"
          :title="m.desc"
          @click="view = m.key"
        >
          <AppIcon :name="m.icon" :size="15" />
          <span>{{ m.label }}</span>
        </button>
      </nav>

      <div class="topbar-right">
        <div class="live-pill" :class="{ on: live.on }">
          <span class="dot"></span>
          <span class="lp-text">{{ live.on ? '实时数据' : '连接中断' }}</span>
          <span class="lp-rev">rev {{ realtime.revision ?? '--' }}</span>
        </div>
        <div class="clock">
          <AppIcon name="clock" :size="14" />
          <span class="ck-time">{{ clock.time }}</span>
          <span class="ck-date">{{ clock.date }}</span>
        </div>
        <button class="icon-btn" title="立即刷新全部模块" :disabled="refreshing" @click="refreshAll">
          <AppIcon name="refresh" :size="16" />
        </button>
      </div>
    </header>

    <!-- 数据变更提示 -->
    <transition name="notice">
      <div v-if="notice" class="notice-banner notice-info" @click="applyPending">
        <AppIcon name="info" /> {{ notice }}
        <button class="notice-act" @click.stop="applyPending">立即刷新</button>
        <button class="notice-x" @click.stop="notice = ''"><AppIcon name="close" :size="13" /></button>
      </div>
    </transition>

    <!-- 主体：按模块切换 -->
    <main class="app-main">
      <transition name="fade" mode="out-in">
        <component
          :is="currentComponent"
          :key="view"
          ref="pageRef"
          :info="pageInfo"
          :selected-point="pendingPoint"
          @navigate="onNavigate"
          @point-selected="onPointSelected"
        />
      </transition>
    </main>

    <!-- 页脚：产品与数据链路信息 -->
    <footer class="footer-bar">
      <div class="fb-group">
        <span class="fb-item"><AppIcon name="database" :size="13" /> 数据源：{{ info.dataSource || 'AIM-FDP 竞赛产品流水线' }}</span>
        <span class="fb-item"><AppIcon name="server" :size="13" /> 算力：{{ info.computePlatform || '青龙超算' }}</span>
        <span class="fb-item"><AppIcon name="shield" :size="13" /> 产品：{{ info.modelProduct || 'AIMB V3.3' }} · 集合 {{ info.ensembleProduct || 'AIMB V2.0' }}</span>
      </div>
      <div class="fb-group">
        <span class="fb-item">起报 {{ fmtCycle(info.initCycle) }}</span>
        <span class="fb-item">更新 {{ fmtFull(info.updatedAt) }}</span>
        <span class="fb-item"><AppIcon name="clock" :size="13" /> 下次扫描 {{ realtime.secondsToNextScan != null ? realtime.secondsToNextScan + 's' : '--' }}</span>
        <span class="fb-item fb-note">预报数据仅供演示与技术验证，不作为正式气象发布依据</span>
      </div>
    </footer>
  </div>
</template>

<script setup>
import { ref, shallowRef, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import AppIcon from './components/AppIcon.vue'
import OutlookDashboard from './components/OutlookDashboard.vue'
import VariableFieldPanel from './components/VariableFieldPanel.vue'
import PointForecastPanel from './components/PointForecastPanel.vue'
import VerificationBoard from './components/VerificationBoard.vue'
import ModelComparison from './components/ModelComparison.vue'
import EnsemblePanel from './components/EnsemblePanel.vue'
import RiskCenter from './components/RiskCenter.vue'
import SystemPanel from './components/SystemPanel.vue'
import { api } from './api.js'
import { formatFull } from './chartKit.js'

/* ---------------- 模块定义：严格对齐需求文档 10 大功能模块 ---------------- */
const modules = [
  { key: 'overview', label: '态势总览', icon: 'globe', desc: '模块1 全国态势总览 + 模块2 多级下钻 + 模块3 时间轴播放', comp: OutlookDashboard },
  { key: 'field', label: '多要素场', icon: 'layers', desc: '模块4 多要素切换：降水/气温/风场/高空要素逐时效场', comp: VariableFieldPanel },
  { key: 'point', label: '单点预报', icon: 'locate', desc: '模块5 单点预报详情：任意经纬度逐6小时/逐日序列', comp: PointForecastPanel },
  { key: 'verification', label: '检验看板', icon: 'gauge', desc: '模块6 预报检验看板：TS/POD/FAR/BIAS/MAE/RMSE/CORR', comp: VerificationBoard },
  { key: 'comparison', label: '模式对比', icon: 'compare', desc: '模块7 多模式对比：确定性子预报/融合/上一时次差值场', comp: ModelComparison },
  { key: 'ensemble', label: '集合概率', icon: 'target', desc: '模块8 集合与概率预报：21 成员概率/离散度/分位数', comp: EnsemblePanel },
  { key: 'risk', label: '风险预警', icon: 'bell', desc: '模块9 预警与风险提示：降水强度分级与影响省份排行', comp: RiskCenter },
  { key: 'system', label: '系统管理', icon: 'server', desc: '模块10 系统与任务管理：产品档案/数据血缘/质检/实时监控', comp: SystemPanel },
]

const view = ref('overview')
const pageRef = ref(null)
const info = ref({})
const realtime = ref({})
const notice = ref('')
const refreshing = ref(false)
const pendingRevision = ref(null)
const clock = ref({ time: '--:--:--', date: '' })
const live = ref({ on: false })

const pageInfo = computed(() => ({ ...info.value, revision: realtime.value.revision }))
const currentComponent = computed(() => modules.find((m) => m.key === view.value)?.comp || OutlookDashboard)

/* ---------------- 实时轮询：比对 revision，数据变化时提示/刷新 ---------------- */
const POLL_MS = 20000
let pollTimer = null
let clockTimer = null

async function poll() {
  try {
    const rt = await api.realtimeStatus()
    const prev = realtime.value.revision
    realtime.value = rt
    live.value.on = rt.running === true
    if (prev != null && rt.revision !== prev) {
      pendingRevision.value = rt.revision
      notice.value = `检测到数据更新（版本 ${prev} → ${rt.revision}），点击立即刷新当前模块`
    }
  } catch {
    live.value.on = false
  }
}

function applyPending() {
  notice.value = ''
  pendingRevision.value = null
  refreshCurrent()
}

function refreshCurrent() {
  const inst = pageRef.value
  if (inst && typeof inst.refresh === 'function') inst.refresh()
  else if (inst && typeof inst.loadOverview === 'function') inst.loadOverview()
}

async function refreshAll() {
  refreshing.value = true
  try {
    info.value = await api.systemInfo()
    await poll()
    refreshCurrent()
  } catch (e) {
    notice.value = e.message || '刷新失败'
  } finally {
    refreshing.value = false
  }
}

/* ---------------- 模块间联动 ---------------- */
function onNavigate(payload) {
  const { view: target, ...rest } = typeof payload === 'string' ? { view: payload } : payload || {}
  if (target === 'field') view.value = 'field'
  else if (target === 'point') view.value = 'point'
  else if (target === 'risk') view.value = 'risk'
  if (rest.lead && pageRef.value && pageRef.value.applyLead) pageRef.value.applyLead(rest.lead)
}

function onPointSelected(payload) {
  if (payload && payload.lon != null && payload.lat != null) {
    pendingPoint.value = payload
    view.value = 'point'
  }
}

const pendingPoint = ref(null)

/* ---------------- 工具 ---------------- */
function fmtCycle(c) {
  if (!c || c.length < 10) return c || '--'
  return `${c.slice(0, 4)}-${c.slice(4, 6)}-${c.slice(6, 8)} ${c.slice(8, 10)}时`
}
function fmtFull(v) { return formatFull(v) || '--' }

function tickClock() {
  const d = new Date()
  const p = (n) => String(n).padStart(2, '0')
  clock.value = {
    time: `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`,
    date: `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${['日', '一', '二', '三', '四', '五', '六'][d.getDay()]}`,
  }
}

onMounted(async () => {
  tickClock()
  clockTimer = setInterval(tickClock, 1000)
  try { info.value = await api.systemInfo() } catch { /* 保持空态 */ }
  await poll()
  pollTimer = setInterval(poll, POLL_MS)
})

onBeforeUnmount(() => {
  clearInterval(pollTimer)
  clearInterval(clockTimer)
})
</script>

<style scoped>
.app-main { flex: 1; min-height: 0; padding: 14px 18px; overflow: auto; }
.notice-act { margin-left: auto; padding: 3px 12px; border-radius: 6px; border: 1px solid currentColor; background: transparent; color: inherit; font-size: 12px; cursor: pointer; }
.notice-x { display: grid; place-items: center; width: 20px; height: 20px; border: none; border-radius: 5px; background: transparent; color: inherit; cursor: pointer; }
.notice-info { display: flex; align-items: center; gap: 9px; margin: 10px 18px 0; cursor: pointer; }

.notice-enter-active, .notice-leave-active { transition: opacity .25s, transform .25s; }
.notice-enter-from, .notice-leave-to { opacity: 0; transform: translateY(-8px); }
.fade-enter-active, .fade-leave-active { transition: opacity .2s ease, transform .2s ease; }
.fade-enter-from { opacity: 0; transform: translateY(6px); }
.fade-leave-to { opacity: 0; }

@media (max-width: 1400px) {
  .main-nav button span { display: none; }
}
</style>
