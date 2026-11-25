'use strict';
(()=>{
let snapshot=null;
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function render(){document.querySelectorAll('[data-infra]').forEach(n=>{
 const a=snapshot?.aviation;
 const age=Date.now()-Date.parse(snapshot?.generatedAt||'');
 const sourceAge=Date.now()-Date.parse(a?.sourceUpdated||'');
 const valid=Number.isFinite(sourceAge)&&sourceAge>=0&&sourceAge<=3*3600000&&a?.status==='available'&&Number.isFinite(age)&&age>=0&&age<=3*3600000;
 n.innerHTML='<h3>US aviation operations</h3>'+(valid?'<p class="notice">FAA feed update: '+esc(a.sourceUpdated)+' · Collected '+esc(snapshot.generatedAt)+'</p>'+ (a.categories.length?a.categories.map(r=>'<div class="data-row"><span>'+esc(r.label)+'</span><b>'+esc(r.reportedEntries)+'</b></div>').join(''):'<p>No categories returned by this snapshot.</p>'):'<p class="notice">Current aviation observations unavailable or stale.</p>')+'<p class="notice">Counts are reported feed entries, not affected passenger counts or confirmed outages. Routine delays may reflect weather or traffic. No cause is inferred.</p><a class="gt-link" href="https://nasstatus.faa.gov/" target="_blank" rel="noopener">Official FAA status</a><h3>Other sector coverage</h3><div class="data-row"><span>Electricity</span><a href="https://doe417.energy.gov/" target="_blank" rel="noopener">DOE annual reports</a></div><div class="data-row"><span>Water</span><a href="https://echo.epa.gov/trends/comparative-maps-dashboards/drinking-water-dashboard" target="_blank" rel="noopener">EPA compliance</a></div><div class="data-row"><span>Telecommunications</span><a href="https://www.fcc.gov/" target="_blank" rel="noopener">FCC official notices</a></div><p class="notice">Reference links only; no automated current outage coverage. Annual compliance and event-driven reports are not equivalent to real-time outages.</p><p class="notice">No national infrastructure risk rating is supported by this partial coverage.</p>';
})}
async function load(){try{const r=await fetch('https://raw.githubusercontent.com/gcfd8hy5mb-ai/global-threshold/main/data/infrastructure.json?t='+Date.now(),{cache:'no-store'});if(!r.ok)throw Error();snapshot=await r.json()}catch{snapshot=null}render();document.dispatchEvent(new CustomEvent('gt-infrastructure',{detail:snapshot}))}
document.addEventListener('gt-page',render);document.addEventListener('visibilitychange',()=>{if(!document.hidden)load()});render();load();
})();
