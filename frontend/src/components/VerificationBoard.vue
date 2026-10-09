<template>
<main class="page-surface">
<header class="page-head rise-in"><div class="ph-left"><div class="ph-kicker"><i></i><span>Verification Board · Module 06</span></div><h2>预报检验看板</h2><p class="ph-desc">按UTC有效时间、要素及网格匹配预报与分析／观测参考场，支持逐时效曲线和分时段统计，降水按6小时累计量计算分阈值评分；模拟参考仅用于演示。</p></div><div class="ph-right"><span class="module-tag"><b>06</b> 必备功能</span><span class="required-tag must">核心必备</span></div></header>
    <section class="verification-toolbar">
      <label class="task-select">全局预报批次<select v-model="forecast" :disabled="!!props.info.activeBatchId"><option value="">当前启用预报</option><option v-for="b in forecasts" :key="b.id" :value="b.id">{{ b.name }}</option></select></label>
      <label>参考批次<select v-model="reference" :disabled="optionsLoading"><option value="">{{ optionsLoading ? '筛选中…' : '请选择匹配参考' }}</option><option v-for="b in references" :key="b.id" :value="b.id">{{ b.name }} · {{ b.matchedCount }}个匹配时效</option></select></label>
      <label>检验要素<select v-model="variable"><option v-for="v in variables" :key="v.key" :value="v.key">{{ v.name }} · {{ v.unit }}</option></select></label>
      <label>预报范围<select v-model="selectedRange"><option v-for="r in ranges" :key="r.key" :value="r.key">{{ r.label }}</option></select></label>
      <button class="data-pair-button" :disabled="loading || optionsLoading || !reference || !variable" @click="load">{{ loading ? '正在计算…' : '开始检验' }}</button>
    </section>
