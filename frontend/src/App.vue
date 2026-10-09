<template>
  <div v-if="checkingSession" class="session-loading">正在验证登录状态…</div>
  <LoginPanel v-else-if="!account" @login="startSession" />
  <div v-else ref="shellRef" class="app-shell" :class="{ 'independent-screen': view === 'screen3d' }">
    <header v-if="view === 'screen3d'" class="independent-header">
      <div class="screen-header-left"><button @click="view='overview'">‹ 返回工作台</button><div class="screen-header-clock"><b>{{ clock.time }}</b><small>{{ clock.date }}</small></div></div>
      <h1>穹宇气象 · 三维预报大屏</h1>
      <div class="screen-header-actions"><label><span>预报批次</span><select aria-label="大屏预报批次" :value="info.activeBatchId || ''" :disabled="!isAdmin || switching || refreshing" @change="switchBatch($event.target.value)"><option value="" disabled>加载中</option><option v-for="b in forecastBatches" :key="b.id" :value="b.id">{{ fmtCycle(b.cycle) }} UTC</option></select></label><span class="screen-header-account">{{ account.username }}</span><button @click="toggleScreenFullscreen">{{ screenFull ? '退出全屏' : '全屏' }}</button><button @click="logout">退出</button></div>
    </header>
    <!-- 顶栏 -->
    <header v-if="view !== 'screen3d'" class="topbar">
      <div class="brand">
        <div class="brand-mark">穹</div>
        <div class="brand-text">
          <h1>穹宇气象大模型演示系统</h1>
        </div>
      </div>

      <nav class="main-nav">
        <button
          v-for="m in visibleModules"
          :key="m.key"
          :class="{ active: view === m.key }"
          :title="m.desc"
          :aria-label="m.label"
          @click="view = m.key"
        >
          <AppIcon :name="m.icon" :size="15" />
          <span>{{ m.label }}</span>
        </button>
      </nav>

      <div class="topbar-right header-actions">
        <div class="live-pill" :class="{ on: live.on }">
          <span class="dot"></span>
          <span class="lp-text">{{ live.on ? '实时数据' : '连接中断' }}</span>
          <span class="lp-rev">rev {{ realtime.revision ?? '--' }}</span>
        </div>
        <div class="clock">
          <span class="ck-time">{{ clock.time }}</span>
          <span class="ck-date">{{ clock.date }}</span>
        </div>
        <button class="icon-btn" title="立即刷新全部模块" :disabled="refreshing" @click="refreshAll">
          <AppIcon name="refresh" :size="16" />
        </button>
      </div>
    </header>

    <section v-if="view !== 'screen3d'" class="global-data-bar">
      <label>全局预报批次／起报时间（UTC）
        <select :value="info.activeBatchId || ''" :disabled="!isAdmin || switching || refreshing" @change="switchBatch($event.target.value)">
          <option value="" disabled>请选择已导入预报</option>
          <option v-for="b in forecastBatches" :key="b.id" :value="b.id">{{ fmtCycle(b.cycle) }} · {{ b.name }}</option>
        </select>
      </label>
      <span>{{ switching ? '正在切换，重新加载各模块…' : '起报时间＋预报时效＝有效时间；各预报页面统一联动' }}</span>
      <span>集合：{{ info.ensembleProduct || '该起报时间暂无集合数据' }}</span>
      <span v-if="batchError" class="batch-error">{{ batchError }}</span>
      <div class="account-actions">
        <span class="account-label" :title="account.username">{{ account.username }} · {{ isAdmin ? '管理员' : '用户' }}</span>
        <button class="logout-btn" @click="logout">退出</button>
      </div>
    </section>
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
          v-if="!switching"
          :key="view + ':' + dataEpoch"
          ref="pageRef"
          :info="pageInfo"
          :is-admin="isAdmin"
          :fullscreen-active="screenFull"
          @toggle-fullscreen="toggleScreenFullscreen"
          :selected-point="pendingPoint"
          @navigate="onNavigate"
          @point-selected="onPointSelected"
          @batch-activated="onBatchActivated"
        />
      </transition>
      <div v-if="switching && view === 'screen3d'" class="screen-switching">正在切换预报批次…</div>
    </main>

    <!-- 页脚：产品与数据链路信息 -->
    <footer v-if="view !== 'screen3d'" class="footer-bar">
      <div class="fb-group">
        <span class="fb-item"><AppIcon name="database" :size="13" /> 数据源：{{ info.dataSource || 'AIM-FDP 竞赛产品流水线' }}</span>
        <span class="fb-item"><AppIcon name="server" :size="13" /> 算力：{{ info.computePlatform || '青龙超算' }}</span>
        <span class="fb-item"><AppIcon name="shield" :size="13" /> 产品：{{ info.modelProduct || '暂无数据' }} · 集合 {{ info.ensembleProduct || '暂无同起报数据' }}</span>
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
import { ref, shallowRef, computed, onMounted, onBeforeUnmount, watch, defineAsyncComponent } from 'vue'
import LoginPanel from './components/LoginPanel.vue'
import AccountManagement from './components/AccountManagement.vue'
import { account } from './auth'
import AppIcon from './components/AppIcon.vue'
import OutlookDashboard from './components/OutlookDashboard.vue'
import VariableFieldPanel from './components/VariableFieldPanel.vue'
import PointForecastPanel from './components/PointForecastPanel.vue'
import VerificationBoard from './components/VerificationBoard.vue'
import EnsemblePanel from './components/EnsemblePanel.vue'
import RiskCenter from './components/RiskCenter.vue'
import SystemPanel from './components/SystemPanel.vue'
import DataManagementPanel from './components/DataManagementPanel.vue'
import { api } from './api.js'
import { formatFull } from './chartKit.js'

