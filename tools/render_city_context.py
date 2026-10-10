from PIL import Image,ImageDraw
from pathlib import Path
import json
p=Path('frontend/public/buildings/lujiazui');data=json.loads((p/'context.osm.json').read_text(encoding='utf-8'))
# WGS84 north-up local context. Colors are cartographic symbols, not satellite imagery.
b=(121.484,31.222,121.520,31.250);size=2048
im=Image.new('RGB',(size,size),(54,75,80));d=ImageDraw.Draw(im)
def xy(v):return ((v['lon']-b[0])/(b[2]-b[0])*size,(b[3]-v['lat'])/(b[3]-b[1])*size)
for e in data['elements']:
    if e.get('tags',{}).get('natural')=='water' and len(e.get('geometry',[]))>3:d.polygon([xy(v) for v in e['geometry']],fill=(30,83,108))
for e in data['elements']:
    t=e.get('tags',{});g=e.get('geometry',[])
    if 'highway' not in t or len(g)<2:continue
    width={'motorway':11,'trunk':10,'primary':9,'secondary':7,'tertiary':6,'residential':4,'service':3,'footway':2,'path':1}.get(t['highway'],3)
    points=[xy(v) for v in g];d.line(points,fill=(30,47,58),width=width+4);d.line(points,fill=(138,157,159),width=width)
im.save(p/'context.png',optimize=True);print('context.png',len(data['elements']), (p/'context.png').stat().st_size)
