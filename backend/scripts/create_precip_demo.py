"""Create labelled synthetic 6-hour rainfall references from 2026092800."""
from pathlib import Path
from datetime import datetime,timedelta
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import xarray as xr
from app import dataset_manager as dm,qiongyu_data as qd

det=dm.resolve('builtin-DF-20260928')
root=qd.PROJECT_ROOT/'data'/'simulated_precip_20260928'
root.mkdir(parents=True,exist_ok=True)
rng=np.random.default_rng(20260928)
paths=[]
for lead in det.leads:
    f,x,y=qd.read_china_field(det.path_for('SURFACE',lead),'TP',stride=1)
    shifted=np.roll(f,shift=(1,-2),axis=(0,1)).copy()
    shifted[:1,:]=f[:1,:];shifted[:,-2:]=f[:,-2:]
    smooth=(np.sin(np.arange(len(y))[:,None]/12+lead/24)+np.cos(np.arange(len(x))[None,:]/16))/2
    o=np.maximum(0,shifted*(.8+.25*smooth)+rng.gamma(1.4,.35,f.shape))
    o[(shifted<.1)&(rng.random(f.shape)<.82)]=0
    end=datetime.strptime(det.cycle,'%Y%m%d%H')+timedelta(hours=lead)
    start=end-timedelta(hours=6)
    ds=xr.Dataset({'TP':(('time','lat','lon'),o[None].astype('float32'),{'units':'mm/6h'})},coords={'time':[np.datetime64(end)],'lat':y,'lon':x},attrs={'product_type':'simulated','time_zone':'UTC','source':'由2026092800确定性预报进行空间位移、强度调整与随机扰动生成；非真实观测','data_product':'模拟6小时降水实况（演示）','product_version':'demo-v1','accumulation_start':start.isoformat(),'accumulation_end':end.isoformat(),'note':'随机种子20260928；仅用于评分流程演示'})
    path=root/f'OBS_ANALYSIS_{end:%Y%m%d%H}.nc'
    ds.to_netcdf(path,engine='h5netcdf');ds.close();paths.append(path)
existing=next((b for b in dm.catalog()['batches'] if b.get('synthetic') and b.get('model')=='precip-demo-20260928-v1'),None)
if existing:result=existing
else:
    value=dm.create_job('obs','0928模拟降水实况 · 6小时累计','模拟数据，非真实观测；从0928预报扰动生成','precip-demo-20260928-v1',len(paths))
    for path in paths:
        import shutil
        target=dm.job_path(value['id'])/'files'/path.name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target)
        dm.record_file(value['id'],path.name,path.stat().st_size)
    result=dm.finalize(value['id'])
    if result['status']!='ready':raise RuntimeError(result['errors'])
print('Demo reference ID:',result['id'],'files:',len(paths),'synthetic:',result.get('synthetic'))
