import json,urllib.request,urllib.parse
from pathlib import Path
p=Path('frontend/public/buildings/lujiazui')
q='[out:json][timeout:60];(way["highway"](31.222,121.484,31.250,121.520);way["natural"="water"](31.222,121.484,31.250,121.520););out body geom;'
req=urllib.request.Request('https://overpass.kumi.systems/api/interpreter',data=urllib.parse.urlencode({'data':q}).encode(),headers={'User-Agent':'QiongyuCompetitionDemo/1.0'})
with urllib.request.urlopen(req,timeout=90) as r:data=json.load(r)
(p/'context.osm.json').write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8');print(len(data['elements']))

