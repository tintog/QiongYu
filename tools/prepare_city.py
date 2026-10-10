"""Prepare a bounded ODbL city extract. No fabricated heights hidden as observations."""
import json,re
from pathlib import Path
p=Path('frontend/public/buildings/lujiazui')
s=json.loads((p/'source.osm.json').read_text(encoding='utf-8'))
def number(v):
    text=str(v or '').strip()
    if not re.fullmatch(r'\d+(\.\d+)?\s*(m|米)?',text): return None
    return float(re.search(r'\d+(\.\d+)?',text)[0])
def inside(x,y,ring):
    c=False
    for a,b in zip(ring,ring[1:]):
        if (a[1]>y)!=(b[1]>y) and x<(b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]: c=not c
    return c
items=[]
for e in s['elements']:
    g=e.get('geometry',[]); t=e.get('tags',{})
    if len(g)<4 or g[0]!=g[-1]: continue
    ring=[[v['lon'],v['lat']] for v in g]
    if any(not(121.488<=x<=121.515 and 31.225<=y<=31.247) for x,y in ring):continue
    h=number(t.get('height')); levels=number(t.get('building:levels'))
    method='OSM height'
    if h is None:
        h=levels*3.2 if levels else 12
        method='levels × 3.2m estimate' if levels else '12m schematic fallback'
    base=number(t.get('min_height')) or (number(t.get('building:min_level')) or 0)*3.2
    if not 2<=h<=650 or base>=h:continue
    items.append(dict(id=e['id'],name=t.get('name:zh') or t.get('name') or '',height=h,minHeight=base,heightSource=method,part='building:part' in t,ring=ring))
# OSM outlines overlap their separately mapped parts. Prefer detailed parts when available.
parts=[b for b in items if b['part']]
items=[b for b in items if b['part'] or not any(inside(sum(x for x,y in a['ring'][:-1])/(len(a['ring'])-1),sum(y for x,y in a['ring'][:-1])/(len(a['ring'])-1),b['ring']) for a in parts)]
features=[dict(type='Feature',id=b['id'],properties={k:v for k,v in b.items() if k!='ring'},geometry=dict(type='Polygon',coordinates=[b['ring']])) for b in items]
(p/'buildings.geojson').write_text(json.dumps(dict(type='FeatureCollection',features=features),ensure_ascii=False,separators=(',',':')),encoding='utf-8')
counts={k:sum(b['heightSource']==k for b in items) for k in ['OSM height','levels × 3.2m estimate','12m schematic fallback']}
manifest=dict(name='上海陆家嘴',center=[121.501,31.236],bounds=[121.488,31.225,121.515,31.247],count=len(items),heights=counts,maxHeight=max(b['height'] for b in items),source='OpenStreetMap contributors',license='ODbL-1.0',sourceUrl='https://www.openstreetmap.org/copyright',extractedAt=s.get('osm3s',{}).get('timestamp_osm_base'),baseElevation=5,description='真实位置的简化建筑；层数换算和缺失高度为估算，窗格为程序化示意材质。地面统一取椭球高5m，未进行逐栋测量。')
(p/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
from PIL import Image,ImageDraw
im=Image.new('RGB',(128,128),(118,141,152));d=ImageDraw.Draw(im)
for y in [10,74]:
    for x in [7,39,71,103]:
        d.rectangle((x,y,x+21,y+43),fill=(44,76,96));d.line((x+1,y+1,x+19,y+1),fill=(165,192,204),width=2)
d.line((0,63,127,63),fill=(190,201,202),width=3);d.line((0,127,127,127),fill=(190,201,202),width=3)
im.save(p/'facade.png')
print(json.dumps(manifest,ensure_ascii=True));print([(b['name'],b['height']) for b in items if b['height']>200][:20])
