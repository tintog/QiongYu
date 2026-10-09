"""UTC-matched, explicitly labelled analysis-reference import and verification."""
import hashlib
import json
from datetime import datetime, timedelta
import numpy as np
from app import qiongyu_data as qd
from app import import_metadata as im

SUPPORTED={'TP','T2M','T850','Q2M','Q700','MSL','Z500','U10','V10','U850','V850'}

def normalize(a,var,unit):
    unit=str(unit).lower().replace(' ','').replace('**','').replace('^','')
    if var=='TP':
        if unit in {'mm','mm/6h'}:return a
        if unit=='m':return a*1000
        raise ValueError('降水参考单位须为mm、mm/6h或m')
    if var in {'T2M','T850'}:
        if unit in {'k','kelvin'}: return a-273.15
        if unit in {'degc','℃','celsius','degrees_celsius'}: return a
        raise ValueError('温度单位不支持')
    if var in {'Q2M','Q700','MSL'}:return qd.normalize_display_units(a,var,unit)
    accepted={'gpm','m'} if var=='Z500' else {'m/s','ms-1'}
    if unit not in accepted:raise ValueError(f'{var}单位不支持：{unit}')
    return a

def inspect(path):
    with qd._open_dataset(path) as ds:
        if ds.attrs.get('product_type') not in {'analysis','observation','simulated'} or ds.attrs.get('time_zone')!='UTC':
            raise ValueError('参考文件必须明确声明analysis/observation及time_zone=UTC；不接受预报冒充实况')
        if ds.sizes.get('time')!=1 or 'dtime' in ds.dims or 'member' in ds.dims:
            raise ValueError('每个参考文件仅一个有效时间，不含预报时效或集合成员')
        stamp=np.asarray(ds.time.values).astype('datetime64[ns]')[0]
        if np.isnat(stamp):raise ValueError('参考时间为空')
        cycle=np.datetime_as_string(stamp,unit='h').replace('-','').replace('T','')
        if path.name!=f'OBS_ANALYSIS_{cycle}.nc':raise ValueError('文件名与UTC有效时间不一致')
        coords={}
        for dim,low,high in [('lon',70,140),('lat',12,56)]:
            a=np.asarray(ds[dim].values,dtype=float)
            if ds[dim].dims!=(dim,) or len(a)<2 or not np.isfinite(a).all() or not np.allclose(np.diff(a),.25) or a[0]>low or a[-1]<high:
                raise ValueError('参考数据需覆盖中国区域的升序0.25度lon/lat网格')
            coords[dim]=a.tolist()
        variables=sorted(set(ds.data_vars)&SUPPORTED)
        if not variables:raise ValueError('没有支持的参考要素')
        if 'TP' in variables:
            start=np.datetime64(ds.attrs.get('accumulation_start','NaT'),'ns')
            end=np.datetime64(ds.attrs.get('accumulation_end','NaT'),'ns')
            if np.isnat(start) or np.isnat(end) or end!=stamp or end-start!=np.timedelta64(6,'h'):
                raise ValueError('降水必须明确声明与有效时间对应的6小时累计起止时间')
        units={}
        for var in variables:
            if ds[var].dims!=('time','lat','lon'):raise ValueError('参考变量维度需为time/lat/lon')
            units[var]=ds[var].attrs.get('units','')
            a=normalize(ds[var].values,var,units[var])
            if var=='TP' and np.any(a[np.isfinite(a)]<0):raise ValueError('降水不能为负值')
            if np.isinf(a).any() or not np.isfinite(a).any():raise ValueError(f'{var}无有效数值或存在无穷值')
        return {'kind':'ANALYSIS','lead':0,'cycle':cycle,'validTime':str(stamp),
                'units':units,'variables':variables,'members':[],
                'referenceType':ds.attrs['product_type'],'accumulationHours':6 if 'TP' in variables else None,
                'synthetic':ds.attrs['product_type']=='simulated',
                'grid':hashlib.sha256(json.dumps(coords,sort_keys=True).encode()).hexdigest(),
                'gridInfo':{'lonCount':len(coords['lon']),'latCount':len(coords['lat']),'resolution':'0.25°'},
                'fileSource':str(ds.attrs.get('source','未声明')), **im.metadata(ds,path.name)}

