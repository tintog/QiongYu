import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript } from '@vue/compiler-sfc'
import * as Vue from 'vue'

globalThis.window = { addEventListener() {}, removeEventListener() {}, confirm: () => true }
const renderer = Vue.createRenderer({ createElement:()=>({}),createText:()=>({}),createComment:()=>({}),setText(){},setElementText(){},patchProp(){},insert(){},remove(){},parentNode:()=>null,nextSibling:()=>null })
const settle = async () => { await Vue.nextTick(); await new Promise(r=>setImmediate(r)); await Vue.nextTick() }
function mount(name,api,chartKit={},props={}) {
  const source=readFileSync(new URL('../src/components/'+name+'.vue',import.meta.url),'utf8')
  const {descriptor}=parse(source)
  const code=compileScript(descriptor,{id:'workflow-test'}).content
    .replace(/import\s*\{([^}]+)\}\s*from 'vue'/g,(_,names)=>'const {'+names+'} = Vue')
    .replace(/import api from '[^']+'/g,'')
    .replace(/import\s*\{([^}]+)\}\s*from '..\/chartKit'/g,(_,names)=>'const {'+names+'} = chartKit')
    .replace('export default','return')
  const component=new Function('Vue','api','chartKit',code)(Vue,api,chartKit)
  component.render=()=>null
  const root={}; renderer.render(Vue.h(component,props),root)
  return {root,get state(){return root._vnode.component.setupState},get emitted(){return root._vnode.component.emitted},unmount(){renderer.render(null,root)}}
}

const variables=[{key:'t2m',name:'气温',shortName:'气温',unit:'℃'},{key:'z500',name:'高度',shortName:'高度',unit:'gpm'}]
const times=['2026-09-28T00:00:00','2026-09-28T06:00:00','2026-09-28T12:00:00','2026-09-28T18:00:00']
const batches=[{id:'a',name:'A预报',product:'DF',cycle:'2026092800',active:true,variables,source:'source A',dataProduct:'A'},
 {id:'b',name:'B预报',product:'DF',cycle:'2026092700',variables,source:'source B',dataProduct:'B'},
 {id:'r',name:'CRALand',product:'obs',variables:[variables[0]],source:'CRALand analysis',dataProduct:'CRALand',referenceType:'analysis',validTimes:times,validTimeStart:times[0],validTimeEnd:times[3],tags:['demo']}]
let currentJob,uploaded=0,activations=0,createBody
const preview={fileCount:2,dataProduct:'CRALand',referenceType:'analysis',suggestedName:'CRALand · 地面分析 · 20260928',suggestedSource:'CRALand analysis',suggestedModel:'V1.0.0',institution:'未核实',complete:true,errors:[],duplicates:[],variableNames:['T2M'],validTimes:times,spatialProcessing:[],grid:{lonCount:281,latCount:177,resolution:'0.25°'}}
const dataApi={dataBatches:async()=>({batches,jobs:[]}),
 createImport:async body=>{createBody=body;return currentJob={...body,id:'import-id',status:'uploading',files:[]}},
 uploadFile:async(id,file,p)=>{p(.5);p(1);uploaded++;currentJob={...currentJob,files:[...currentJob.files,{name:file.name,status:'valid'}]};return currentJob},
 importPreview:async()=>({...preview,duplicates:[]}),importStatus:async()=>currentJob,
 updateImportMetadata:async(id,body)=>{currentJob={...currentJob,...body,metadataConfirmed:true};return currentJob},
 finalizeImport:async()=>({...currentJob,status:'ready',canActivate:true,errors:[],warnings:[]}),
 activateBatch:async()=>{activations++},removeBatch:async()=>({message:'retained'})}