<p v-if="matched?.synthetic" class="notice-banner notice-info">模拟实况演示：参考降水由0928预报扰动生成，并非真实观测。以下评分仅验证计算流程，不用于证明模型精度。</p>
<p v-if="matched" class="metric-limit">可匹配{{ matched.matchedCount }}个时效：{{ matched.matchedTimes.map(t=>'+'+t.leadHour+'h').join('、') }}。分析参考场不等于站点观测；风要素检验风速。</p>
<details v-if="excluded.length" class="excluded-panel"><summary>{{ excluded.length }}个参考批次不匹配</summary><p v-for="r in excluded" :key="r.id">{{ r.name }}：{{ r.reason }}</p></details>
<div v-if="!data.available" class="empty-state"><strong>{{ loading ? '正在计算检验指标…' : '检验指标暂不可用' }}</strong><span>{{ data.message || '请选择已导入的匹配参考场，开始真实检验。' }}</span></div>
<div v-else class="verify-layout">
<section class="verify-top">
<div class="vt-metrics">
<div v-for="m in continuousSummary" :key="m.key" class="vt-card" :class="{'accent-teal':m.key==='corr','accent-amber':m.key==='bias'}"><span>{{ m.label }}</span><strong>{{ format(m.value) }}</strong><em>{{ m.unit }} · {{ m.direction }}</em></div>
<div class="vt-card accent-violet"><span>参考场来源</span><strong class="small">{{ data.referenceName }}</strong><em>{{ data.synthetic ? '模拟实况 · 演示数据' : data.referenceType === 'analysis' ? '分析参考场' : '观测参考场' }}</em></div>
</div>
<label v-if="variable==='tp'" class="metric-limit">评分阈值（6小时累计） <select v-model.number="selectedThreshold"><option v-for="t in [0.1,1,5,10,20]" :key="t" :value="t">{{t}} mm/6h</option></select></label>
<div class="vt-seg"><div class="seg"><button v-for="r in ranges" :key="r.key" :class="{active:selectedRange===r.key}" @click="selectedRange=r.key">{{ r.label }}</button></div><div class="seg"><button v-for="m in metricOptions.filter(m=>!m.disabled && (!m.precip || variable==='tp'))" :key="m.key" :class="{active:selectedMetric===m.key}" @click="selectedMetric=m.key">{{ m.short }}</button></div></div>
</section>
<section class="panel verify-curve"><div class="panel-head"><div class="panel-title"><i class="bar"></i><h3>{{ currentMetric.short }} 逐时效曲线</h3><span class="panel-sub">{{ rangeConfig.label }}</span></div><div class="panel-extra"><span class="hint-chip">{{ currentMetric.direction }}</span></div></div><div class="panel-body"><div v-if="!chartRows.length" class="chart-empty">该范围没有匹配时效，不生成曲线或评分。</div><div ref="leadChartEl" class="verify-chart"></div></div></section>
<div class="verify-bottom">
<section class="panel"><div class="panel-head"><div class="panel-title"><i class="bar"></i><h3>分级降水检验</h3></div><span class="panel-sub">Threshold Scores</span></div><div class="panel-body scroll-y"><table class="data-table"><thead><tr><th>阈值</th><th>TS</th><th>POD</th><th>FAR</th><th>BIAS</th><th>命中</th><th>空报</th><th>漏报</th></tr></thead><tbody><tr v-for="r in rangeSummary.scores || []" :key="r.threshold"><td>{{r.threshold}} mm/6h</td><td>{{format(r.TS)}}</td><td>{{format(r.POD)}}</td><td>{{format(r.FAR)}}</td><td>{{format(r.BIAS)}}</td><td>{{formatInteger(r.hits)}}</td><td>{{formatInteger(r.falseAlarms)}}</td><td>{{formatInteger(r.misses)}}</td></tr><tr v-if="!rangeSummary.scores?.length"><td colspan="8">当前要素不是降水，分阈值检验不可用。</td></tr></tbody></table><p class="metric-limit">ACC未接入所需气候态；平均偏差不等于降水BIAS。</p></div></section>
<section class="panel"><div class="panel-head"><div class="panel-title"><i class="bar"></i><h3>分时段统计</h3></div><span class="panel-sub">Segment Stats</span></div><div class="panel-body"><div ref="segmentChartEl" class="seg-chart"></div><table class="data-table"><thead><tr><th>范围</th><th>时效数</th><th>MAE</th><th>RMSE</th></tr></thead><tbody><tr v-for="s in data.segments || []" :key="s.key"><td>{{ s.label }}</td><td>{{ s.matchedTimeCount }}</td><td>{{ format(s.mae) }}</td><td>{{ format(s.rmse) }}</td></tr></tbody></table></div></section>
</div>
<section class="panel trace-panel"><div class="panel-head"><div class="panel-title"><i class="bar"></i><h3>数据追溯与口径说明</h3></div><span class="panel-sub">Traceability</span></div><div class="panel-body trace-body"><div class="trace-grid"><div><span>起报时间（UTC）</span><strong>{{ data.cycle }}</strong></div><div><span>参考批次</span><strong>{{ data.referenceName }}</strong></div><div><span>当前范围匹配时效</span><strong>{{ rangeSummary.matchedTimeCount || 0 }}</strong></div><div><span>有效样本／网格</span><strong>{{ formatInteger(rangeSummary.validPoints) }} · 0.25°</strong></div><div><span>检验要素</span><strong>{{ data.variable }}</strong></div><div><span>单位口径</span><strong>{{ data.unit }}</strong></div></div><p class="trace-note">{{ data.referenceSource }}（来源声明未独立认证）。{{ data.referenceNote }}共同有限格点等权合并计算，网格坐标严格匹配、不使用附近时刻代替实况。分析参考场不等于站点观测，不代表竞赛官方评分。</p><p v-for="r in data.skipped" :key="r.leadHour" class="metric-limit">跳过+{{ r.leadHour }}h：{{ r.reason }}</p></div></section>
<details class="panel lead-table"><summary>逐时效检验明细</summary><table class="data-table"><thead><tr><th>时效</th><th>有效时间（UTC）</th><th>样本</th><th>MAE</th><th>RMSE</th><th>平均偏差</th><th>CORR</th></tr></thead><tbody><tr v-for="r in chartRows" :key="r.leadHour"><td>+{{ r.leadHour }}h</td><td>{{ r.validTime }}</td><td>{{ r.validPoints }}</td><td>{{ format(r.mae) }}</td><td>{{ format(r.rmse) }}</td><td>{{ format(r.bias) }}</td><td>{{ format(r.corr) }}</td></tr></tbody></table></details>
</div></main>
</template>
<script setup>
import {ref,computed,onMounted,onBeforeUnmount,nextTick,watch} from 'vue'
import {mountChart,disposeChart} from '../chartKit'
import api from '../api'
const props=defineProps({info:{type:Object,default:()=>({})}})
const batches=ref([]),forecast=ref(''),reference=ref(''),variable=ref(''),loading=ref(false),data=ref({available:false})
const optionsLoading=ref(false),referenceRows=ref([]),excluded=ref([])
const forecasts=computed(()=>batches.value.filter(b=>b.product==='DF'))
const references=computed(()=>referenceRows.value)
const matched=computed(()=>references.value.find(b=>b.id===reference.value))
const variables=computed(()=>references.value.find(b=>b.id===reference.value)?.variables || [])
const format=n=>n==null?'—':Number(n).toFixed(4)
let requestId=0
let optionsId=0
watch([reference,forecast],()=>{requestId++;data.value={available:false};loading.value=false})
watch(variables,v=>{if(!v.some(x=>x.key===variable.value))variable.value=v[0]?.key || ''})
watch(variable,()=>{requestId++;data.value={available:false};loading.value=false;selectedMetric.value='mae'})
watch(forecast,()=>loadOptions())
async function loadOptions(){
  const id=++optionsId,previous=reference.value
  optionsLoading.value=true;loading.value=false;referenceRows.value=[];excluded.value=[];requestId++;data.value={available:false}
  try{
    const result=await api.referenceOptions(forecast.value)
    if(id!==optionsId)return
    referenceRows.value=result.references;excluded.value=result.excluded
    reference.value=references.value.some(b=>b.id===previous)?previous:references.value.find(b=>b.active)?.id || references.value[0]?.id || ''
    if(!references.value.length)data.value={available:false,message:result.message + '；请导入时间、要素和网格匹配的参考批次。'}
  }catch(e){if(id===optionsId){reference.value='';data.value={available:false,message:e.message}}}
  finally{if(id===optionsId)optionsLoading.value=false}
}
async function load(){
  const id=++requestId
  if(optionsLoading.value || !reference.value || !variable.value)return
  loading.value=true
  try{
    const result=await api.verification(24,{reference_id:reference.value,variable:variable.value,...(forecast.value?{forecast_id:forecast.value}:{})})
    if(id===requestId)data.value=result
  }catch(e){if(id===requestId)data.value={available:false,message:e.message}}
  finally{if(id===requestId)loading.value=false}
}
async function refresh(){
  requestId++;loading.value=false;data.value={available:false}
  try{const result=await api.dataBatches();batches.value=result.batches;forecast.value=props.info.activeBatchId || '';await loadOptions()}
  catch(e){data.value={available:false,message:e.message}}
}
onMounted(()=>{refresh();window.addEventListener('resize',onResize)})
defineExpose({refresh})

