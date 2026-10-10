import json, urllib.request, urllib.parse
from pathlib import Path
q='[out:json][timeout:60];(way["building"](31.225,121.488,31.247,121.515);way["building:part"](31.225,121.488,31.247,121.515););out body geom;'
req=urllib.request.Request('https://overpass-api.de/api/interpreter',data=urllib.parse.urlencode({'data':q}).encode(),headers={'User-Agent':'QiongyuCompetitionDemo/1.0'})
with urllib.request.urlopen(req,timeout=90) as r: data=json.load(r)
p=Path('frontend/public/buildings/lujiazui/source.osm.json');p.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
e=data['elements']; print('buildings',len(e),'height',sum('height' in x.get('tags',{}) for x in e),'levels',sum('building:levels' in x.get('tags',{}) for x in e))
