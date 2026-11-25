'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const app=fs.readFileSync('app.js','utf8');
const boundary=app.indexOf('const econ=');
if(boundary<0)throw Error('Model extraction boundary missing');
const models=vm.runInNewContext(app.slice(0,boundary)+'\n({calculateModel,calculateEnergy})');
const data=JSON.parse(fs.readFileSync('data/us-economy.json','utf8'));
const day=86400000,asOf=Date.parse(data.generatedAt);
assert(Number.isFinite(asOf));
const series=new Map(data.rows.map(r=>[r.id,{...r,history:[...new Map((r.history||[]).filter(p=>typeof p.value==='number'&&Number.isFinite(p.value)&&/^\d{4}-\d{2}-\d{2}$/.test(p.date)&&Date.parse(p.date)<=asOf).map(p=>[p.date,p])).values()].sort((a,b)=>a.date.localeCompare(b.date))}]));
function row(id,date,maxAge,previousWeek=false){
 const r=series.get(id);if(!r)return null;
 const latest=r.history.filter(p=>p.date<=date).at(-1);
 if(!latest||Date.parse(date)-Date.parse(latest.date)>maxAge*day)return null;
 const previous=previousWeek?new Date(Date.parse(latest.date)-7*day).toISOString().slice(0,10):null;
 const prior=previous?r.history.find(p=>p.date===previous):undefined;
 if(previousWeek&&!prior)return null;
 return {id,label:r.label,source:r.source,status:'available',freshness:'Within expected reporting interval',latest,prior};
}
function scoreAt(date,kind){
 const specs=kind==='economic'?[['CPIAUCNS',62],['UNRATE',62],['A191RL1Q225SBEA',120]]:[['DCOILWTICO',7],['DHHNGSP',7],['WCESTUS1',7,true],['WCRFPUS2',7,true]];
 const rows=specs.map(([id,age,week])=>row(id,date,age,week));
 if(rows.some(r=>!r))return null;
 const result=kind==='economic'?models.calculateModel(rows):models.calculateEnergy(rows);
 if(!result)return null;
 assert(Number.isFinite(result.score)&&result.score>=0&&result.score<=100);
 return {date,score:Number(result.score.toFixed(4))};
}
function summarize(points,attempted){
 const sorted=points.slice().sort((a,b)=>a.score-b.score||a.date.localeCompare(b.date)),periods={};
 for(const p of points)(periods[p.date.slice(0,4)]??=[]).push(p.score);
 return {attempted,calculated:points.length,first:points[0]?.date||null,last:points.at(-1)?.date||null,minimum:sorted[0]||null,maximum:sorted.at(-1)||null,mean:points.length?Number((points.reduce((s,p)=>s+p.score,0)/points.length).toFixed(4)):null,annual:Object.entries(periods).map(([year,v])=>({year,count:v.length,mean:Number((v.reduce((a,b)=>a+b,0)/v.length).toFixed(4)),max:Math.max(...v)}))};
}
const economicDates=(series.get('CPIAUCNS')?.history||[]).map(p=>p.date),energyDates=(series.get('WCESTUS1')?.history||[]).map(p=>p.date);
const results={generatedAt:new Date().toISOString(),snapshotAt:data.generatedAt,method:'retrospective-revised-observations-v1',limitations:'Observation-date alignment only. Publication delays and revisions are not reconstructed. Scores are exploratory diagnostics, not forecasts, probabilities, or predictive validation.',coverage:[...series.values()].map(r=>({id:r.id,count:r.history.length,first:r.history[0]?.date||null,last:r.history.at(-1)?.date||null,status:r.status})),economic:summarize(economicDates.map(d=>scoreAt(d,'economic')).filter(Boolean),economicDates.length),energy:summarize(energyDates.map(d=>scoreAt(d,'energy')).filter(Boolean),energyDates.length)};
assert.equal(models.calculateModel([]),null);assert.equal(models.calculateEnergy([]),null);
fs.writeFileSync('data/model-diagnostics.json',JSON.stringify(results,null,2)+'\n');
console.log('Economic observations:',results.economic.calculated,'/',results.economic.attempted,'; energy:',results.energy.calculated,'/',results.energy.attempted);
