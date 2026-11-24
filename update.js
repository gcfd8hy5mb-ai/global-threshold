'use strict';
const BUILD = document.querySelector('meta[name="gt-build"]').content;
let checking=false, lastCheck=0;
async function checkUpdate(manual=false){
 const status=document.getElementById('update-status');
 if(checking || (!manual && Date.now()-lastCheck<15000)) return;
 checking=true;lastCheck=Date.now();
 if(status)status.textContent='Checking for updates…';
 try{
  const u=new URL('version.json',document.baseURI);u.searchParams.set('t',Date.now());
  const res=await fetch(u,{cache:'no-store'});if(!res.ok)throw Error('Version unavailable');
  const info=await res.json();
  if(!/^\d+\.\d+\.\d+$/.test(info.version))throw Error('Invalid version');
  if(info.version!==BUILD){
   const parts=v=>v.split('.').map(Number);
   const a=parts(info.version),b=parts(BUILD);
   const newer=a[0]>b[0]||(a[0]===b[0]&&(a[1]>b[1]||(a[1]===b[1]&&a[2]>b[2])));
   if(newer){
    const target=new URL('index.html',document.baseURI);
    target.searchParams.set('build',info.version);
    target.searchParams.set('refresh',Date.now());
    if(new URL(location.href).searchParams.get('build')===info.version){
     if(status)status.textContent='Update publishing. Try again shortly.';
     return;
    }
    location.replace(target.href);return;
   }
  }
  if(status)status.textContent='Current build '+BUILD+' — update check complete.';
 }catch(e){if(status)status.textContent='Unable to check for updates. Your current version is still available.';}
 finally{checking=false;}
}
window.addEventListener('pageshow',()=>checkUpdate());
window.addEventListener('focus',()=>checkUpdate());
document.addEventListener('visibilitychange',()=>{if(!document.hidden)checkUpdate()});
window.addEventListener('online',()=>checkUpdate());
document.addEventListener('click',e=>{if(e.target.closest('#check-update'))checkUpdate(true)});
setInterval(()=>{if(!document.hidden)checkUpdate()},60000);
checkUpdate();
