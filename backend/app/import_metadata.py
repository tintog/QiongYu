"""Metadata suggestions are declarations, never independent source certification."""
import re
from datetime import datetime, timedelta

def metadata(ds, filename):
    attrs=ds.attrs
    original=str(attrs.get('source_file', filename))
    source=str(attrs.get('source','未声明'))
    label=str(attrs.get('data_product',attrs.get('original_directory_label','')))
    if not label:
        if 'CRA40LAND' in original.upper() or 'CRALAND' in source.upper():label='CRALand'
        elif 'ART_ATM' in original.upper() or 'ART_ATM' in source.upper():label='ART_ATM'
        else:label=filename.split('_')[0] if not filename.startswith('OBS_') else '未识别产品'
    version=str(attrs.get('product_version',attrs.get('version','')))
    if not version:
        match=re.search(r'_V(\d+(?:[._]\d+)+)',original,re.I)
        if match:version='V'+match[1].replace('_','.')
    return {'dataProduct':label,'productVersion':version or '未声明',
            'institution':str(attrs.get('institution','未核实')),
            'spatialProcessing':str(attrs.get('spatial_processing',attrs.get('note','未声明'))),
            'originalFile':original}

def group(names):
    names=set(names)
    surface=bool(names & {'T2M','Q2M','U10','V10','MSL','TP'})
    upper=bool(names & {'Z500','Q700','T850','U850','V850'})
    if upper and names <= {'MSL','Z500','Q700','T850','U850','V850'} and 'MSL' in names:return '高空分析及气压'
    return '地面与高空' if surface and upper else '高空分析' if upper else '地面分析'

def summarize(value):
    files=[f for f in value.get('files',[]) if f.get('status')=='valid']
    if not files:return {}
    products=sorted({f.get('dataProduct','未识别产品') for f in files})
    versions=sorted({f.get('productVersion','未声明') for f in files})
    institutions=sorted({f.get('institution','未核实') for f in files})
    sources=sorted({f.get('fileSource','未声明') for f in files})
    names=sorted({name for f in files for name in f.get('units',{})})
    product=' / '.join(products)
    version=' / '.join(versions)
    institution=' / '.join(institutions)
    ref=value['product']=='obs'
    kind=group(names) if ref else ('确定性预报' if value['product']=='DF' else '集合预报')
    if ref:
        times=sorted({f['validTime'] for f in files})
        start,end=times[0][:10].replace('-',''),times[-1][:10].replace('-','')
        date=start if start==end else start+'—'+end
        reference_types={f.get('referenceType') for f in files}
        if reference_types=={'observation'}:kind=kind.replace('分析','观测')
    else:
        date=files[0]['cycle']+' UTC'
        init=datetime.strptime(files[0]['cycle'],'%Y%m%d%H')
        times=sorted({(init+timedelta(hours=f['lead'])).isoformat() for f in files})
    return {'dataProduct':product,'productVersion':version,'institution':institution,'elementGroup':kind,
            'suggestedName':f'{product} · {kind} · {date}'[:120],
            'suggestedSource':(' / '.join(sources))[:240],
            'suggestedModel':version[:120], 'validTimes':times,'variableNames':names,
            'grid':files[0]['gridInfo'],'members':files[0].get('members',[]),
            'fileCount':len(files), 'referenceType':files[0].get('referenceType'),
            'spatialProcessing':sorted({f.get('spatialProcessing','未声明') for f in files}),
            'sourceVerified':False}
