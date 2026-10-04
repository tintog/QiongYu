<template>
  <div class="module-page system-page">
    <header class="module-head">
      <div class="mh-left">
        <h2><AppIcon name="server" /> 模块 10 · 系统与任务管理</h2>
        <p class="ph-desc">
          集中展示穹宇AI降水预报模型的产品档案、数据血缘（从双源下载到质检发布的全流程）、
          时效完整性质检报告与实时任务监控状态，支撑运维值守与数据可追溯性核查。
        </p>
      </div>
      <div class="mh-right">
        <span class="mh-chip" :class="{ live: monitorRunning }">
          <span class="dot"></span> 实时监控{{ monitorRunning ? '运行中' : '已停止' }}
        </span>
        <button class="btn btn-ghost" :disabled="loading" @click="load">
          <AppIcon name="refresh" /> {{ loading ? '加载中' : '刷新状态' }}
        </button>
      </div>
    </header>

    <div v-if="error" class="notice-banner notice-error"><AppIcon name="alert" /> {{ error }}</div>

    <!-- 模型与产品档案 -->
    <section class="sys-hero">
      <article class="hero-card">
        <div class="hero-brand">
          <div class="hero-mark">穹</div>
          <div>
            <h3>{{ sys.modelName }}</h3>
            <p>{{ sys.subtitle }}</p>
          </div>
        </div>
        <div class="hero-grid">
          <div class="hg-item"><span>确定性子预报产品</span><strong>{{ sys.modelProduct }}</strong></div>
          <div class="hg-item"><span>集合预报产品</span><strong>{{ sys.ensembleProduct }}</strong></div>
          <div class="hg-item"><span>集合成员数</span><strong>{{ sys.ensembleMembers ?? '--' }} 个</strong></div>
          <div class="hg-item"><span>预报时效</span><strong>{{ sys.forecastRange }} / {{ sys.forecastHours }}h</strong></div>
          <div class="hg-item"><span>时间分辨率</span><strong>{{ sys.timeResolution }}</strong></div>
          <div class="hg-item"><span>空间分辨率</span><strong>{{ sys.spatialResolution }}</strong></div>
          <div class="hg-item"><span>数据来源</span><strong>{{ sys.dataSource }}</strong></div>
          <div class="hg-item"><span>算力平台</span><strong>{{ sys.computePlatform }}</strong></div>
        </div>
        <div class="hero-foot">
          <span class="hf-tag" :class="sys.isRealData ? 'ok' : 'warn'">
            <AppIcon :name="sys.isRealData ? 'check' : 'alert'" /> {{ sys.isRealData ? '真实产品数据' : '演示数据' }}
          </span>
          <span class="hf-path"><AppIcon name="database" /> {{ sys.dataRoot }}</span>
          <span class="hf-time"><AppIcon name="clock" /> 更新于 {{ fmtTime(sys.updatedAt) }}</span>
        </div>
      </article>

      <article class="panel monitors">
        <header class="panel-head"><h3><AppIcon name="activity" /> 实时任务监控</h3><span class="ph-hint">每 {{ rt.scanIntervalSeconds || 60 }}s 增量扫描</span></header>
        <div class="mon-grid">
          <div class="mon-item"><span>版本号 revision</span><strong>{{ rt.revision ?? '--' }}</strong></div>
          <div class="mon-item"><span>已扫描次数</span><strong>{{ rt.scanCount ?? '--' }}</strong></div>
          <div class="mon-item"><span>最近扫描</span><strong>{{ fmtTime(rt.lastScanAt) }}</strong></div>
          <div class="mon-item"><span>下次扫描</span><strong>{{ rt.secondsToNextScan != null ? rt.secondsToNextScan + 's 后' : '--' }}</strong></div>
        </div>
        <div class="prod-status">
          <div v-for="(p, key) in rt.products || {}" :key="key" class="ps-row">
            <span class="ps-name">{{ key === 'DF' ? '确定性子预报 DF' : '集合预报 ENS' }}</span>
            <span class="ps-meta">{{ p.version }} · 时次 {{ fmtCycle(p.cycle) }}</span>
            <span class="ps-meta">{{ p.files }} 文件 / {{ p.leads }} 时效</span>
            <span class="ps-tag ok">就绪</span>
          </div>
          <div v-if="!Object.keys(rt.products || {}).length" class="empty-state">暂无产品</div>
        </div>
      </article>
    </section>

    <!-- 数据血缘 -->
    <section class="panel">
      <header class="panel-head">
        <h3><AppIcon name="branch" /> 数据血缘链路</h3>
        <span class="ph-hint">起报时次 {{ fmtCycle(lineage.cycle) }} · {{ fmtTime(lineage.cycleTime) }}</span>
      </header>
      <div class="lineage-flow">
        <template v-for="(s, i) in lineage.stages || []" :key="s.key">
          <div class="ln-node" :class="s.status">
            <div class="ln-idx">{{ i + 1 }}</div>
            <div class="ln-body">
              <div class="ln-name">{{ s.name }}</div>
              <div class="ln-detail">{{ s.detail }}</div>
              <div class="ln-meta">
                <span v-if="s.count != null" class="ln-count">{{ s.count >= 1000 ? (s.count / 1000).toFixed(2) + 'k' : s.count }} 条</span>
                <span v-if="s.duration" class="ln-dur">{{ s.duration }}</span>
                <span class="ln-status" :class="s.status">{{ s.status === 'completed' ? '已完成' : s.status }}</span>
              </div>
            </div>
          </div>
          <div v-if="i < (lineage.stages || []).length - 1" class="ln-arrow"><AppIcon name="route" /></div>
        </template>
      </div>
      <div class="lineage-products">
        <div v-for="p in lineage.products || []" :key="p.name" class="lp-card">
          <div class="lp-head"><AppIcon name="grid" /> {{ p.name }}</div>
          <div class="lp-kv"><span>文件数</span><strong>{{ p.files }}</strong></div>
          <div class="lp-kv"><span>时效数</span><strong>{{ p.leads }}</strong></div>
          <div class="lp-kv"><span>要素类</span><strong>{{ (p.kinds || []).join(' + ') }}</strong></div>
          <div class="lp-src">{{ p.source }}</div>
        </div>
      </div>
    </section>

    <!-- 质检报告 -->
    <section class="sys-bottom">
      <article class="panel panel-grow">
        <header class="panel-head"><h3><AppIcon name="check" /> 数据质检报告</h3><span class="ph-hint">时效完整性 + 变量可用性</span></header>
        <div class="qc-summary">
          <div class="qc-ring">
            <svg viewBox="0 0 120 120">
              <circle cx="60" cy="60" r="52" class="ring-bg" />
              <circle cx="60" cy="60" r="52" class="ring-fg" :style="{ strokeDashoffset: ringOffset }" />
            </svg>
            <div class="qc-ring-text">
              <strong>{{ ((quality.integrity ?? 0) * 100).toFixed(0) }}%</strong>
              <span>完整率</span>
            </div>
          </div>
          <div class="qc-stats">
            <div class="qc-stat"><span>应有时效</span><strong>{{ quality.expectedLeads ?? '--' }}</strong></div>
            <div class="qc-stat"><span>实际完整</span><strong>{{ quality.completeLeads ?? '--' }}</strong></div>
            <div class="qc-stat"><span>缺失时效</span><strong :class="{ bad: (quality.missingLeads || []).length }">{{ (quality.missingLeads || []).length }}</strong></div>
            <div class="qc-stat"><span>确定性文件</span><strong>{{ quality.fileCount ?? '--' }}</strong></div>
            <div class="qc-stat"><span>集合文件</span><strong>{{ quality.ensembleFileCount ?? '--' }}</strong></div>
          </div>
        </div>
        <div class="qc-steps">
          <div v-for="s in quality.steps || []" :key="s.name" class="qc-step" :class="s.status">
            <AppIcon :name="s.status === 'pass' ? 'check' : 'alert'" />
            <div><div class="qc-step-name">{{ s.name }}</div><div class="qc-step-detail">{{ s.detail }}</div></div>
            <span class="qc-step-tag">{{ s.status === 'pass' ? '通过' : s.status }}</span>
          </div>
        </div>
      </article>

      <article class="panel">
        <header class="panel-head"><h3><AppIcon name="info" /> 系统边界与口径</h3></header>
        <div class="boundary-list">
          <p>{{ sys.boundaryNote }}</p>
          <div class="bd-row"><span>起报时次</span><strong>{{ fmtCycle(sys.initCycle) }}</strong></div>
          <div class="bd-row"><span>起报时间</span><strong>{{ fmtTime(sys.initialTime) }}</strong></div>
          <div class="bd-row"><span>时效个数</span><strong>{{ sys.leadCount ?? '--' }}</strong></div>
          <div class="bd-row"><span>时间轴节点</span><strong>{{ sys.timelineCount ?? '--' }}</strong></div>
          <div class="bd-note">
            <AppIcon name="info" /> 本页所有指标均由后端从 NetCDF 产品文件实时解析生成，
            非预置静态数据；数据源目录更新后 60 秒内自动感知并刷新。
          </div>
        </div>
      </article>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import AppIcon from './AppIcon.vue'
