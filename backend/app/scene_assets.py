"""Same-origin delivery of fixed public map/model sources; never forwards session credentials."""
import re
import requests
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool

router = APIRouter()
SOURCES = {
    'imagery': 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/',
    'shequ': 'https://data.mars3d.cn/3dtiles/qx-shequ/',
    'simiao': 'https://data.mars3d.cn/3dtiles/qx-simiao/',
}

@router.get('/scene-assets/{source}/{asset_path:path}')
async def public_scene_asset(source: str, asset_path: str):
    if source not in SOURCES or '..' in asset_path or not re.fullmatch(r'[-a-zA-Z0-9_/.]*', asset_path):
        raise HTTPException(400, 'Invalid scene asset')
    if source == 'imagery' and asset_path and not re.fullmatch(r'tile/\d+/\d+/\d+', asset_path):
        raise HTTPException(400, 'Invalid imagery tile')
    if source != 'imagery' and not asset_path.endswith(('.json', '.b3dm', '.glb', '.gltf', '.png', '.jpg', '.jpeg', '.bin')):
        raise HTTPException(400, 'Invalid model asset')
    url = SOURCES[source] + asset_path + ('?f=json' if source == 'imagery' and not asset_path else '')
    def download():
        try:
            with requests.get(url, timeout=(8, 25), allow_redirects=False, stream=True) as upstream:
                if upstream.status_code != 200:
                    return Response(status_code=502, content='Public scene source unavailable')
                content = bytearray()
                for chunk in upstream.iter_content(65536):
                    content.extend(chunk)
                    if len(content) > 32 * 1024 * 1024:
                        return Response(status_code=502, content='Scene asset exceeds size limit')
                return Response(bytes(content), media_type=upstream.headers.get('Content-Type', 'application/octet-stream'), headers={'Cache-Control':'public, max-age=3600'})
        except requests.RequestException:
            return Response(status_code=502, content='Public scene source unavailable')
    return await run_in_threadpool(download)
