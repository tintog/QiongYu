import assert from 'node:assert/strict'
import { rasterize } from '../src/scene/weatherTexture.js'
let written
globalThis.document={createElement:()=>({getContext:()=>({createImageData:(w,h)=>({data:new Uint8ClampedArray(w*h*4)}),putImageData:p=>{written=p.data}})})}
const points=[[100,30,0],[101,30,10],[100,31,20],[101,31,30],[NaN,31,5]]
const result=rasterize(points,['#001122','#ddeeff'],0,30,true)
assert.deepEqual(result.bounds,[99.5,29.5,101.5,31.5])
assert.equal(result.image.width,2);assert.equal(result.image.height,2)
assert.deepEqual([...written.slice(0,3)],[221,238,255]) // Northern row first.
assert.equal(written[11],0) // Zero rainfall in southern row remains transparent.
assert.equal(written[15],205)
assert.throws(()=>rasterize([],['#ffffff'],0,1),/有效格点/)
const smoothResult=rasterize(points,['#001122','#ddeeff'],0,30,true,true)
assert.equal(smoothResult.image.width,8);assert.equal(smoothResult.image.height,8)
assert.equal(written[3],Math.round(45+155*Math.sqrt(20/30)))
const sparse=rasterize([[100,30,10],[101,31,20]],['#001122','#ddeeff'],0,30,false,true)
assert.equal(sparse.image.width,8)
assert.equal(written[(3*8+3)*4+3],0) // Interpolation must not fabricate missing grid values.
console.log('PASS: north-up grid orientation, cell bounds, missing data and dry-cell transparency')
