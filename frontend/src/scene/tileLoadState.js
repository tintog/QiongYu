// A bounded loading episode: slow or failed requests never look like endless progress.
export function createTileLoadState(timeout=20000){
 const channels=new Map();
 const get=key=>{if(!channels.has(key))channels.set(key,{pending:0,started:0,errors:0});return channels.get(key)};
 return {
  update(key,pending,now=Date.now()){const s=get(key);if(pending>0&&s.pending===0)s.started=now;s.pending=Math.max(0,pending)},
  fail(key){get(key).errors++},
  reset(key){channels.set(key,{pending:0,started:0,errors:0})},
  snapshot(now=Date.now()){const entries=[...channels.entries()].map(([key,s])=>({key,...s,slow:s.pending>0&&now-s.started>=timeout}));const pending=entries.reduce((n,s)=>n+s.pending,0);const warning=entries.some(s=>s.slow||s.errors);return {pending,phase:warning?'warning':pending?'loading':'ready',entries}}
 }
}
