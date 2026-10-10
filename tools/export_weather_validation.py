"""Export real local weather results for independent UI validation, without login credentials."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app import qiongyu_service as svc, qiongyu_data as qd
index,_=qd.resolve_latest()
result={'info':{'initCycle':index.cycle,'modelProduct':'本地竞赛预报产品'},'variables':svc.variables(),'provinces':[{k:a[k] for k in ['name','region','lon','lat']} for a in qd.REGION_ANCHORS],'timeline':svc.timeline(),'overview':{str(h):svc.overview(h,'6h',2) for h in [24,30]},'point':svc.point_forecast(121.501,31.236,'tp'),'risk':svc.risk_warnings(2)}
out=Path(__file__).resolve().parents[1]/'frontend/tests/.weather-validation.json';out.write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8');print(json.dumps({'cycle':index.cycle,'leads':len(index.leads),'points':len(result['overview']['24']['points']),'max24':result['overview']['24']['statistics'],'pointLeads':len(result['point']['series'])}))
