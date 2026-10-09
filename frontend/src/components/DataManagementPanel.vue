<template>
  <main class="page-surface data-page">
    <header class="page-head rise-in">
      <div class="ph-left">
        <div class="ph-kicker"><i></i><span>Data Management</span></div>
        <h2>{{ isAdmin ? '数据管理' : '我的数据' }}</h2>
        <p class="ph-desc">选文件 → 上传到待确认区 → 自动识别 → 确认信息 → 管理员审核入库。来源声明未独立认证，系统不执行模型推理。</p>
      </div>
      <div class="ph-right"><button class="btn btn-ghost" :disabled="busy" @click="load">刷新批次</button></div>
    </header>
    <div v-if="error" class="notice-banner notice-error" role="alert">{{ error }}</div>
    <div v-if="message" class="notice-banner notice-info" role="status">{{ message }}</div>
    <section class="metrics">
      <div class="panel"><span>可用批次</span><strong>{{ batches.length }}</strong></div>
      <div class="panel"><span>待处理／失败任务</span><strong>{{ tasks.length }}</strong></div>
      <div class="panel" v-for="p in ['DF','ens','obs']" :key="p"><span>{{ p === 'obs' ? '默认检验参考' : '启用的' + typeLabel(p) }}</span><strong>{{ batches.find(b => b.active && b.product === p)?.name || '未设置' }}</strong></div>
    </section>
    <section class="panel">
      <div class="panel-head"><h3>① 选择文件并识别</h3><span>最多240个文件 · 单文件128MiB · 单批2GiB</span></div>
      <div class="panel-body">
        <p class="hint">按文件名预选类别，文件内部元数据再次核对。选择类型不会转换文件。DF／ens同起报、SURFACE与PLEVELS配套；参考场地面与高空分批上传。</p>
        <fieldset :disabled="busy">
          <div class="form-row actions">
            <label>数据类别<select v-model="form.product" :disabled="!!job.id"><option value="DF">DF · 确定性预报</option><option value="ens">ens · 集合预报</option><option value="obs">obs · 实况／分析参考场</option></select></label>
            <input ref="fileInput" type="file" multiple accept=".nc" aria-label="选择NetCDF文件" @change="chooseFiles" />
            <span>{{ files.length }}个文件 · {{ sizeLabel }}</span><button class="btn btn-primary" :disabled="!files.length || !!job.id" @click="upload">上传并自动识别</button><button class="btn btn-ghost" :disabled="busy" @click="resetImport">新建导入批次</button>
          </div>
        </fieldset>
        <p class="hint">参考文件使用OBS_ANALYSIS_YYYYMMDDHH.nc、单一UTC有效时间、time/lat/lon和0.25°中国区域网格。降水须明确声明6小时累计起止时间，模拟数据须标注simulated。上次完成后可重新选择文件或新建导入批次。</p>
        <div v-if="busy || progress" class="progress-block"><progress :value="progress" max="100"></progress><span>{{ phase }} · {{ progress }}%</span><button v-if="uploading" class="btn btn-ghost" @click="controller?.abort()">取消上传</button></div>
      </div>
    </section>
    <section v-if="preview.fileCount" class="panel">
      <div class="panel-head"><h3>② 自动识别预览 · 请核对后确认</h3><span>{{ job.status === 'ready' ? '已入库 · 识别信息留存' : '尚未入库／启用' }}</span></div>
      <div class="panel-body">
        <div class="preview-grid">
          <p><span>数据产品</span><strong>{{ preview.dataProduct }}</strong></p>
          <p><span>性质／分组</span><strong>{{ form.product === 'obs' ? referenceLabel(preview.referenceType) : typeLabel(form.product) }} · {{ preview.elementGroup }}</strong></p>
          <p><span>有效时间（UTC）</span><strong>{{ timeRange(preview.validTimes) }} · {{ preview.validTimes?.length }}个时刻</strong></p>
          <p><span>网格</span><strong>{{ preview.grid?.lonCount }}×{{ preview.grid?.latCount }} · {{ preview.grid?.resolution }}</strong></p>
          <p><span>文件／成员数</span><strong>{{ preview.fileCount }}个文件 · {{ preview.members?.length || '无集合成员' }}</strong></p>
          <p><span>要素</span><strong>{{ preview.variableNames?.join('、') }}</strong></p>
        </div>
        <p v-for="p in preview.spatialProcessing" :key="p" class="hint">处理记录（文件声明）：{{ p }}</p>
        <p v-for="p in preview.errors" :key="p" class="bad">{{ p }}</p>
        <div v-if="preview.duplicates?.length" class="duplicate-warning">
          <strong>发现重复文件内容：</strong><p v-for="b in preview.duplicates" :key="b.id">{{ b.name }} · {{ b.exact ? '整批相同' : '部分重复' }} · {{ b.matchedFiles }}个文件 · {{ b.id }}</p>
          <label><input type="checkbox" v-model="form.allowDuplicate" :disabled="busy || job.status !== 'uploading' || job.reviewStatus === 'pending'" />我确认仍需单独登记副本（不代表新增数据）</label>
        </div>
        <fieldset :disabled="busy || job.status !== 'uploading' || job.reviewStatus === 'pending'">
          <div class="form-row">
            <label>批次名称<input v-model="form.name" maxlength="120" /><button class="btn btn-ghost" @click="form.name = preview.suggestedName">恢复建议名称</button></label>
            <label>模型／数据产品<input v-model="form.dataProduct" maxlength="120" /></label>
            <label>来源机构<input v-model="form.institution" maxlength="120" placeholder="未知填未核实" /></label>
            <label>产品版本<input v-model="form.model" maxlength="120" placeholder="未声明" /></label>
          </div>
          <div class="form-row second-row">
            <label>来源说明<input v-model="form.source" maxlength="240" placeholder="文件来源或获取方式；未知填未核实" /></label>
            <label>标签（逗号分隔，最多12个）<input v-model="tagInput" maxlength="240" placeholder="例如：竞赛演示,九月分析" /></label>
            <label>备注<input v-model="form.remarks" maxlength="1000" placeholder="可选：处理过程、用途" /></label>
          </div>
        </fieldset>
        <p class="hint">时间、要素、网格及参考性质以文件为准，不能手工改成另一类数据。机构未知时保留“未核实”；自动识别不代表来源认证。</p>
        <button v-if="job.status === 'uploading' && job.reviewStatus !== 'pending'" class="btn btn-primary" :disabled="busy || !canFinalize" @click="finalize">{{ isAdmin ? '③ 审核通过并入库' : '③ 确认信息并提交审核' }}</button>
      </div>
    </section>
    <section v-if="job.id" class="panel">
      <p v-if="job.reviewStatus==='pending'" class="hint">已提交管理员审核，审核完成前不会进入可用产品。</p>
      <p v-if="job.reviewMessage" class="bad">退回原因：{{job.reviewMessage}}</p>
      <div v-if="isAdmin && job.reviewStatus==='pending'" class="panel-body"><button class="btn btn-primary" :disabled="busy || !canFinalize" @click="approve">审核通过并入库</button><input v-model="reviewReason" placeholder="填写退回原因"><button class="btn btn-ghost" :disabled="busy || !reviewReason.trim()" @click="reject">退回修改</button></div>
      <div class="panel-head"><h3>导入报告 · {{ statusLabel(job.status) }}</h3><span>{{ job.files?.length || 0 }}/{{ job.expectedFiles }}个文件</span></div>
      <div class="panel-body">
        <p v-for="p in job.errors || []" :key="p" class="bad">{{ p }}</p><p v-for="p in job.warnings || []" :key="p" class="hint">{{ p }}</p>
        <p v-if="job.status === 'ready'" class="good">已入库，未自动替换当前数据。{{ job.canActivate ? form.product === 'obs' ? '可在列表设为默认参考，或到检验看板选择。' : '可在列表启用预报。' : '时效不连续，暂不可全局启用。' }}</p>
        <div class="report-table"><table class="data-table"><thead><tr><th>文件</th><th>状态</th><th>识别结果／错误</th></tr></thead><tbody><tr v-for="f in job.files || []" :key="f.name"><td>{{ f.name }}</td><td :class="f.status === 'valid' ? 'good' : 'bad'">{{ f.status === 'valid' ? '通过' : '失败' }}</td><td>{{ f.error || (f.validTime ? f.validTime.slice(0,16).replace('T',' ') + ' UTC · ' + referenceLabel(f.referenceType) : f.cycle + ' UTC · +' + f.lead + 'h · ' + f.kind) }}</td></tr></tbody></table></div>
      </div>
    </section>
    <section class="panel">
      <div class="panel-head"><h3>可用数据批次 · {{ filtered.length }}/{{ batches.length }}</h3></div>
      <div class="panel-body">
        <div class="type-tabs"><button v-for="p in ['', 'DF','ens','obs']" :key="p" class="btn" :class="productFilter === p ? 'btn-primary' : 'btn-ghost'" @click="productFilter = p">{{ p ? typeLabel(p) : '全部' }}（{{ batches.filter(b => !p || b.product === p).length }}）</button></div>
        <div class="filters">
          <input v-model="search" placeholder="搜索名称、编号、来源、标签" aria-label="搜索批次" />
          <select v-model="dataProductFilter" aria-label="筛选数据产品"><option value="">全部产品</option><option v-for="p in productChoices" :key="p">{{ p }}</option></select>
          <select v-model="sourceFilter" aria-label="筛选来源"><option value="">全部来源说明</option><option v-for="p in sourceChoices" :key="p">{{ p }}</option></select>
          <select v-model="variableFilter" aria-label="筛选要素"><option value="">全部要素</option><option v-for="v in variableChoices" :key="v.key" :value="v.key">{{ v.name }}</option></select>
          <select v-model="statusFilter" aria-label="筛选状态"><option value="">全部状态</option><option value="active">正在使用</option><option value="ready">校验可用</option></select>
          <label>日期起<input v-model="dateStart" type="date" /></label><label>日期止<input v-model="dateEnd" type="date" /></label>
          <button class="btn btn-ghost" @click="resetFilters">清空筛选</button>
        </div>
        <p class="hint">日期按UTC：预报筛选起报日期，参考场筛选有效时间范围；唯一编号用于区分同名批次。</p>
        <div class="scroll-y"><table class="data-table"><thead><tr><th>批次／产品</th><th>来源／性质</th><th>时间口径（UTC）</th><th>要素／文件</th><th>状态</th><th>操作</th></tr></thead><tbody>
          <tr v-for="b in filtered" :key="b.id">
            <td>{{ b.name }}<small>{{ b.dataProduct || b.model }} · {{ b.productVersion || b.model }}</small><small class="batch-id">{{ b.id }}</small><small>{{ (b.tags || []).join(' · ') }}</small></td>
            <td>{{ b.source }}<small>{{ b.institution || '未核实' }} · {{ b.product === 'obs' ? referenceLabel(b.referenceType) : typeLabel(b.product) }}</small><small>来源未独立认证</small></td>
            <td v-if="b.product === 'obs'">有效时间：{{ timeRange(b.validTimes) }}<small>{{ b.validTimes?.length }}个时刻</small></td>
            <td v-else>起报：{{ b.cycle }}<small>预报时效：+{{ b.leads[0] }}—{{ b.leads.at(-1) }}h</small></td>
            <td>{{ b.variables?.map(v => v.shortName).join('、') }}<small>{{ b.fileCount }}个文件</small></td>
            <td>{{ b.active ? b.product === 'obs' ? '默认参考' : '启用预报' : '校验可用' }}</td>
            <td class="row-actions"><button class="btn btn-ghost" @click="detail = b">详情</button><button v-if="isAdmin" class="btn btn-primary" :disabled="busy || b.active || !b.canActivate" @click="activate(b)">{{ b.product === 'obs' ? '设为默认参考' : '启用预报' }}</button><button v-if="isAdmin && !b.builtin && !b.active" class="btn btn-ghost" :disabled="busy" @click="remove(b)">移除</button></td>
          </tr>
        </tbody></table></div><p v-if="!filtered.length" class="hint">没有匹配批次；失败任务不进入可用列表。</p>
      </div>
    </section>
    <section v-if="detail" class="panel"><div class="panel-head"><h3>{{ detail.name }} · 详情</h3><button class="btn btn-ghost" @click="detail = null">收起</button></div><div class="panel-body detail-grid">
      <p>唯一编号：{{ detail.id }}</p><p>产品：{{ detail.dataProduct || '未识别' }} · 性质：{{ detail.product === 'obs' ? referenceLabel(detail.referenceType) : typeLabel(detail.product) }}</p>
      <p>网格：{{ detail.grid?.lonCount }}×{{ detail.grid?.latCount }} · {{ detail.grid?.resolution }}</p>
      <p>要素：{{ detail.variables?.map(v => v.name).join('、') }} · 成员：{{ detail.members?.length || '无集合成员' }}</p>
      <p>{{ detail.product === 'obs' ? '有效时间（UTC）：' + detail.validTimes.join('、') : '起报（UTC）：' + detail.cycle + '；时效：' + detail.leads.join('、') + 'h' }}</p>
      <p v-for="p in detail.spatialProcessing || []" :key="p">处理记录：{{ p }}</p><p>备注：{{ detail.remarks || '无' }}</p>
      <p v-for="w in detail.warnings" :key="w" class="hint">{{ w }}</p><p class="hint">分析参考场不等于站点观测，没有匹配参考数据不生成检验分数。</p>
    </div></section>
    <section v-if="tasks.length" class="panel"><div class="panel-head"><h3>待处理／失败任务</h3></div><div class="panel-body"><div v-for="t in tasks" :key="t.id" class="task-row"><span>{{ t.name }} · {{ t.reviewStatus === 'pending' ? '待审核' : t.reviewStatus === 'returned' ? '退回修改' : statusLabel(t.status) }} · {{ t.createdAt }}</span><button class="btn btn-ghost" :disabled="busy" @click="viewJob(t.id)">查看／确认</button></div></div></section>
  </main>