def finalize(value):
    files=value['files'];valid=[f for f in files if f['status']=='valid']
    errors=[f"{f['name']}：{f['error']}" for f in files if f['status']!='valid']
    if len(files)!=value['expectedFiles']:errors.append('文件数量不符')
    if not valid or len({f['grid'] for f in valid})!=1:errors.append('参考网格不一致或无有效文件')
    if len({f['validTime'] for f in valid})!=len(valid):errors.append('参考有效时间重复，请将地面和高空分批导入')
    if len({tuple(f['variables']) for f in valid})!=1:errors.append('批次内要素不一致')
    if len({f['referenceType'] for f in valid})!=1:errors.append('分析场与观测不能混为一批')
    value.update(errors=errors,status='failed' if errors else 'ready',warnings=['模拟实况仅用于流程演示，不能证明模型精度' if valid and valid[0].get('synthetic') else '参考来源需独立核实；降水按6小时累计口径检验'],canActivate=not errors)
    if not errors:
        value.update(cycle=min(f['cycle'] for f in valid),leads=[0],members=[],grid=valid[0]['gridInfo'],
                     validTimes=sorted(f['validTime'] for f in valid),observationVariables=valid[0]['variables'],referenceType=valid[0]['referenceType'],synthetic=valid[0].get('synthetic',False))
    return value

def stats(f,o):
    delta=f-o
    corr=float(np.corrcoef(f,o)[0,1]) if len(f)>1 and np.std(f)>0 and np.std(o)>0 else None
    return {'mae':float(np.mean(np.abs(delta))),'rmse':float(np.sqrt(np.mean(delta**2))),
            'bias':float(np.mean(delta)),'corr':corr,'validPoints':len(f)}


def reference_options(forecast_id=None):
    from app import dataset_manager as dm
    det=dm.resolve(forecast_id) if forecast_id else qd.resolve_latest(qd.DATA_ROOT)[0]
    if not det:return {'references':[],'excluded':[],'message':'没有可用预报'}
    if det.product!='DF':raise ValueError('当前仅检验确定性预报')
    times={str(np.datetime64(datetime.strptime(det.cycle,'%Y%m%d%H')+timedelta(hours=h),'ns')):h for h in det.leads}
    references=[];excluded=[]
    for row in dm.catalog()['batches']:
        if row['product']!='obs':continue
        value=dm.job(row['id'])
        matched=[{'validTime':str(np.datetime64(f['validTime'],'ns')),'leadHour':times[str(np.datetime64(f['validTime'],'ns'))]} for f in value['files'] if str(np.datetime64(f['validTime'],'ns')) in times]
        common=row['variables']
        reason='无共同要素' if not common else '有效时间不匹配' if not matched else ''
        if not reason:
            # Compare coordinates without loading forecast values; calculation checks finite samples separately.
            with qd._open_dataset(dm.job_path(row['id'])/'files'/value['files'][0]['name']) as obs_ds:
                matching_vars=[]
                for spec in common:
                    path=det.path_for(spec['file'],matched[0]['leadHour'])
                    if not path:continue
                    with qd._open_dataset(path) as fc:
                        x=fc.lon.values;y=fc.lat.values
                        x=x[(x>=70)&(x<=140)];y=y[(y>=12)&(y<=56)]
                        if np.array_equal(x,obs_ds.lon.values) and np.array_equal(y,obs_ds.lat.values):matching_vars.append(spec)
                common=matching_vars
            if not common:reason='网格或要素配套文件不匹配'
        if reason:excluded.append({'id':row['id'],'name':row['name'],'reason':reason});continue
        matched.sort(key=lambda x:x['leadHour'])
        references.append({**row,'variables':common,'matchedTimes':matched,'matchedCount':len(matched)})
    return {'cycle':det.cycle,'references':references,'excluded':excluded,
            'message':'候选配对按有效时间、要素及网格筛选；计算时复核共同有效格点'}