/* ---------------- 当前演示模块 ---------------- */
const modules = [
  { key: 'screen3d', label: '3D大屏', icon: 'globe', desc: '三维气象场、时效播放、区域与单点联动', comp: defineAsyncComponent(() => import('./components/WeatherScreen.vue')) },
  { key: 'overview', label: '态势总览', icon: 'globe', desc: '模块1 全国态势总览 + 模块2 多级下钻 + 模块3 时间轴播放', comp: OutlookDashboard },
  { key: 'field', label: '多要素场', icon: 'layers', desc: '模块4 多要素切换：降水/气温/风场/高空要素逐时效场', comp: VariableFieldPanel },
  { key: 'point', label: '单点预报', icon: 'locate', desc: '模块5 单点预报详情：任意经纬度逐6小时/逐日序列', comp: PointForecastPanel },
  { key: 'ensemble', label: '集合概率', icon: 'target', desc: '模块8 集合与概率预报：21 成员概率/离散度/分位数', comp: EnsemblePanel },
  { key: 'risk', label: '风险预警', icon: 'bell', desc: '模块9 预警与风险提示：降水强度分级与影响省份排行', comp: RiskCenter },
  { key: 'verification', label: '检验看板', icon: 'gauge', desc: '模块6 预报检验看板：TS/POD/FAR/BIAS/MAE/RMSE/CORR', comp: VerificationBoard },
  { key: 'system', label: '系统管理', icon: 'server', desc: '模块10 系统与任务管理：产品档案/数据血缘/质检/实时监控', comp: SystemPanel },
  { key: 'data', label: '数据管理', icon: 'database', desc: '统一上传、校验、批次登记与启用', comp: DataManagementPanel },
  { key:'accounts',label:'用户管理',icon:'shield',desc:'账户角色与操作日志',comp:AccountManagement },
]

