import * as C from 'cesium'
import {createRegionalBuildingManager} from './regionalBuildings.js'
const escape=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))
export function createCesiumRegionalBuildings(viewer,{getQuality,onChange}){
 const credits=new Map()
 const applyGround=(tileset,region)=>{if(region?.grounding?.mode!=='terrain-center')return;const [lon,lat]=region.center,c=C.Cartographic.fromDegrees(lon,lat);const h=viewer.scene.globe.getHeight(c);const offset=(Number.isFinite(h)?h:0)-region.grounding.baseElevation;const a=C.Cartesian3.fromDegrees(lon,lat,0),b=C.Cartesian3.fromDegrees(lon,lat,offset);tileset.modelMatrix=C.Matrix4.fromTranslation(C.Cartesian3.subtract(b,a,new C.Cartesian3()))}
 const manager=createRegionalBuildingManager({
  load:region=>C.Cesium3DTileset.fromUrl(region.tilesetUrl,{maximumScreenSpaceError:{fast:16,balanced:8,fine:3}[getQuality()],cacheBytes:96*1024*1024,maximumCacheOverflowBytes:32*1024*1024,skipLevelOfDetail:true}),
  attach(tileset,region){viewer.scene.primitives.add(tileset);applyGround(tileset,region);const credit=new C.Credit(`<a href="${escape(region.credit.url)}" target="_blank" rel="noopener">${escape(region.credit.text)}</a> · ${escape(region.credit.license)}`,true);credits.set(tileset,credit);viewer.cesiumWidget.creditDisplay.addStaticCredit(credit);viewer.scene.requestRender()},
  detach(tileset){if(viewer.isDestroyed()){credits.delete(tileset);if(!tileset.isDestroyed())tileset.destroy();return}const credit=credits.get(tileset);if(credit){viewer.cesiumWidget.creditDisplay.removeStaticCredit(credit);credits.delete(tileset)}if(!tileset.isDestroyed()){if(!viewer.scene.primitives.remove(tileset))tileset.destroy()}viewer.scene.requestRender()},onChange,
 })
 return {...manager,applyQuality(){manager.forEachReady(t=>{t.maximumScreenSpaceError={fast:16,balanced:8,fine:3}[getQuality()]});viewer.scene.requestRender()},align(){manager.forEachReady(applyGround)}}
}
export function captureBuildingView(viewer,enabled,suspended){
 const height=viewer.camera.positionCartographic.height,canvas=viewer.scene.canvas,ray=viewer.camera.getPickRay(new C.Cartesian2(canvas.clientWidth/2,canvas.clientHeight/2));const hit=ray&&viewer.scene.globe.pick(ray,viewer.scene);const centerCart=hit?C.Cartographic.fromCartesian(hit):viewer.camera.positionCartographic;const center=[C.Math.toDegrees(centerCart.longitude),C.Math.toDegrees(centerCart.latitude)],rect=viewer.camera.computeViewRectangle();
 let bounds=rect?[C.Math.toDegrees(rect.west),C.Math.toDegrees(rect.south),C.Math.toDegrees(rect.east),C.Math.toDegrees(rect.north)]:null;
 const radius=Math.max(.03,Math.max(height,0)/111000*5),lonRadius=radius/Math.max(.2,Math.cos(centerCart.latitude));const local=[center[0]-lonRadius,center[1]-radius,center[0]+lonRadius,center[1]+radius];
 if(!bounds||bounds[0]>bounds[2])bounds=local;else bounds=[Math.max(bounds[0],local[0]),Math.max(bounds[1],local[1]),Math.min(bounds[2],local[2]),Math.min(bounds[3],local[3])];
 return {enabled,suspended,height,center,bounds};
}