def verification(variable='tp',reference_id=None,forecast_id=None):
    from app import dataset_manager as dm
    det=dm.resolve(forecast_id) if forecast_id else qd.resolve_latest(qd.DATA_ROOT)[0]
    unavailable={'available':False,'cycle':det.cycle if det else '', 'message':'无匹配参考数据；历史预报不作为实况。'}
    if not det:return unavailable
    reference_id=reference_id or dm.selection().get('obs')
    if not reference_id:return unavailable
    value=dm.job(reference_id)
    if value['product']!='obs' or value['status']!='ready':raise ValueError('参考批次不可用')
    spec=qd.VARIABLE_MAP.get(variable)
    if not spec:return {**unavailable,'message':'本批参考场不含降水；请选择气温、气压、比湿、位势高度或风速。'}
    if det.product!='DF':raise ValueError('当前仅检验确定性预报')
    names=[spec['u'],spec['v']] if 'u' in spec else [spec['var']]
    if not set(names)<=set(value['observationVariables']):return {**unavailable,'message':'所选参考批次不含该要素。'}
    score=lambda f,o: {**stats(f,o),**({'scores':precip_scores(f,o)} if variable=='tp' else {})}
    by_time={str(np.datetime64(f['validTime'],'ns')):f for f in value['files']}
    series=[];skipped=[];all_f=[];all_o=[]
    for lead in det.leads:
        stamp=str(np.datetime64(datetime.strptime(det.cycle,'%Y%m%d%H')+timedelta(hours=lead),'ns'))
        item=by_time.get(stamp)
        if not item:continue
        path=det.path_for(spec['file'],lead)
        if not path:continue
        with qd._open_dataset(dm.job_path(reference_id)/'files'/item['name']) as ds:
            forecast=[];observed=[]
            mismatch=False
            for var in names:
                f,x,y=qd.read_china_field(path,var,stride=1)
                ob=ds[var].isel(time=0).sel(lon=slice(70,140),lat=slice(12,56))
                if not np.array_equal(x,ob.lon.values) or not np.array_equal(y,ob.lat.values):mismatch=True;break
                forecast.append(f);observed.append(normalize(ob.values,var,ob.attrs.get('units','')))
            if mismatch:skipped.append({'leadHour':lead,'reason':'网格不一致，不自动插值'});continue
            f=np.hypot(*forecast) if len(names)==2 else forecast[0]
            o=np.hypot(*observed) if len(names)==2 else observed[0]
            mask=np.isfinite(f)&np.isfinite(o)
            if not mask.any():skipped.append({'leadHour':lead,'reason':'无共同有效格点'});continue
            f,o=f[mask].astype(float),o[mask].astype(float)
            series.append({'leadHour':lead,'validTime':stamp,'day':lead/24,**score(f,o)})
            all_f.append(f);all_o.append(o)
    if not series:return {**unavailable,'message':'没有相同UTC有效时间及网格的预报—参考配对。','skipped':skipped}
    segments=[]
    for key,label,low,high in [('day1-3','1—3天',0,72),('day4-10','4—10天',72,240),('day11-15','11—15天',240,360)]:
        indices=[i for i,r in enumerate(series) if low<r['leadHour']<=high]
        if indices:
            segments.append({'key':key,'label':label,'matchedTimeCount':len(indices),**score(np.concatenate([all_f[i] for i in indices]),np.concatenate([all_o[i] for i in indices]))})
        else:segments.append({'key':key,'label':label,'matchedTimeCount':0,'validPoints':0,'mae':None,'rmse':None,'bias':None,'corr':None})
    return {'available':True,'cycle':det.cycle,'variable':spec['name'],'unit':'mm/6h' if variable=='tp' else spec['unit'],'segments':segments,
            'referenceName':value['name'],'referenceSource':value['source'],'referenceType':value['referenceType'],
            'referenceNote':'中国区域0.25度逐格点等权统计；NaN共同掩膜；仅统计匹配时刻，不代表竞赛官方评分。',
            'synthetic':value.get('synthetic',False),'accumulationHours':6 if variable=='tp' else None,
            'overall':score(np.concatenate(all_f),np.concatenate(all_o)),'series':series,'skipped':skipped}


def precip_scores(f,o):
    rows=[]
    for threshold in (0.1,1,5,10,20):
        fp=f>=threshold;op=o>=threshold
        hit=int(np.count_nonzero(fp&op));false=int(np.count_nonzero(fp&~op));miss=int(np.count_nonzero(~fp&op));correct=int(np.count_nonzero(~fp&~op))
        ratio=lambda a,b:float(a/b) if b else None
        rows.append({'threshold':threshold,'TS':ratio(hit,hit+false+miss),'POD':ratio(hit,hit+miss),'FAR':ratio(false,hit+false),'BIAS':ratio(hit+false,hit+miss),'hits':hit,'falseAlarms':false,'misses':miss,'correctNegatives':correct})
    return rows
