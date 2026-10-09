<template>
  <main class="login-page">
    <section class="intro"><span class="eyebrow">QIONGYU · AIM-FDP</span><h1>穹宇气象<br>大模型演示系统</h1><p>从全国降水态势到局地预报分析<br>连接预报产品、集合概率与结果检验</p><div class="features"><span>15天预报</span><span>多要素分析</span><span>集合概率</span></div></section>
    <form class="login-card" @submit.prevent="submit"><span class="eyebrow">欢迎登录</span><h2>进入气象分析工作台</h2><p class="sub">选择登录角色，使用对应账户进入系统</p><div class="roles"><button v-for="r in choices" :key="r.key" type="button" :aria-pressed="role===r.key" :class="{selected:role===r.key}" @click="role=r.key"><strong>{{r.name}}</strong><small>{{r.desc}}</small></button></div><label>账号<input v-model.trim="username" autocomplete="username" required maxlength="64" placeholder="请输入账号"></label><label>密码<input v-model="password" type="password" autocomplete="current-password" required maxlength="128" placeholder="请输入密码"></label><p v-if="error" class="error" role="alert">{{error}}</p><button class="submit" :disabled="busy">{{busy?'正在验证…':'登录系统'}}</button><p class="foot">预报数据仅供演示与技术验证</p></form>
  </main>
</template>
<script setup>
import { ref } from 'vue'
import api from '../api'
import { account } from '../auth'
const emit=defineEmits(['login'])
const role=ref('user'),username=ref(''),password=ref(''),busy=ref(false),error=ref('')
const choices=[{key:'user',name:'普通用户',desc:'预报分析 · 个人数据'},{key:'admin',name:'管理员',desc:'数据审核 · 系统管理'}]
async function submit(){busy.value=true;error.value='';try{account.value=await api.login({username:username.value,password:password.value,role:role.value});password.value='';emit('login')}catch(e){error.value=e.message}finally{busy.value=false}}
</script>
<style scoped>
.login-page{min-height:100vh;display:grid;grid-template-columns:1.1fr 1fr;align-items:center;gap:80px;padding:7vw;background:radial-gradient(ellipse at 20% 20%,#164467 0,transparent 55%),#08182c;color:#edf6ff}.eyebrow{font-size:12px;letter-spacing:3px;color:#74d5ec}.intro h1{font-size:clamp(32px,4vw,60px);line-height:1.3;margin:25px 0}.intro p{color:#a7bcd1;line-height:2;font-size:17px}.features{display:flex;gap:16px;margin-top:35px}.features span{border-top:2px solid #5fcadd;padding-top:12px;color:#bdd6e7}.login-card{max-width:490px;width:100%;padding:36px;border:1px solid #294562;border-radius:20px;background:#10233b;box-shadow:0 24px 70px #0004}.login-card h2{font-size:25px;margin:18px 0 10px}.sub,.foot{font-size:13px;color:#9db5cb}.roles{display:flex;gap:12px;margin:26px 0}.roles button{flex:1;background:#0c1c30;border:1px solid #34506e;border-radius:10px;padding:15px;color:#d4e7f6;text-align:left;cursor:pointer}.roles .selected{border-color:#6addf1;background:#143952}.roles strong,.roles small{display:block}.roles small{margin-top:8px;font-size:11px;color:#a5bdd0}.login-card label{display:block;font-size:13px;margin:18px 0}.login-card input{display:block;width:100%;box-sizing:border-box;margin-top:9px;padding:13px;background:#091a2f;color:#fff;border:1px solid #35506b;border-radius:8px}.login-card input:focus{outline:2px solid #65cee6}.submit{width:100%;padding:14px;background:#5ad0e9;color:#092439;border:0;border-radius:8px;font-weight:700;cursor:pointer;margin-top:10px}.submit:disabled{opacity:.6}.error{color:#ffa3ad;font-size:13px}.foot{text-align:center;margin-top:22px}@media(max-width:900px){.login-page{grid-template-columns:1fr;gap:25px;padding:30px}.intro h1{font-size:30px}.intro p,.features{display:none}.login-card{max-width:none}}
</style>