let activationEvents=0
const data=mount('DataManagementPanel',dataApi,{}, {isAdmin:true,onBatchActivated:()=>activationEvents++})
await settle()
data.state.chooseFiles({target:{files:[{name:'OBS_ANALYSIS_2026092800.nc',size:10},{name:'OBS_ANALYSIS_2026092806.nc',size:20}]}})
assert.equal(data.state.form.product,'obs')
await data.state.upload()
assert.equal(uploaded,2);assert.equal(data.state.progress,100)
assert.deepEqual(createBody,{product:'obs',expectedFiles:2,staged:true})
assert.equal(data.state.job.status,'uploading')
assert.equal(data.state.form.name,preview.suggestedName)
assert.equal(data.state.form.model,'V1.0.0')
assert.ok(data.state.canFinalize)
data.state.preview.duplicates=[{id:'existing',name:'old batch'}]
assert.equal(data.state.canFinalize,false)
data.state.form.allowDuplicate=true
data.state.form.name='用户确认的名称';data.state.tagInput='demo,九月,demo'
data.state.fileInput={value:'previous selection'}
await data.state.finalize()
assert.equal(data.state.fileInput.value,'')
assert.equal(data.state.job.status,'ready')
assert.equal(currentJob.name,'用户确认的名称');assert.deepEqual(currentJob.tags,['demo','九月'])
await data.state.activate(batches[0])
assert.equal(activations,1);assert.equal(activationEvents,1)
data.state.productFilter='obs';assert.equal(data.state.filtered.length,1)
data.state.search='demo';assert.equal(data.state.filtered.length,1)
data.state.dateStart='2026-09-29';assert.equal(data.state.filtered.length,0)
data.state.resetFilters();data.state.variableFilter='z500';assert.equal(data.state.filtered.length,2)
data.state.resetFilters()
await data.state.viewJob('import-id')
assert.equal(data.state.form.name,'用户确认的名称')
assert.equal(data.state.tagInput,'demo,九月')
assert.equal(data.state.compare,undefined)
const panelSource=readFileSync(new URL('../src/components/DataManagementPanel.vue',import.meta.url),'utf8')
assert.match(panelSource,/value="obs">obs/)
assert.doesNotMatch(panelSource,/@click="compare/)
const appSource=readFileSync(new URL('../src/App.vue',import.meta.url),'utf8')
assert.doesNotMatch(appSource,/ModelComparison|key: 'comparison'/)
data.state.resetImport()
assert.equal(data.state.files.length,0);assert.equal(data.state.job.id,undefined)
assert.equal(data.state.progress,0)
data.state.chooseFiles({target:{files:[{name:'OBS_ANALYSIS_2026092800.nc',size:10},{name:'OBS_ANALYSIS_2026092806.nc',size:20}]}})
await data.state.upload()
assert.equal(uploaded,4);assert.equal(data.state.job.status,'uploading')
assert.equal(batches.length,3)
data.unmount()
console.log('PASS: staged upload, auto metadata, duplicate confirmation, tags, catalog filters, restored user name, activation')

const matched={...batches[2],matchedCount:3,matchedTimes:[{leadHour:6},{leadHour:12},{leadHour:18}]}
let verifyParams,optionDeferred=false
const pending=[]
const verifyApi={dataBatches:async()=>({batches}),
 referenceOptions:async()=>optionDeferred?new Promise(resolve=>pending.push(resolve)):{references:[matched],excluded:[{id:'bad',name:'bad',reason:'有效时间不匹配'}]},
 verification:async(lead,params)=>{verifyParams=params;return {available:true,overall:{mae:1},series:[{leadHour:6,mae:1,corr:.9},{leadHour:18,mae:2,corr:.8}],segments:[{key:'day4-10',matchedTimeCount:0,validPoints:0,mae:null}],unit:'℃'}}}
let chartOption,cleared=0,disposed=0
const chart={setOption:o=>chartOption=o,clear:()=>cleared++,resize(){}}
const board=mount('VerificationBoard',verifyApi,{mountChart:()=>chart,disposeChart:el=>{if(el)disposed++}})
await settle()
assert.equal(board.state.references.length,1);assert.equal(board.state.matched.matchedCount,3)
assert.equal(board.state.excluded.length,1);assert.equal(board.state.variable,'t2m')
board.state.leadChartEl={}
await board.state.load();await settle()
assert.deepEqual(chartOption.series[0].data,[[6,1],[12,null],[18,2]])
assert.equal(chartOption.xAxis.type,'value');assert.equal(chartOption.series[0].connectNulls,false)
assert.match(chartOption.yAxis.name,/℃/)
board.state.segmentChartEl={}
board.state.renderSegments()
assert.equal(chartOption.yAxis.name,'℃')
assert.deepEqual(chartOption.series[0].data,[null])
assert.deepEqual(chartOption.series[1].data,[null])
board.state.segmentChartEl=null
const verificationSource=readFileSync(new URL('../src/components/VerificationBoard.vue',import.meta.url),'utf8')
for(const layoutClass of ['vt-metrics','verify-curve','verify-bottom','trace-grid']){
  assert.ok(verificationSource.includes(layoutClass))
}
assert.ok(verificationSource.includes('分级降水检验'))
assert.doesNotMatch(verificationSource,/verification-summary/)
board.state.selectedMetric='corr';await settle()
assert.doesNotMatch(chartOption.yAxis.name,/℃/)
board.state.selectedRange='day4-10';await settle()
assert.equal(board.state.chartRows.length,0);assert.equal(board.state.rangeSummary.mae,null)
assert.ok(cleared);board.state.selectedRange='all';await settle()
assert.equal(verifyParams.reference_id,'r');assert.equal(verifyParams.variable,'t2m')
optionDeferred=true
const older=board.state.loadOptions()
board.state.forecast='b';await settle()
assert.equal(pending.length,2)
pending[1]({references:[{...matched,id:'r2',variables:[variables[1]],matchedCount:4}],excluded:[]})
await settle();pending[0]({references:[matched],excluded:[]})
await older;await settle()
assert.equal(board.state.reference,'r2');assert.equal(board.state.variable,'z500')
assert.equal(board.state.matched.matchedCount,4);assert.equal(board.state.data.available,false)
assert.ok(disposed)
board.unmount()
console.log('PASS: reference matching count, excluded reasons, supported variables and stale candidate response protection')
let globalForecast
const globalBoard=mount('VerificationBoard',{
 dataBatches:async()=>({batches}),
 referenceOptions:async id=>{globalForecast=id;return {references:[matched],excluded:[]}}
},{mountChart:()=>chart,disposeChart(){}},{info:{activeBatchId:'b'}})
await settle()
assert.equal(globalBoard.state.forecast,'b')
assert.equal(globalForecast,'b')
globalBoard.unmount()
assert.match(appSource,/view \+ ':' \+ dataEpoch/)
assert.match(appSource,/v-if="!switching"/)
assert.match(appSource,/全局预报批次／起报时间/)
console.log('PASS: verification follows global batch; page remount and switching guard are wired')

// Exercise the actual XHR API client, including already-aborted uploads.
const realApi=(await import('../src/api.js')).default
let xhrCount=0
globalThis.XMLHttpRequest=class {
  constructor(){xhrCount++;this.upload={}}
  open(){}setRequestHeader(){}
  send(){this.upload.onprogress({lengthComputable:true,loaded:5,total:10});this.status=200;this.responseText=JSON.stringify({code:0,data:{id:'ok'}});queueMicrotask(()=>this.onload())}
  abort(){this.onabort?.()}
}
let fraction=0
assert.deepEqual(await realApi.uploadFile('id',{name:'a.nc'},x=>fraction=x),{id:'ok'})
assert.equal(fraction,.5)
const aborted=new AbortController();aborted.abort()
await assert.rejects(realApi.uploadFile('id',{name:'a.nc'},null,aborted.signal),/取消/)
assert.equal(xhrCount,1)
console.log('PASS: XHR progress, successful response, pre-aborted upload rejection')
