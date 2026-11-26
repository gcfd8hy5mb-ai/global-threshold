'use strict';
(()=>{
let data=null;
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fresh=()=>{const age=Date.now()-Date.parse(data?.generatedAt||'');return Number.isFinite(age)&&age>=0&&age<6*3600000};
const safe=url=>{try{const u=new URL(url);return ['https:','http:'].includes(u.protocol)&&['news.un.org','justice.gov','www.justice.gov','wto.org','www.wto.org','osce.org','www.osce.org','news.osce.org','iaea.org','www.iaea.org'].includes(u.hostname)}catch{return false}};
function render(){document.querySelectorAll('[data-public-news]').forEach(n=>{
 const s=data?.sources?.find(x=>x.id===n.dataset.publicNews);
 const valid=fresh()&&s?.status==='available'&&Array.isArray(s.items);
 const seen=new Set();
 const items=valid?s.items.filter(x=>{if(!safe(x.url)||typeof x.title!=='string'||typeof x.publishedAt!=='string')return false;const k=x.title.trim().toLowerCase()+'|'+x.publishedAt.slice(0,10);if(seen.has(k))return false;seen.add(k);return true}).slice(0,n.dataset.compact==='true'?2:12):[];
 n.innerHTML='<p class="notice">'+esc(s?.source||'Public-source reports')+' · '+(valid?'Collected '+esc(data.generatedAt):'Current collection unavailable or stale')+'</p>'+items.map(x=>'<div class="gt-event"><b>'+esc(x.title)+'</b><span>Published '+esc(x.publishedAt.slice(0,10))+'</span><a class="gt-link" href="'+esc(x.url)+'" target="_blank" rel="noopener noreferrer">Original report</a></div>').join('')+(valid&&!items.length?'<p>No dated reports returned in the collection window.</p>':'')+'<p class="notice">Selected publisher reports, not comprehensive incident coverage or a threat rating. Publication dates are not incident dates. Allegations are not findings of guilt.</p>';
})}
async function load(){try{const r=await fetch('https://raw.githubusercontent.com/gcfd8hy5mb-ai/global-threshold/main/data/public-news.json?t='+Date.now(),{cache:'no-store'});if(!r.ok)throw Error();data=await r.json()}catch{data=null}render();document.dispatchEvent(new CustomEvent('gt-public-news',{detail:data}))}
document.addEventListener('gt-news-render',render);document.addEventListener('gt-page',render);document.addEventListener('visibilitychange',()=>{if(!document.hidden)load()});render();load();
})();
