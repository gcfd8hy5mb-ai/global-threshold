'use strict';
(()=>{
let data=null;
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function safe(url){try{const u=new URL(url);return u.protocol==='https:'&&u.hostname==='www.sec.gov'&&u.pathname.startsWith('/Archives/edgar/data/')}catch{return false}}
function render(){document.querySelectorAll('[data-sec-cyber]').forEach(n=>{
const age=Date.now()-Date.parse(data?.generatedAt||'');
const valid=Number.isFinite(age)&&age>=0&&age<12*3600000&&['available','partial'].includes(data?.status)&&Array.isArray(data.items);
const items=valid?data.items.filter(x=>safe(x.url)).slice(0,n.dataset.compact==='true'?3:20):[];
n.innerHTML='<p class="notice">SEC EDGAR · Item 1.05 · '+(valid?(data.status==='partial'?'Partial collection · ':'')+esc(data.generatedAt):'Current collection unavailable or stale')+'</p>'+items.map(x=>'<div class="gt-event"><small>'+esc(x.form==='8-K/A'?'AMENDED DISCLOSURE':'COMPANY DISCLOSURE')+'</small><b>'+esc(x.name)+'</b><span>Filed '+esc(x.date)+'</span><a href="'+esc(x.url)+'" class="gt-link" target="_blank" rel="noopener noreferrer">Original filing</a></div>').join('')+(valid&&!items.length?'<p>No qualifying filings retrieved in this limited search.</p>':'')+'<p class="notice">US-incorporated registrants only. Filing dates are not incident dates. Amendments are not counted as new incidents. Limited search coverage; not a national attack count.</p>';
})}
async function load(){try{const r=await fetch('https://raw.githubusercontent.com/gcfd8hy5mb-ai/global-threshold/main/data/sec-cyber.json?t='+Date.now(),{cache:'no-store'});if(!r.ok)throw Error();data=await r.json()}catch{data=null}render()}
document.addEventListener('gt-page',render);document.addEventListener('gt-news-render',render);document.addEventListener('visibilitychange',()=>{if(!document.hidden)load()});render();load();
})();
