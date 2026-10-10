/** Geographic catalog and resource lifecycle; independent of Cesium for deterministic tests. */
export function validateBuildingCatalog(value,origin='http://localhost'){
 if(value?.version!==1||!Array.isArray(value.regions))throw Error('不支持的建筑目录格式');
 const regions=[],warnings=[],ids=new Set();
 for(const raw of value.regions){try{
  if(!/^[a-z0-9][a-z0-9-]{0,63}$/.test(raw.id)||ids.has(raw.id))throw Error('区域ID无效或重复');
  const b=raw.bounds,c=raw.center;
  if(!Array.isArray(b)||b.length!==4||!b.every(Number.isFinite)||b[0]>=b[2]||b[1]>=b[3]||b[0]<-180||b[2]>180||b[1]<-90||b[3]>90)throw Error('覆盖范围无效');
  if(!Array.isArray(c)||c.length!==2||!c.every(Number.isFinite)||c[0]<b[0]||c[0]>b[2]||c[1]<b[1]||c[1]>b[3])throw Error('中心不在覆盖范围内');
  if(typeof raw.tilesetUrl!=='string'||!raw.tilesetUrl.trim()||typeof raw.credit?.url!=='string'||!raw.credit.url.trim())throw Error('缺少模型或署名地址');
  const url=new URL(raw.tilesetUrl,origin),creditUrl=new URL(raw.credit?.url,origin);
  if(!['http:','https:'].includes(url.protocol)||url.username||url.password||!['http:','https:'].includes(creditUrl.protocol)||creditUrl.username||creditUrl.password)throw Error('资源或署名地址无效');
  if(!raw.name||!raw.credit?.text||!raw.credit?.license)throw Error('缺少名称、来源或许可');
  const maxHeight=raw.maxCameraHeight??60000;
  if(!Number.isFinite(maxHeight)||maxHeight<=0||maxHeight>150000)throw Error('近景加载高度无效');
  if(raw.grounding && (!['absolute','terrain-center'].includes(raw.grounding.mode)||!Number.isFinite(raw.grounding.baseElevation)))throw Error('高程基准无效');
  ids.add(raw.id);regions.push({...raw,bounds:[...b],center:[...c],maxCameraHeight:maxHeight,priority:Number(raw.priority)||0,enabled:raw.enabled!==false,credit:{...raw.credit,url:creditUrl.href}});
 }catch(e){warnings.push(`${raw?.id||'未命名区域'}：${e.message}`)}}
 return {regions,warnings};
}
export function intersectsBounds(a,b){return !!a&&!!b&&a[0]<=b[2]&&a[2]>=b[0]&&a[1]<=b[3]&&a[3]>=b[1]}
export function selectBuildingRegions(regions,view,limit=2){
 if(!view?.enabled||view.suspended||!Number.isFinite(view.height))return [];
 const center=view.center||[105,32];
 const candidates=regions.filter(r=>r.enabled&&view.height<=r.maxCameraHeight&&intersectsBounds(r.bounds,view.bounds));
 const distance=r=>(r.center[0]-center[0])**2*Math.cos(center[1]*Math.PI/180)**2+(r.center[1]-center[1])**2;
 candidates.sort((a,b)=>b.priority-a.priority||distance(a)-distance(b)||a.id.localeCompare(b.id));
 const groups=new Set();return candidates.filter(r=>{if(!r.group)return true;if(groups.has(r.group))return false;groups.add(r.group);return true}).slice(0,limit);
}
export function createRegionalBuildingManager({load,attach,detach,onChange=()=>{},now=Date.now,maxResident=2,maxConcurrent=2,idleMs=10000,retryMs=30000,timeoutMs=15000}){
 let regions=[],view={},dead=false,workers=0;const states=new Map();
 const stateFor=id=>{if(!states.has(id))states.set(id,{id,phase:'idle',resource:null,wanted:false,lastSeen:0,failedAt:0,error:'',token:null});return states.get(id)};
 const notify=()=>onChange(snapshot());
 function drop(s){if(s.resource){detach(s.resource);s.resource=null}if(s.token)s.token.cancelled=true;s.token=null;s.phase='idle';s.error=''}
 function snapshot(){const entries=[...states.values()].map(s=>({id:s.id,phase:s.phase,wanted:s.wanted,error:s.error}));return {entries,loaded:entries.filter(s=>s.phase==='ready').length,visible:entries.filter(s=>s.phase==='ready'&&s.wanted).length,loading:entries.filter(s=>s.phase==='loading').length,failed:entries.filter(s=>s.phase==='error').length,selected:entries.filter(s=>s.wanted).length}}
 function pump(){
  if(dead)return;const wanted=selectBuildingRegions(regions,view,maxResident),ids=new Set(wanted.map(r=>r.id));
  for(const s of states.values()){
   s.wanted=ids.has(s.id);if(s.wanted)s.lastSeen=now();
   if(s.resource)s.resource.show=s.wanted;
   if(!s.wanted&&(s.phase==='loading'||view.suspended||!view.enabled||now()-s.lastSeen>=idleMs))drop(s);
  }
  for(const region of wanted){const s=stateFor(region.id);s.wanted=true;s.lastSeen=now();if(s.phase==='ready'||s.phase==='loading'||(s.phase==='error'&&now()-s.failedAt<retryMs)||workers>=maxConcurrent)continue;
   // Evict inactive residents before starting another source; never exceed the resource cap.
   let used=[...states.values()].filter(t=>t.resource||t.phase==='loading').length;
   const inactive=[...states.values()].filter(t=>!t.wanted&&t.resource).sort((a,b)=>a.lastSeen-b.lastSeen);
   while(used>=maxResident&&inactive.length){drop(inactive.shift());used--}
   if(used>=maxResident)continue;
   const token={cancelled:false};s.token=token;s.phase='loading';s.error='';workers++;
   let timer,expired=false;
   const operation=Promise.resolve().then(()=>load(region)).then(resource=>{if(expired||token.cancelled||dead){detach(resource);throw Error('区域请求已取消')}return resource});
   const deadline=new Promise((_,reject)=>{timer=setTimeout(()=>{expired=true;reject(Error('建筑连接超时，可重试'))},timeoutMs)});
   Promise.race([operation,deadline]).then(resource=>{if(dead||token.cancelled||s.token!==token){detach(resource);return}try{attach(resource,region)}catch(e){detach(resource);throw e}s.resource=resource;s.phase='ready';resource.show=s.wanted}).catch(e=>{if(!dead&&!token.cancelled&&s.token===token){s.phase='error';s.failedAt=now();s.error=e.message}}).finally(()=>{clearTimeout(timer);workers--;if(s.token===token)s.token=null;if(!dead){pump();notify()}});
  }notify();
 }
 return {setCatalog(items){regions=items;const ids=new Set(items.map(r=>r.id));for(const s of states.values())if(!ids.has(s.id)){drop(s);states.delete(s.id)}pump()},update(next){view=next;pump()},snapshot,retry(){for(const s of states.values())if(s.phase==='error'){s.phase='idle';s.failedAt=0;s.error=''}pump()},forEachReady(callback){for(const s of states.values())if(s.resource)callback(s.resource,regions.find(r=>r.id===s.id))},dispose(){dead=true;for(const s of states.values())drop(s);states.clear()}};
}