const selectedThreshold=ref(1)
const selectedMetric=ref('mae'),selectedRange=ref('all'),leadChartEl=ref(null),segmentChartEl=ref(null)
let segmentChart=null,segmentElement=null
let leadChart=null,chartElement=null
const ranges=[{key:'all',label:'全部匹配时效',low:0,high:360},{key:'day1-3',label:'1—3天',low:0,high:72},{key:'day4-10',label:'4—10天',low:72,high:240},{key:'day11-15',label:'11—15天',low:240,high:360}]
const rangeConfig=computed(()=>ranges.find(r=>r.key===selectedRange.value) || ranges[0])
const chartRows=computed(()=>(data.value.series || []).map(r=>({...r,...(r.scores?.find(s=>s.threshold===selectedThreshold.value)||{})})).filter(r=>r.leadHour>rangeConfig.value.low && r.leadHour<=rangeConfig.value.high))
const rangeSummary=computed(()=>selectedRange.value==='all' ? {...data.value.overall,matchedTimeCount:(data.value.series || []).length} : (data.value.segments || []).find(s=>s.key===selectedRange.value) || {matchedTimeCount:0,validPoints:0})
const metricOptions=[
 {key:'mae',label:'MAE 平均绝对误差',short:'MAE',direction:'越小越好',help:'预报与参考值绝对差的平均；与所选要素单位相同。'},
 {key:'rmse',label:'RMSE 均方根误差',short:'RMSE',direction:'越小越好',help:'误差平方均值的平方根，对较大误差更敏感。'},
 {key:'corr',label:'CORR 相关系数',short:'CORR',direction:'越接近1，一致性越高',help:'皮尔逊相关系数，不是准确率或距平相关系数；常量场不可定义。'},
 {key:'bias',label:'平均偏差',short:'平均偏差',direction:'越接近0越好',help:'预报减参考值的平均；正值偏高、负值偏低，不是降水频次BIAS。'},
 {key:'TS',label:'TS评分',short:'TS',precip:true,direction:'越接近1越好'},{key:'POD',label:'POD命中率',short:'POD',precip:true,direction:'越接近1越好'},{key:'FAR',label:'FAR空报率',short:'FAR',precip:true,direction:'越接近0越好'},{key:'BIAS',label:'降水频次BIAS',short:'BIAS',precip:true,direction:'越接近1越好'},{key:'ACC',label:'ACC',disabled:true}
]
const currentMetric=computed(()=>metricOptions.find(m=>m.key===selectedMetric.value) || metricOptions[0])
const metricUnit=computed(()=>['corr','TS','POD','FAR','BIAS'].includes(selectedMetric.value)?'无量纲':data.value.unit || '')
const formatInteger=value=>new Intl.NumberFormat('zh-CN').format(value || 0)
const continuousSummary=computed(()=>metricOptions.filter(m=>!m.disabled && (!m.precip || variable.value==='tp')).map(m=>({...m,value:m.precip?rangeSummary.value.scores?.find(s=>s.threshold===selectedThreshold.value)?.[m.key]:rangeSummary.value[m.key],unit:m.precip||m.key==='corr'?'无量纲':data.value.unit})))
function renderChart(){
 if(!data.value.available || !leadChartEl.value)return
 if(chartElement && chartElement!==leadChartEl.value)disposeChart(chartElement)
 chartElement=leadChartEl.value
 leadChart=mountChart(chartElement) || leadChart
 if(!leadChart)return
 const rows=chartRows.value
 if(!rows.length){leadChart.clear();return}
 const color=selectedMetric.value==='corr'?'#50d9ff':'#50dba8',points=[]
 rows.forEach((r,i)=>{if(i && r.leadHour-rows[i-1].leadHour>6)points.push([rows[i-1].leadHour+6,null]);points.push([r.leadHour,r[selectedMetric.value] ?? null])})
 leadChart.setOption({
  animation:false,
  tooltip:{trigger:'axis',backgroundColor:'#0a285e',borderColor:'#4b81bd',textStyle:{color:'#eaf4ff'},formatter:items=>{const item=items[0];return item ? '+'+item.value[0]+'h<br/>'+currentMetric.value.short+'：'+format(item.value[1])+' '+metricUnit.value : ''}},
  grid:{left:65,right:32,top:40,bottom:50},
  xAxis:{type:'value',name:'预报时效',nameLocation:'middle',nameGap:32,min:rows.length===1?rows[0].leadHour-3:rows[0].leadHour,max:rows.length===1?rows[0].leadHour+3:rows.at(-1).leadHour,minInterval:6,axisLabel:{color:'#8fb8df',formatter:v=>'+'+v+'h'},axisLine:{lineStyle:{color:'#315f9b'}},splitLine:{show:false}},
  yAxis:{type:'value',name:currentMetric.value.short+(selectedMetric.value==='corr'?'':' / '+metricUnit.value),nameTextStyle:{color:'#8fb8df'},axisLabel:{color:'#8fb8df'},splitLine:{lineStyle:{type:'dashed',color:'rgba(119,173,226,.18)'}}},
  series:[{name:currentMetric.value.label,type:'line',smooth:false,connectNulls:false,showSymbol:true,symbolSize:7,data:points,lineStyle:{width:3,color},itemStyle:{color},areaStyle:{color:{type:'linear',x:0,y:0,x2:0,y2:1,colorStops:[{offset:0,color:color+'40'},{offset:1,color:color+'05'}]}}}]
 },true)
}
function renderSegments(){
 if(!segmentChartEl.value)return
 if(segmentElement && segmentElement!==segmentChartEl.value)disposeChart(segmentElement)
 segmentElement=segmentChartEl.value;segmentChart=mountChart(segmentElement)
 if(!segmentChart)return
 const rows=data.value.segments || []
 segmentChart.setOption({tooltip:{trigger:'axis'},legend:{data:['MAE','RMSE'],textStyle:{color:'#93b3d8'}},grid:{left:55,right:20,top:35,bottom:35},xAxis:{type:'category',data:rows.map(r=>r.label),axisLabel:{color:'#93b3d8'}},yAxis:{type:'value',name:data.value.unit,axisLabel:{color:'#93b3d8'},splitLine:{lineStyle:{color:'rgba(88,148,216,.12)'}}},series:[{name:'MAE',type:'bar',data:rows.map(r=>r.mae??null),itemStyle:{color:'#5fd8ff'}},{name:'RMSE',type:'bar',data:rows.map(r=>r.rmse??null),itemStyle:{color:'#ff9a4d'}}]},true)
}
function onResize(){leadChart?.resize();segmentChart?.resize()}
watch([data,selectedMetric,selectedRange,selectedThreshold],async()=>{await nextTick();if(data.value.available){renderChart();renderSegments()}else{disposeChart(chartElement);disposeChart(segmentElement);leadChart=null;chartElement=null;segmentChart=null;segmentElement=null}})
onBeforeUnmount(()=>{requestId++;optionsId++;window.removeEventListener('resize',onResize);disposeChart(chartElement);disposeChart(segmentElement)})
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
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
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

