// Exercise the actual Vue setup logic without a browser or chart renderer.
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript } from '@vue/compiler-sfc'
import * as Vue from 'vue'

const source = readFileSync(new URL('../src/components/PointForecastPanel.vue', import.meta.url), 'utf8')
const { descriptor } = parse(source)
let code = compileScript(descriptor, { id: 'point-linkage-test' }).content
code = code.replace(/import\s*\{([^}]+)\}\s*from 'vue'/g, (_, names) => `const {${names}} = Vue`)
  .replace(/import AppIcon from '[^']+'/g, 'const AppIcon = {}')
  .replace(/import api from '[^']+'/g, '')
  .replace(/import\s*\{([^}]+)\}\s*from '..\/chartKit'/g, (_, names) => `const {${names}} = chartKit`)
  .replace('export default', 'return')
const requests = []
const pending = []
let deferRequests = false
const api = {
  provinces: async () => [], variables: async () => [],
  point: (lon, lat, variable) => {
    requests.push({ lon, lat, variable })
    const result = { requested: { lon, lat }, series: [], daily: [], summary: {}, variable: { kind: 'precipitation' } }
    if (deferRequests) return new Promise(resolve => pending.push(() => resolve(result)))
    return Promise.resolve(result)
  },
}
const chartKit = Object.fromEntries(['mountChart', 'disposeChart', 'leadCurveOption', 'compareBarOption', 'donutOption', 'geoOption', 'formatShort', 'num'].map(name => [name, () => null]))
const component = new Function('Vue', 'api', 'chartKit', code)(Vue, api, chartKit)
component.render = () => null
globalThis.window = { addEventListener() {}, removeEventListener() {} }
const renderer = Vue.createRenderer({
  createElement: () => ({}), createText: () => ({}), createComment: () => ({}),
  setText() {}, setElementText() {}, patchProp() {}, insert() {}, remove() {},
  parentNode: () => null, nextSibling: () => null,
})
const root = {}
const settle = async () => { await Vue.nextTick(); await new Promise(resolve => setImmediate(resolve)); await Vue.nextTick() }
renderer.render(Vue.h(component, { selectedPoint: { lon: 116.41, lat: 39.9 } }), root)
await settle()
assert.deepEqual(requests.at(-1), { lon: 116.41, lat: 39.9, variable: 'tp' })
renderer.render(Vue.h(component, { selectedPoint: { lon: 104.07, lat: 30.67 } }), root)
await settle()
assert.deepEqual(requests.at(-1), { lon: 104.07, lat: 30.67, variable: 'tp' })
const exposed = root._vnode.component.exposed
await exposed.applyPoint({ lon: 113.28, lat: 23.13 })
assert.deepEqual(requests.at(-1), { lon: 113.28, lat: 23.13, variable: 'tp' })
const count = requests.length
exposed.applyPoint({ lon: 'invalid', lat: 30 })
assert.equal(requests.length, count)
// Resolve the newest request first and ensure the older response cannot replace it.
deferRequests = true
const oldRequest = exposed.applyPoint({ lon: 100, lat: 25 })
const newRequest = exposed.applyPoint({ lon: 121.47, lat: 31.23 })
pending[1]()
await newRequest
pending[0]()
await oldRequest
const state = root._vnode.component.setupState
assert.deepEqual(state.point.requested, { lon: 121.47, lat: 31.23 })
renderer.render(null, root)
console.log('PASS: initial selection, prop update, applyPoint, invalid coordinates, stale response protection')
