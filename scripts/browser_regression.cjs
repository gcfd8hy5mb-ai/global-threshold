'use strict';
const { chromium,webkit }=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const names=['Dashboard','Briefing','Economics','Geopolitics','Risk Signals','More','Infrastructure','Energy','Markets','Cybersecurity','Supply Chains','Government','Scenarios','History','Calendar','Sources','Settings'];
(async()=>{for(const [engine,width,height] of [[chromium,1366,900],[webkit,390,844]]){
 const browser=await engine.launch({headless:true});try{
 const page=await browser.newPage({viewport:{width,height},isMobile:width<500,hasTouch:width<500});const errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/*',async route=>{const u=new URL(route.request().url());if(u.hostname==='127.0.0.1')return route.continue();const m=u.pathname.match(/\/data\/([a-z-]+)\.json$/);if(m&&fs.existsSync('data/'+m[1]+'.json'))return route.fulfill({contentType:'application/json',body:fs.readFileSync('data/'+m[1]+'.json','utf8'),headers:{'access-control-allow-origin':'*'}});return route.abort();});
 await page.goto('http://127.0.0.1:8765/index.html');await page.waitForSelector('#content .metric');
 for(const name of names){await page.evaluate(n=>show(n),name);assert(await page.locator('#content .panel').count()>0,name);assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2),'horizontal overflow: '+name); }
 await page.evaluate(()=>show('Dashboard'));await page.locator('#content [data-metric]').first().click();assert(await page.locator('#modal').evaluate(e=>e.open));await page.locator('#close').click();assert(!(await page.locator('#modal').evaluate(e=>e.open)));
 await page.locator('#search').click();await page.locator('#query').fill('History');await page.locator('#results [data-page="History"]').click();assert(await page.locator('[data-history]').count()===1);
 await page.waitForTimeout(500);assert.deepEqual(errors,[]);console.log(engine.name(),width,'17 page checks and dialog/search passed');
 }finally{await browser.close()}
}})().catch(e=>{console.error(e);process.exitCode=1});