.verification-toolbar{display:grid;grid-template-columns:1.4fr 1.5fr 1fr 1fr auto;gap:10px;align-items:end;padding:12px;border:1px solid var(--line);border-radius:var(--radius);background:rgba(8,22,46,.8)}
.verification-toolbar label{display:grid;gap:5px;font-size:11px;color:var(--text-dim)}
.verification-toolbar select{min-width:0;width:100%;height:36px;background:#102846;color:var(--text);border:1px solid var(--line);border-radius:5px;padding:0 8px}
.verification-toolbar button{height:36px;background:var(--cyan);border:0;border-radius:5px;padding:0 12px}
button:disabled{opacity:.4;cursor:not-allowed}.metric-limit,.excluded-panel{font-size:11px;color:var(--text-dim);margin:8px 0}.verify-layout{flex:none;overflow:visible}.verify-chart{height:280px}.seg-chart{min-height:220px;height:220px}.chart-empty{padding:20px;text-align:center;color:var(--text-dim)}.trace-grid strong{overflow-wrap:anywhere}.trace-note{display:block}.lead-table{overflow:auto}.lead-table summary{padding:12px;cursor:pointer}
@media(max-width:1100px){.verification-toolbar{grid-template-columns:repeat(2,minmax(0,1fr))}.vt-metrics{grid-template-columns:repeat(3,1fr)}.trace-grid{grid-template-columns:repeat(3,1fr)}}
@media(max-width:700px){.verification-toolbar,.verify-bottom{grid-template-columns:1fr}.vt-metrics,.trace-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