</template>

<script setup>
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import api from '../api'
const props=defineProps({isAdmin:Boolean})
const emit = defineEmits(['batch-activated'])
const reviewReason=ref('')
const batches=ref([]),tasks=ref([]),detail=ref(null),job=ref({}),preview=ref({}),files=ref([]),fileInput=ref(null)
const busy=ref(false),uploading=ref(false),error=ref(''),message=ref(''),progress=ref(0),phase=ref(''),tagInput=ref('')
const search=ref(''),productFilter=ref(''),dataProductFilter=ref(''),sourceFilter=ref(''),variableFilter=ref(''),statusFilter=ref(''),dateStart=ref(''),dateEnd=ref('')
const blankForm=product=>({product,name:'',source:'',model:'',dataProduct:'',institution:'未核实',remarks:'',allowDuplicate:false})
const form=ref(blankForm('DF'))
let controller=null
const typeLabel=p=>({DF:'确定性预报',ens:'集合预报',obs:'参考数据'}[p] || p)
const referenceLabel=p=>p==='simulated'?'模拟实况（非真实观测）':p==='analysis'?'分析参考场':p==='observation'?'观测参考场':'参考性质未声明'
const timeRange=times=>times?.length ? times[0].slice(0,16).replace('T',' ')+'—'+times.at(-1).slice(0,16).replace('T',' ') : '未识别'
const sizeLabel=computed(()=>((files.value.reduce((s,f)=>s+f.size,0))/1024/1024).toFixed(1)+'MiB')
const canFinalize=computed(()=>preview.value.complete && !(preview.value.errors || []).length && form.value.name.trim() && form.value.source.trim() && (!preview.value.duplicates?.length || form.value.allowDuplicate))
const productChoices=computed(()=>[...new Set(batches.value.map(b=>b.dataProduct).filter(Boolean))].sort())
const sourceChoices=computed(()=>[...new Set(batches.value.map(b=>b.source).filter(Boolean))].sort())
const variableChoices=computed(()=>[...new Map(batches.value.flatMap(b=>b.variables || []).map(v=>[v.key,v])).values()])
const filtered=computed(()=>batches.value.filter(b=>{
  const text=[b.name,b.id,b.source,b.dataProduct,b.institution,...(b.tags || [])].join(' ').toLowerCase()
  const start=b.product==='obs'?b.validTimeStart?.slice(0,10):b.cycle?.slice(0,4)+'-'+b.cycle?.slice(4,6)+'-'+b.cycle?.slice(6,8)
  const end=b.product==='obs'?b.validTimeEnd?.slice(0,10):start
  return (!productFilter.value || b.product===productFilter.value) && text.includes(search.value.toLowerCase())
    && (!dataProductFilter.value || b.dataProduct===dataProductFilter.value) && (!sourceFilter.value || b.source===sourceFilter.value)
    && (!variableFilter.value || b.variables?.some(v=>v.key===variableFilter.value))
    && (!statusFilter.value || (statusFilter.value==='active'?b.active:!b.active))
    && (!dateStart.value || end>=dateStart.value) && (!dateEnd.value || start<=dateEnd.value)
}))
function resetFilters(){search.value=productFilter.value=dataProductFilter.value=sourceFilter.value=variableFilter.value=statusFilter.value=dateStart.value=dateEnd.value=''}
const statusLabel=s=>({uploading:'待确认／待完成',ready:'校验通过',failed:'校验失败',removed:'已移除，文件保留'}[s] || s)
async function load(){try{const d=await api.dataBatches();batches.value=d.batches;tasks.value=d.jobs.filter(j=>!['ready','removed'].includes(j.status))}catch(e){error.value=e.message}}
function chooseFiles(e){
  files.value=Array.from(e.target.files || []);progress.value=0;job.value={};preview.value={};error.value='';message.value='';tagInput.value=''
  const kinds=new Set(files.value.map(f=>f.name.startsWith('OBS_')?'obs':/_ENS_/.test(f.name)?'ens':/_FCST_/.test(f.name)?'DF':null).filter(Boolean))
  form.value=blankForm(kinds.size===1?[...kinds][0]:form.value.product)
  if(kinds.size>1)error.value='请将不同类别的文件分批选择'
}
function resetImport(){
  if(busy.value)return
  if(job.value.status==='uploading' && !window.confirm('当前待确认任务会保留，可稍后在任务列表查看。现在开始新批次？'))return
  files.value=[];job.value={};preview.value={};progress.value=0;phase.value='';error.value='';message.value='';tagInput.value=''
  form.value=blankForm(form.value.product)
  if(fileInput.value)fileInput.value.value=''
}
function applyPreview(p,saved={}){
  preview.value=p
  form.value={...blankForm(saved.product || form.value.product),name:saved.metadataConfirmed?saved.name:p.suggestedName || '',
    source:saved.metadataConfirmed?saved.source:p.suggestedSource || '未核实',model:saved.metadataConfirmed?saved.model:p.suggestedModel || '未声明',
    dataProduct:saved.dataProduct || p.dataProduct || '未识别产品',institution:saved.institution || p.institution || '未核实',
    remarks:saved.remarks || '',allowDuplicate:saved.allowDuplicate || false}
  tagInput.value=(saved.tags || []).join(',')
}
async function upload(){
  error.value='';message.value=''
  if(!files.value.length || files.value.length>240 || new Set(files.value.map(f=>f.name)).size!==files.value.length){error.value='请选1—240个不重名文件；地面与高空分批上传';return}
  const total=files.value.reduce((s,f)=>s+f.size,0)
  if(total>2*1024**3 || files.value.some(f=>f.size>128*1024**2 || !f.size)){error.value='文件为空或超过容量限制';return}
  busy.value=uploading.value=true;controller=new AbortController();let completed=0
  try{
    job.value=await api.createImport({product:form.value.product,expectedFiles:files.value.length,staged:true})
    for(const [i,file] of files.value.entries()){
      phase.value='上传并识别 '+(i+1)+'/'+files.value.length+'：'+file.name
      job.value=await api.uploadFile(job.value.id,file,fraction=>{progress.value=Math.floor((completed+file.size*fraction)/total*100)},controller.signal)
      completed+=file.size
    }
    progress.value=100
    applyPreview(await api.importPreview(job.value.id))
    phase.value='自动识别完成，请核对并确认信息入库'
  }catch(e){error.value=e.message;phase.value='任务未完成，可查看报告；重新选择文件可创建新任务'}
  finally{busy.value=uploading.value=false;await load()}
}
async function finalize(){
  if(!canFinalize.value){error.value='请核对完整文件、名称、来源及重复提示';return}
  const tags=[...new Set(tagInput.value.split(/[,，]/).map(x=>x.trim()).filter(Boolean))]
  if(tags.length>12){error.value='最多12个标签';return}
  busy.value=true;error.value=''
  try{
    const {product,...fields}=form.value
    await api.updateImportMetadata(job.value.id,{...fields,tags})
    job.value=await api.finalizeImport(job.value.id);phase.value=job.value.reviewStatus==='pending'?'已提交审核':statusLabel(job.value.status)
    if(job.value.status==='ready' && fileInput.value)fileInput.value.value=''
    await load()
  }catch(e){error.value=e.message}finally{busy.value=false}
}
async function activate(b){busy.value=true;error.value='';try{await api.activateBatch(b.id);await load();message.value=(b.product==='obs'?'已设为默认参考：':'已启用预报：')+b.name;emit('batch-activated')}catch(e){error.value=e.message}finally{busy.value=false}}
async function remove(b){if(!window.confirm('从可用列表移除“'+b.name+'”？原始文件保留。'))return;busy.value=true;try{const r=await api.removeBatch(b.id);message.value=r.message;await load()}catch(e){error.value=e.message}finally{busy.value=false}}
async function viewJob(id){busy.value=true;error.value='';try{job.value=await api.importStatus(id);form.value.product=job.value.product;applyPreview(await api.importPreview(id),job.value);files.value=[];progress.value=0;phase.value='已载入任务报告'}catch(e){error.value=e.message}finally{busy.value=false}}
async function approve(){busy.value=true;error.value='';try{job.value=await api.finalizeImport(job.value.id);await load()}catch(e){error.value=e.message}finally{busy.value=false}}
async function reject(){busy.value=true;error.value='';try{job.value=await api.rejectImport(job.value.id,reviewReason.value);reviewReason.value='';await load()}catch(e){error.value=e.message}finally{busy.value=false}}
onMounted(load)
onBeforeUnmount(()=>controller?.abort())
defineExpose({refresh:load})
</script>
<style scoped>
.data-page{display:flex;flex-direction:column;gap:14px}.metrics{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px}.metrics .panel{padding:16px;gap:8px}.metrics strong{font-size:17px;color:var(--cyan);overflow-wrap:anywhere}.metrics span,.hint,.panel-head>span{font-size:12px;color:var(--text-dim)}fieldset{border:0;padding:0;margin:0}.form-row,.filters{display:flex;gap:12px;flex-wrap:wrap}.form-row label{display:flex;flex-direction:column;gap:6px;flex:1;min-width:180px}.form-row input,.form-row select,.filters input,.filters select{padding:9px;border:1px solid var(--line);border-radius:6px;background:var(--bg-panel,#0a1930);color:var(--text)}.actions{align-items:end;margin:12px 0}.actions label{max-width:280px}.second-row{margin-top:14px}.progress-block{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin:12px 0}.progress-block progress{width:35%;accent-color:#5fd8ff}.preview-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.preview-grid p{border:1px solid var(--line);padding:12px;border-radius:6px;overflow-wrap:anywhere}.preview-grid span{display:block;color:var(--text-dim);font-size:12px}.preview-grid strong{display:block;margin-top:7px;font-size:14px}.duplicate-warning{padding:12px;margin:12px 0;border:1px solid #ce9b48;border-radius:6px;color:#ffd18b}.type-tabs{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px}.filters{align-items:end}.filters label{font-size:12px;display:flex;flex-direction:column;gap:5px}.report-table{max-height:260px;overflow:auto;margin:12px 0}.bad{color:#ff8294}.good{color:#56dbb2}.row-actions{white-space:nowrap}.row-actions button{margin:2px}.data-table small{display:block;color:var(--text-dim);margin-top:5px}.batch-id{font-family:monospace;font-size:10px;overflow-wrap:anywhere}.detail-grid{overflow-wrap:anywhere}.task-row{display:flex;justify-content:space-between;gap:12px;padding:8px 0}@media(max-width:1100px){.metrics{grid-template-columns:repeat(2,1fr)}.preview-grid{grid-template-columns:repeat(2,1fr)}}@media(max-width:650px){.preview-grid{grid-template-columns:1fr}}
</style>
