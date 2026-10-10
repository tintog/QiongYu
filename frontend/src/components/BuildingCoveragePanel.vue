<template>
  <section class="building-coverage" aria-label="全国建筑覆盖">
    <div class="coverage-title"><h4>建筑数据覆盖</h4><span>{{ regions.length }} 个区域</span></div>
    <label class="coverage-toggle"><input type="checkbox" :checked="enabled" @change="$emit('update:enabled',$event.target.checked)">随视角加载区域建筑</label>
    <p class="coverage-state" role="status">{{ message }}</p>
    <div class="coverage-counts"><span>显示 {{ state.visible || 0 }}</span><span>驻留 {{ state.loaded || 0 }}/2</span><span>加载 {{ state.loading || 0 }}</span></div>
    <p v-if="error" class="coverage-error">{{ error }}</p>
    <button v-if="state.failed" class="coverage-retry" @click="$emit('retry')">重试失败的区域</button>
    <label class="coverage-toggle"><input type="checkbox" :checked="outlines" @change="$emit('update:outlines',$event.target.checked)">显示已接入范围</label>
    <input v-model="search" class="coverage-search" placeholder="查找已接入城区" aria-label="查找建筑区域">
    <div class="coverage-list"><button v-for="region in filtered" :key="region.id" @click="$emit('locate',region)"><span>{{ region.name }}<small>{{ region.province || '已接入区域' }} · {{ region.credit.license }}</small></span><b>定位 ›</b></button></div>
    <p v-if="!filtered.length" class="coverage-note">暂无匹配的已接入区域</p>
    <p class="coverage-note">只在有数据的区域显示建筑；目录可扩展至全国各城区。当前列表不代表全国已覆盖。</p>
  </section>
</template>
<script setup>
import {ref,computed} from 'vue'
const props=defineProps({regions:{type:Array,default:()=>[]},state:{type:Object,default:()=>({})},enabled:Boolean,outlines:Boolean,message:String,error:String})
defineEmits(['update:enabled','update:outlines','locate','retry'])
const search=ref(''),filtered=computed(()=>props.regions.filter(r=>(r.name+' '+(r.province||'')).includes(search.value.trim())))
</script>
<style scoped>
.building-coverage{border:1px solid #34556a;border-radius:7px;padding:12px;margin-bottom:18px;background:#102a3a}.coverage-title{display:flex;align-items:center;justify-content:space-between;gap:8px}.coverage-title h4{border:0!important;padding:0!important;margin:0!important;font-size:14px}.coverage-title>span{color:#85cbd9;font-size:10px;white-space:nowrap}.coverage-toggle{display:flex!important;align-items:center;gap:7px;margin:12px 0!important;font-size:12px!important;line-height:1.6}.coverage-toggle input{width:14px;height:14px;accent-color:#69cfe2}.coverage-state{font-size:12px;line-height:1.7;color:#b9dce4;margin:10px 0}.coverage-counts{display:flex;gap:6px;font-size:10px;color:#91bacd}.coverage-counts span{background:#17364a;padding:5px;border-radius:3px}.coverage-note{font-size:10px;color:#95b3c5;line-height:1.8;margin:10px 0 0}.coverage-error{font-size:11px;color:#f4bd95;line-height:1.7;overflow-wrap:anywhere}.coverage-search{font-size:11px!important;width:100%;box-sizing:border-box;margin:8px 0!important}.coverage-list{display:flex;flex-direction:column;gap:6px}.coverage-list button{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:10px!important;text-align:left;width:100%;font-size:12px!important}.coverage-list small{display:block;color:#91b2c6;font-size:9px;margin-top:5px}.coverage-list b{font-size:10px;white-space:nowrap;color:#8bd3e2}.coverage-retry{font-size:11px!important}
.building-coverage button,.coverage-search{font:inherit;color:#d3e5f1;background:#112b3e;border:1px solid #335069;border-radius:5px;padding:8px 10px}.building-coverage button{cursor:pointer}.building-coverage button:hover{background:#1b3c52;border-color:#72b8ca}
</style>

