// Preserve grid cell centres and north-up orientation when projecting onto the globe.
export function rasterize(points, palette, minimum, maximum, hideDry = false, smooth = false) {
  const valid = points.filter(p => p.length >= 3 && p.every(Number.isFinite))
  if (!valid.length) throw new Error('当前图层没有有效格点')
  const xs = [...new Set(valid.map(p => p[0]))].sort((a,b) => a-b)
  const ys = [...new Set(valid.map(p => p[1]))].sort((a,b) => b-a)
  const xi = new Map(xs.map((v,i) => [v,i])), yi = new Map(ys.map((v,i) => [v,i]))
  const canvas = document.createElement('canvas')
  const factor = smooth ? 4 : 1
  canvas.width = xs.length*factor; canvas.height = ys.length*factor
  const ctx = canvas.getContext('2d'), pixels = ctx.createImageData(canvas.width,canvas.height)
  const colors = palette.map(hex => [1,3,5].map(i => parseInt(hex.slice(i,i+2),16)))
  const grid = new Float64Array(xs.length*ys.length).fill(NaN)
  for (const [x,y,v] of valid) {
    grid[yi.get(y)*xs.length+xi.get(x)] = v
  }
  for(let row=0;row<canvas.height;row++)for(let col=0;col<canvas.width;col++) {
    const x=Math.max(0,Math.min(xs.length-1,(col+.5)/factor-.5))
    const y=Math.max(0,Math.min(ys.length-1,(row+.5)/factor-.5))
    const x0=Math.floor(x),y0=Math.floor(y),x1=Math.min(x0+1,xs.length-1),y1=Math.min(y0+1,ys.length-1)
    const samples=[grid[y0*xs.length+x0],grid[y0*xs.length+x1],grid[y1*xs.length+x0],grid[y1*xs.length+x1]]
    const weights=[(1-x+x0)*(1-y+y0),(x-x0)*(1-y+y0),(1-x+x0)*(y-y0),(x-x0)*(y-y0)]
    let v=0,missing=false
    for(let i=0;i<4;i++){if(weights[i]>1e-10){if(!Number.isFinite(samples[i])){missing=true;break}v+=samples[i]*weights[i]}}
    if(missing)continue
    const ratio = Math.max(0,Math.min(1,(v-minimum)/(maximum-minimum || 1)))
    const position=ratio*(colors.length-1),index=Math.floor(position),fraction=position-index
    const color = smooth ? colors[index].map((c,i)=>Math.round(c*(1-fraction)+colors[Math.min(index+1,colors.length-1)][i]*fraction)) : colors[Math.min(colors.length-1, Math.floor(ratio*colors.length))]
    const alpha=hideDry?(v<.1?0:smooth?Math.round(45+155*Math.sqrt(ratio)):205):205
    pixels.data.set([...color,alpha],(row*canvas.width+col)*4)
  }
  ctx.putImageData(pixels,0,0)
  const dx = (xs[1]-xs[0] || .25)/2, dy = (ys[0]-ys[1] || .25)/2
  return { image: canvas, bounds: [xs[0]-dx,ys.at(-1)-dy,xs.at(-1)+dx,ys[0]+dy] }
}