const shellRef=ref(null),screenFull=ref(false)
async function toggleScreenFullscreen(){try{if(document.fullscreenElement)await document.exitFullscreen();else await shellRef.value.requestFullscreen()}catch(e){notice.value='全屏失败：'+e.message}}
function syncScreenFullscreen(){screenFull.value=document.fullscreenElement===shellRef.value}
const checkingSession=ref(true)
const isAdmin=computed(()=>account.value?.role==='admin')
const visibleModules=computed(()=>modules.filter(m=>isAdmin.value || !['system','accounts'].includes(m.key)).map(m=>m.key==='data'&&!isAdmin.value?{...m,label:'我的数据'}:m))
const view = ref('overview')
const pageRef = ref(null)
const info = ref({})
const realtime = ref({})
const notice = ref('')
const refreshing = ref(false)
const pendingRevision = ref(null)
const clock = ref({ time: '--:--:--', date: '' })
const live = ref({ on: false })
const forecastBatches=ref([]),switching=ref(false),batchError=ref(''),dataEpoch=ref(0)
async function loadBatches(){
  const result=await api.dataBatches()
  forecastBatches.value=result.batches.filter(b=>b.product==='DF' && b.canActivate).sort((a,b)=>b.cycle.localeCompare(a.cycle))
}
async function switchBatch(id){
  if(!isAdmin.value || !id || switching.value)return
  switching.value=true;batchError.value=''
  try{
    await api.activateBatch(id)
    info.value=await api.systemInfo()
    await loadBatches()
    dataEpoch.value++;pendingPoint.value=null;notice.value='';pendingRevision.value=null
    await poll()
  }catch(e){batchError.value=e.message;info.value={};dataEpoch.value++;await refreshAll()}
  finally{switching.value=false}
}

const pageInfo = computed(() => ({ ...info.value, revision: realtime.value.revision }))
const currentComponent = computed(() => visibleModules.value.find((m) => m.key === view.value)?.comp || OutlookDashboard)

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
  refreshAll()
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
    await loadBatches()
    await poll()
    dataEpoch.value++
  } catch (e) {
    notice.value = e.message || '刷新失败'
  } finally {
    refreshing.value = false
  }
}

/* ---------------- 模块间联动 ---------------- */
function onNavigate(payload) {
  const { view: target, ...rest } = typeof payload === 'string' ? { view: payload } : payload || {}
  if (visibleModules.value.some(m => m.key === target)) view.value = target
  if (rest.lead && pageRef.value && pageRef.value.applyLead) pageRef.value.applyLead(rest.lead)
}

function onPointSelected(payload) {
  if (payload && payload.lon != null && payload.lat != null) {
    pendingPoint.value = payload
    view.value = 'point'
  }
}

const pendingPoint = ref(null)
async function onBatchActivated() {
  await refreshAll()
  notice.value = ''
  pendingRevision.value = null
}

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

async function startSession(){
  clearInterval(pollTimer)
  view.value='overview';info.value={};notice.value='';pendingPoint.value=null;dataEpoch.value++
  await refreshAll()
  if(account.value)pollTimer=setInterval(poll,POLL_MS)
}
function stopSession(){clearInterval(pollTimer);info.value={};forecastBatches.value=[];realtime.value={};live.value.on=false;notice.value=''}
async function logout(){try{await api.logout()}finally{account.value=null;stopSession()}}
onMounted(async()=>{
  tickClock();clockTimer=setInterval(tickClock,1000)
  document.addEventListener('fullscreenchange',syncScreenFullscreen)
  window.addEventListener('qiongyu-session-expired',stopSession)
  try{account.value=await api.me()}catch{account.value=null}
  checkingSession.value=false
  if(account.value)await startSession()
})

onBeforeUnmount(() => {
  document.removeEventListener('fullscreenchange',syncScreenFullscreen)
  window.removeEventListener('qiongyu-session-expired',stopSession)
  clearInterval(pollTimer)
  clearInterval(clockTimer)
})
</script>

