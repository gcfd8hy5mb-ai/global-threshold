'use strict';
(()=>{
let snapshot=null;
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function render(){document.querySelectorAll('[data-infra]').forEach(n=>{
 const a=snapshot?.aviation;
 const age=Date.now()-Date.parse(snapshot?.generatedAt||'');
 const sourceAge=Date.now()-Date.parse(a?.sourceUpdated||'');
 const valid=Number.isFinite(sourceAge)&&sourceAge>=0&&sourceAge<=3*3600000&&a?.status==='available'&&Number.isFinite(age)&&age>=0&&age<=3*3600000;
 const sector=(name,status,desc,body)=>'<section class="panel"><h3>'+esc(name)+'</h3><p class="gold">'+esc(status)+'</p><p class="notice">'+esc(desc)+'</p>'+body+'</section>';
 const link=(url,label)=>'<a class="gt-link" href="'+url+'" target="_blank" rel="noopener">'+esc(label)+'</a>';
 const air=valid?'<p class="notice">FAA feed update: '+esc(a.sourceUpdated)+' · Collected '+esc(snapshot.generatedAt)+'</p>'+ (Array.isArray(a.categories)&&a.categories.length?a.categories.map(r=>'<div class="data-row"><span>'+esc(r.label)+'</span><b>'+esc(r.reportedEntries)+'</b></div>').join(''):'<p>No categories returned by this snapshot.</p>'):'<p class="notice">Current aviation observations unavailable or stale.</p>';
 n.innerHTML='<p><b>'+ (valid?'1 of 6':'0 of 6')+' divisions with current reporting</b></p><p class="notice">These six divisions are an application-specific grouping, not the full federal critical infrastructure sector taxonomy. Coverage is not a risk rating. No national infrastructure risk score is supported.</p>'+
 sector('Power Grid','Reference only','Electricity generation and distribution. Automated outage coverage unavailable.',link('https://doe417.energy.gov/','DOE electric disturbance reports'))+
 sector('Water Systems','Reference only','Drinking water and wastewater. Compliance records are not current outage reports.',link('https://echo.epa.gov/trends/comparative-maps-dashboards/drinking-water-dashboard','EPA drinking water compliance'))+
 sector('Communications','Reference only','Telecommunications and internet services. Automated outage coverage unavailable.',link('https://www.fcc.gov/','FCC official notices'))+
 sector('Transportation',valid?'Partial current reporting':'Current reporting unavailable','Aviation, rail, highways and ports. Only aggregate aviation observations are collected automatically.','<h4>Aviation</h4>'+air+'<p class="notice">Reported entries are not confirmed outages or affected passenger counts. No cause is inferred.</p>'+link('https://nasstatus.faa.gov/','Official FAA status'))+
 sector('Energy Infrastructure','Reference only','Fuel distribution, pipelines and refining. Market prices do not establish infrastructure disruptions.', '<button class="section-button" data-page="Energy">Energy market observations →</button>')+
 sector('Emergency Services','Not connected','Emergency response and communications. No automated national disruption reporting is connected.','');

})}
async function load(){try{const r=await fetch('https://raw.githubusercontent.com/gcfd8hy5mb-ai/global-threshold/main/data/infrastructure.json?t='+Date.now(),{cache:'no-store'});if(!r.ok)throw Error();snapshot=await r.json()}catch{snapshot=null}render();document.dispatchEvent(new CustomEvent('gt-infrastructure',{detail:snapshot}))}
document.addEventListener('gt-page',render);document.addEventListener('visibilitychange',()=>{if(!document.hidden)load()});render();load();
})();
