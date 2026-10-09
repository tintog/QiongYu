import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { cpSync, mkdirSync, existsSync, readFileSync } from 'node:fs'
import { resolve, extname } from 'node:path'

// Serve Cesium workers and static resources locally in development and production.
function cesiumAssets() {
  const source = resolve('node_modules/cesium/Build/Cesium')
  return {
    name: 'local-cesium-assets',
    configureServer(server) {
      server.middlewares.use('/cesium', (req, res, next) => {
        let path
        try { path = resolve(source, '.' + decodeURIComponent((req.url || '/').split('?')[0])) } catch { return next() }
        if (!path.startsWith(source + '/') && !path.startsWith(source + '\\')) return next()
        if (!existsSync(path) || !extname(path)) return next()
        const types = { '.js':'application/javascript', '.json':'application/json', '.css':'text/css', '.png':'image/png', '.jpg':'image/jpeg', '.svg':'image/svg+xml', '.wasm':'application/wasm' }
        res.setHeader('Content-Type', types[extname(path)] || 'application/octet-stream')
        res.end(readFileSync(path))
      })
    },
    writeBundle(options) {
      const target = resolve(options.dir || 'dist', 'cesium')
      mkdirSync(target, { recursive:true })
      for (const name of ['Workers','Assets','Widgets','ThirdParty']) cpSync(resolve(source,name), resolve(target,name), {recursive:true})
    },
  }
}


// Fixed public sources only: no user-supplied proxy targets or credential forwarding.
function sceneAssets(){const cache=new Map();let cacheBytes=0;return {name:'public-scene-assets',configureServer(server){server.middlewares.use('/scene-assets',async(req,res,next)=>{const path=(req.url||'').split('?')[0];const match=path.match(/^\/(imagery|shequ|simiao)\/(.*)$/);if(!match)return next();const [,kind,tail]=match;if(tail.includes('..')||!/^[-a-zA-Z0-9_/.]*$/.test(tail)){res.statusCode=400;return res.end('Invalid asset path')}
 const bases={imagery:'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/',shequ:'https://data.mars3d.cn/3dtiles/qx-shequ/',simiao:'https://data.mars3d.cn/3dtiles/qx-simiao/'};
 if(kind==='imagery'&&tail!==''&&!/^tile\/\d+\/\d+\/\d+$/.test(tail)){res.statusCode=400;return res.end('Invalid imagery path')}
 const url=bases[kind]+tail+(kind==='imagery'&&!tail?'?f=json':'');const saved=cache.get(url);if(saved){cache.delete(url);cache.set(url,saved);res.setHeader('Content-Type',saved.type);res.setHeader('Cache-Control','public,max-age=3600');return res.end(saved.body)}
 for(let attempt=0;attempt<2;attempt++){try{const upstream=await fetch(url,{signal:AbortSignal.timeout(20000),redirect:'error'});if(upstream.status>=500&&attempt===0)continue;const body=Buffer.from(await upstream.arrayBuffer());res.statusCode=upstream.status;const type=upstream.headers.get('content-type')||'application/octet-stream';res.setHeader('Content-Type',type);if(upstream.ok){res.setHeader('Cache-Control','public,max-age=3600');if(body.length<=16*1024*1024){cache.set(url,{body,type});cacheBytes+=body.length;while(cacheBytes>96*1024*1024){const key=cache.keys().next().value;cacheBytes-=cache.get(key).body.length;cache.delete(key)}}}return res.end(body)}catch(e){if(attempt===1){res.statusCode=502;return res.end('Public scene source unavailable')}}}

 })}}}

export default defineConfig({
  plugins: [vue(), cesiumAssets(), sceneAssets()],
  define: { CESIUM_BASE_URL: JSON.stringify('/cesium/') },
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8001',
    },
  },
})