<style scoped>
.independent-screen{height:100dvh;min-height:0;overflow:hidden;background:#071725;display:flex;flex-direction:column}
.independent-screen .app-main{padding:0;overflow:hidden;position:relative;display:flex;flex:1;min-height:0}
.independent-header{height:56px;min-height:56px;display:grid;grid-template-columns:1fr auto 1fr;gap:20px;align-items:center;padding:0 18px;border-bottom:1px solid #29455e;background:#091b2d;color:#dceaf4;z-index:20}
.independent-header h1{margin:0;font-size:19px;letter-spacing:2px;font-weight:600;white-space:nowrap}
.screen-header-left,.screen-header-actions{display:flex;align-items:center;gap:12px;min-width:0}.screen-header-actions{justify-content:flex-end}
.independent-header button{padding:7px 10px;border:1px solid #345169;border-radius:5px;background:#102b40;color:#d1e5f1;font-size:12px;white-space:nowrap;cursor:pointer}.independent-header button:hover{border-color:#66bfd7;background:#1b3e56}
.screen-header-clock{display:flex;flex-direction:column;gap:2px;white-space:nowrap;font-variant-numeric:tabular-nums}.screen-header-clock b{font-size:15px;color:#8ed8e9}.screen-header-clock small{font-size:10px;color:#91adc2}
.screen-header-actions label{display:flex;align-items:center;gap:8px;font-size:11px;color:#a6bed1}.screen-header-actions select{max-width:220px;min-width:0;padding:7px;background:#102b40;border:1px solid #345169;border-radius:5px;color:#d1e5f1;font-size:11px}.screen-header-account{font-size:12px;color:#a6bed1;max-width:90px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.screen-switching{position:absolute;inset:0;display:grid;place-items:center;color:#b5d9eb}
.independent-screen .notice-info{position:absolute;top:62px;left:50%;transform:translateX(-50%);z-index:25;background:#12304a;max-width:80%;margin:0;padding:10px 14px;border-radius:6px}
@media(max-width:1450px){.independent-header{gap:12px;padding:0 12px}.independent-header h1{font-size:17px;letter-spacing:1px}.screen-header-actions{gap:7px}.screen-header-actions label>span{display:none}.screen-header-actions select{max-width:170px}.screen-header-left{gap:10px}}
@media(max-width:1050px){.screen-header-clock{display:none}.independent-header h1{font-size:15px}.screen-header-account{display:none}.screen-header-actions select{max-width:145px}.independent-header{gap:6px}.independent-header button{padding:7px;font-size:11px}}

.topbar{flex-shrink:0;grid-template-columns:minmax(240px,auto) minmax(0,1fr) auto;gap:14px}
.topbar-right{display:flex;align-items:center;justify-content:flex-end;gap:10px;white-space:nowrap}
.topbar-right .live-pill,.topbar-right .clock,.topbar-right .icon-btn{flex-shrink:0}
.topbar-right .dot{width:6px;height:6px;border-radius:50%;background:currentColor}
.main-nav{max-width:100%;min-width:0;box-sizing:border-box}
.main-nav button{padding:8px 10px;flex-shrink:0}
.global-data-bar{flex-shrink:0;position:relative;z-index:10}
.account-actions{margin-left:auto;display:flex;align-items:center;gap:10px;white-space:nowrap}
.account-label{max-width:140px;overflow:hidden;text-overflow:ellipsis;color:var(--text-dim)}
.logout-btn{padding:4px 10px;border:1px solid var(--line);border-radius:5px;background:transparent;color:var(--text-dim);white-space:nowrap;font-size:11px;cursor:pointer}
.logout-btn:hover{color:var(--cyan);border-color:var(--line-strong)}
@media(max-width:1100px){.topbar{grid-template-columns:auto minmax(0,1fr) auto;padding:0 12px;gap:10px}.brand-text h1{font-size:14px}.main-nav button{padding:8px}.topbar-right .lp-rev{display:none}.topbar-right{gap:8px}}
@media(max-width:780px){.topbar{height:auto;min-height:var(--header-h);grid-template-columns:1fr auto;padding:10px 12px;row-gap:10px}.main-nav{grid-row:2;grid-column:1/-1;width:100%;justify-content:flex-start;overflow-x:auto}.topbar-right{grid-row:1;grid-column:2}.topbar-right .live-pill{display:none}.global-data-bar label{flex-wrap:wrap}.account-actions{margin-left:auto}}
.session-loading{min-height:100vh;display:grid;place-items:center;background:#08182c;color:#a7d7e9}
.global-data-bar{display:flex;align-items:center;flex-wrap:wrap;gap:12px;padding:10px 18px;border-bottom:1px solid var(--line);background:#0b203b;color:var(--text-dim);font-size:11px}.global-data-bar label{display:flex;align-items:center;gap:8px}.global-data-bar select{max-width:480px;padding:7px;background:#102846;color:var(--text);border:1px solid var(--line);border-radius:5px}.batch-error{color:#ff9a9a}
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