import { api } from '../api.js'
import { formatFull } from '../chartKit.js'

const props = defineProps({ info: { type: Object, default: () => ({}) } })

const sys = ref({})
const lineage = ref({})
const quality = ref({})
const rt = ref({})
const loading = ref(false)
const error = ref('')

const monitorRunning = computed(() => rt.value.running === true)
const ringOffset = computed(() => {
  const p = Math.max(0, Math.min(1, quality.value.integrity ?? 0))
  return String(2 * Math.PI * 52 * (1 - p))
})

function fmtCycle(c) {
  if (!c || c.length < 10) return c || '--'
  return `${c.slice(0, 4)}-${c.slice(4, 6)}-${c.slice(6, 8)} ${c.slice(8, 10)}时`
}
function fmtTime(v) { return formatFull(v) || '--' }

async function load() {
  loading.value = true; error.value = ''
  try {
    const [s, l, q, r] = await Promise.all([
      api.systemInfo(), api.lineage(), api.quality(), api.realtimeStatus(),
    ])
    sys.value = s; lineage.value = l; quality.value = q; rt.value = r
  } catch (e) {
    error.value = e.message || '系统状态加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(() => props.info?.revision, () => { load() })

defineExpose({ refresh: load })
</script>

<style scoped>
.sys-hero { display: grid; grid-template-columns: 1.5fr 1fr; gap: 14px; }
.hero-card { padding: 18px; border-radius: 12px; background: linear-gradient(140deg, rgba(20,52,78,.75), rgba(10,26,42,.9)); border: 1px solid rgba(47,230,214,.18); }
.hero-brand { display: flex; align-items: center; gap: 14px; margin-bottom: 16px; }
.hero-mark { width: 52px; height: 52px; flex: none; display: grid; place-items: center; font-size: 24px; font-weight: 800; color: #041722; border-radius: 13px; background: linear-gradient(135deg, #2fe6d6, #3fa9ff); box-shadow: 0 6px 20px rgba(47,230,214,.3); }
.hero-brand h3 { margin: 0 0 4px; font-size: 18px; color: var(--text-main); letter-spacing: .5px; }
.hero-brand p { margin: 0; font-size: 12.5px; color: var(--text-dim); }
.hero-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }
.hg-item { display: flex; flex-direction: column; gap: 4px; padding: 9px 11px; border-radius: 8px; background: rgba(8,22,36,.6); border: 1px solid rgba(47,230,214,.1); }
.hg-item span { font-size: 11.5px; color: var(--text-dim); }
.hg-item strong { font-size: 13px; color: var(--cyan); }
.hero-foot { display: flex; align-items: center; flex-wrap: wrap; gap: 14px; margin-top: 14px; padding-top: 13px; border-top: 1px solid rgba(47,230,214,.12); font-size: 12px; }
.hf-tag { display: inline-flex; align-items: center; gap: 5px; padding: 3px 10px; border-radius: 999px; font-weight: 600; }
.hf-tag.ok { color: #7ff0c4; background: rgba(47,230,180,.12); border: 1px solid rgba(47,230,180,.3); }
.hf-tag.warn { color: #ffd08a; background: rgba(255,157,61,.12); border: 1px solid rgba(255,157,61,.3); }
.hf-path, .hf-time { display: inline-flex; align-items: center; gap: 5px; color: var(--text-dim); }

.monitors { display: flex; flex-direction: column; }
.mon-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; }
.mon-item { display: flex; flex-direction: column; gap: 4px; padding: 10px 12px; border-radius: 8px; background: rgba(8,22,36,.6); }
.mon-item span { font-size: 11.5px; color: var(--text-dim); }
.mon-item strong { font-size: 15px; color: var(--cyan); }
.prod-status { display: flex; flex-direction: column; gap: 8px; margin-top: 12px; }
.ps-row { display: grid; grid-template-columns: 1.1fr 1fr 1fr auto; align-items: center; gap: 8px; padding: 9px 11px; border-radius: 8px; background: rgba(8,22,36,.6); font-size: 12px; }
.ps-name { color: var(--text-main); font-weight: 600; }
.ps-meta { color: var(--text-dim); }
.ps-tag.ok { padding: 2px 9px; border-radius: 999px; color: #7ff0c4; background: rgba(47,230,180,.12); font-size: 11px; }

.lineage-flow { display: flex; align-items: stretch; gap: 6px; overflow-x: auto; padding-bottom: 6px; }
.ln-node { flex: 1; min-width: 168px; display: flex; gap: 10px; padding: 12px; border-radius: 10px; background: rgba(10,26,42,.7); border: 1px solid rgba(47,230,214,.14); }
.ln-node.completed { border-color: rgba(47,230,180,.28); }
.ln-idx { width: 24px; height: 24px; flex: none; display: grid; place-items: center; font-size: 12px; font-weight: 700; border-radius: 7px; background: linear-gradient(135deg, #2fe6d6, #1a8fa8); color: #041722; }
.ln-body { flex: 1; min-width: 0; }
.ln-name { font-size: 13px; font-weight: 700; color: var(--text-main); margin-bottom: 4px; }
.ln-detail { font-size: 11.5px; line-height: 1.55; color: var(--text-dim); margin-bottom: 7px; }
.ln-meta { display: flex; flex-wrap: wrap; gap: 7px; font-size: 11px; }
.ln-count, .ln-dur { color: var(--cyan); }
.ln-status { padding: 1px 8px; border-radius: 999px; color: #7ff0c4; background: rgba(47,230,180,.12); }
.ln-arrow { display: flex; align-items: center; color: rgba(47,230,214,.4); }

.lineage-products { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin-top: 14px; }
.lp-card { padding: 12px 14px; border-radius: 10px; background: rgba(8,22,36,.55); border: 1px solid rgba(47,230,214,.12); }
.lp-head { display: flex; align-items: center; gap: 7px; font-size: 13px; font-weight: 700; color: var(--text-main); margin-bottom: 10px; }
.lp-kv { display: flex; justify-content: space-between; font-size: 12px; padding: 4px 0; }
.lp-kv span { color: var(--text-dim); }
.lp-kv strong { color: var(--cyan); }
.lp-src { margin-top: 8px; padding-top: 8px; border-top: 1px dashed rgba(47,230,214,.14); font-size: 11px; color: var(--text-dim); line-height: 1.5; }

.sys-bottom { display: grid; grid-template-columns: 1.6fr 1fr; gap: 14px; }
.qc-summary { display: flex; align-items: center; gap: 26px; margin-bottom: 14px; }
.qc-ring { position: relative; width: 120px; height: 120px; flex: none; }
.qc-ring svg { width: 100%; height: 100%; transform: rotate(-90deg); }
.ring-bg { fill: none; stroke: rgba(44,74,99,.6); stroke-width: 9; }
.ring-fg { fill: none; stroke: url(#g); stroke: #2fe6d6; stroke-width: 9; stroke-linecap: round; stroke-dasharray: 326.7; transition: stroke-dashoffset .6s ease; filter: drop-shadow(0 0 6px rgba(47,230,214,.5)); }
.qc-ring-text { position: absolute; inset: 0; display: grid; place-content: center; text-align: center; }
.qc-ring-text strong { display: block; font-size: 22px; color: var(--cyan); }
.qc-ring-text span { font-size: 11.5px; color: var(--text-dim); }
.qc-stats { flex: 1; display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.qc-stat { display: flex; flex-direction: column; gap: 4px; padding: 10px 12px; border-radius: 8px; background: rgba(8,22,36,.6); }
.qc-stat span { font-size: 11.5px; color: var(--text-dim); }
.qc-stat strong { font-size: 16px; color: var(--text-main); }
.qc-stat strong.bad { color: #ff6b7a; }
.qc-steps { display: flex; flex-direction: column; gap: 8px; }
.qc-step { display: flex; align-items: center; gap: 11px; padding: 10px 12px; border-radius: 8px; background: rgba(8,22,36,.5); border-left: 3px solid #2fe6b4; color: #7ff0c4; }
.qc-step.fail { border-left-color: #ff6b7a; color: #ff6b7a; }
.qc-step > div { flex: 1; }
.qc-step-name { font-size: 12.5px; font-weight: 600; color: var(--text-main); }
.qc-step-detail { font-size: 11.5px; color: var(--text-dim); margin-top: 2px; }
.qc-step-tag { font-size: 11px; padding: 2px 9px; border-radius: 999px; background: currentColor; color: #06131f; font-weight: 700; }

.boundary-list { display: flex; flex-direction: column; gap: 10px; }
.boundary-list > p { margin: 0; font-size: 12.5px; line-height: 1.7; color: var(--text-soft); }
.bd-row { display: flex; justify-content: space-between; font-size: 12.5px; padding: 7px 0; border-bottom: 1px dashed rgba(47,230,214,.12); }
.bd-row span { color: var(--text-dim); }
.bd-row strong { color: var(--cyan); }
.bd-note { display: flex; gap: 8px; margin-top: 4px; padding: 11px 12px; border-radius: 8px; font-size: 12px; line-height: 1.65; color: #9fd8ff; background: rgba(47,169,255,.08); border: 1px solid rgba(47,169,255,.2); }

@media (max-width: 1600px) {
  .sys-hero { grid-template-columns: 1fr; }
  .sys-bottom { grid-template-columns: 1fr; }
  .hero-grid { grid-template-columns: repeat(2, 1fr); }
}
</style>
