'use strict';
(()=>{
let rows=[];
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function render(){document.querySelectorAll('[data-history]').forEach(n=>{
 n.innerHTML='<p class="notice">Observed values retained as collection runs succeed. Revised observations replace earlier values for the same date; this is not a real-time release-vintage archive or backtest.</p>'+ (rows.length?rows.map(r=>{const points=(r.history||[]).filter(x=>Number.isFinite(x.value)&&/^\d{4}-\d{2}-\d{2}$/.test(x.date)).slice(-12).reverse();return '<details><summary>'+esc(r.label)+' · '+points.length+' recent retained periods</summary>'+points.map(x=>'<div class="data-row"><span>'+esc(x.date)+'</span><b>'+esc(x.value.toLocaleString('en-US',{maximumFractionDigits:4}))+' '+esc(r.unit)+'</b></div>').join('')+'</details>'}).join(''):'<p class="notice">Awaiting verified observation history.</p>');
})}
document.addEventListener('gt-current-macro',e=>{rows=e.detail.rows;render()});document.addEventListener('gt-page',render);render();
})();
