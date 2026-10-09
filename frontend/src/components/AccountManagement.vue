<template><main class="page-surface"><header class="page-head"><h2>用户管理与操作日志</h2><button class="btn btn-ghost" @click="load">刷新</button></header><p v-if="error" class="notice-banner notice-error" role="alert">{{error}}</p><p v-if="message" class="notice-banner notice-info">{{message}}</p><section class="panel"><div class="panel-head"><h3>{{editing?'编辑账户':'创建账户'}}</h3></div><form class="panel-body form" @submit.prevent="save"><label>账号<input v-model.trim="form.username" :disabled="editing" required maxlength="64"></label><label>角色<select v-model="form.role"><option value="user">普通用户</option><option value="admin">管理员</option></select></label><label>密码<input v-model="form.password" type="password" :required="!editing" minlength="8" maxlength="128" autocomplete="new-password" :placeholder="editing?'留空保留原密码':'至少8位'"></label><label><input v-model="form.enabled" type="checkbox">启用账户</label><button class="btn btn-primary" :disabled="busy">保存</button><button type="button" class="btn btn-ghost" @click="reset">新建账户</button></form><p class="hint">修改账户后，该账户需要重新登录；最后一个有效管理员不能停用或降级。</p></section><section class="panel"><div class="panel-head"><h3>账户列表</h3></div><div class="panel-body"><table class="data-table"><thead><tr><th>账号</th><th>角色</th><th>状态</th><th>操作</th></tr></thead><tbody><tr v-for="u in users" :key="u.username"><td>{{u.username}}</td><td>{{u.role==='admin'?'管理员':'普通用户'}}</td><td>{{u.enabled?'启用':'停用'}}</td><td><button class="btn btn-ghost" @click="edit(u)">编辑／重置密码</button></td></tr></tbody></table></div></section><section class="panel"><div class="panel-head"><h3>最近200条操作记录</h3></div><div class="panel-body logs"><table class="data-table"><thead><tr><th>时间</th><th>账户</th><th>操作</th><th>目标</th></tr></thead><tbody><tr v-for="l in logs" :key="l.id"><td>{{new Date(l.created*1000).toLocaleString('zh-CN')}}</td><td>{{l.username}}</td><td>{{l.action}}</td><td>{{l.target}}</td></tr></tbody></table></div></section></main></template>
<script setup>
import {ref,onMounted} from 'vue'
import api from '../api'
const users=ref([]),logs=ref([]),error=ref(''),message=ref(''),busy=ref(false),editing=ref(false)
const blank=()=>({username:'',password:'',role:'user',enabled:true})
const form=ref(blank())
function reset(){editing.value=false;form.value=blank()}
function edit(u){editing.value=true;form.value={...u,password:'',enabled:!!u.enabled}}
async function load(){try{[users.value,logs.value]=await Promise.all([api.users(),api.logs()])}catch(e){error.value=e.message}}
async function save(){busy.value=true;error.value='';message.value='';try{const body={...form.value,password:form.value.password||null};await (editing.value?api.updateUser(body):api.createUser(body));message.value='账户已保存';reset();await load()}catch(e){error.value=e.message}finally{busy.value=false}}
onMounted(load)
defineExpose({refresh:load})
</script>
<style scoped>
.page-surface{display:flex;flex-direction:column;gap:16px;min-width:0}
.page-head{align-items:center;justify-content:space-between;margin-bottom:0}
.page-head h2{margin:0}
.panel{flex:0 0 auto;min-width:0}
.panel-body{padding:16px;overflow-x:auto}
.panel-body.form{display:grid;grid-template-columns:minmax(180px,260px) minmax(130px,180px) minmax(200px,280px) max-content max-content max-content;align-items:end;justify-content:start;gap:16px;flex:0 0 auto;overflow:visible}
.form label{display:flex;flex-direction:column;gap:8px;min-width:0;font-size:13px;color:var(--text-dim)}
.form input:not([type=checkbox]),.form select{width:100%;box-sizing:border-box;height:40px;padding:9px 12px;background:#10243a;color:#fff;border:1px solid #34516e;border-radius:6px}
.form label:has(input[type=checkbox]){flex-direction:row;align-items:center;align-self:end;height:40px;white-space:nowrap}
.form input[type=checkbox]{width:15px;height:15px;margin:0;accent-color:var(--cyan)}
.form .btn{height:40px;white-space:nowrap}
.hint{font-size:12px;color:var(--text-dim);padding:0 16px 16px;margin:0}
.logs{max-height:450px;overflow:auto}
.data-table{width:100%;text-align:left}
.logs td:last-child{overflow-wrap:anywhere}
@media(max-width:1200px){.panel-body.form{grid-template-columns:repeat(3,minmax(0,1fr))}.form label:has(input[type=checkbox]){grid-column:1}.form .btn{justify-self:start}}
@media(max-width:650px){.panel-body.form{grid-template-columns:1fr 1fr}.form label:first-child,.form label:nth-child(3){grid-column:1/-1}.form label:has(input[type=checkbox]){grid-column:auto}}
</style>
