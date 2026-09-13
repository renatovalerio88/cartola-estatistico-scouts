(function(){
'use strict';
if(typeof window==='undefined'||typeof window.fetch!=='function')return;
const nativeFetch=window.fetch.bind(window);
let dataPromise=null;
function isSiteData(input){
  try{
    const raw=typeof input==='string'?input:(input&&input.url)||'';
    const u=new URL(raw,location.href);
    return /\/dados(?:-lite)?\.json$/.test(u.pathname);
  }catch(_){return false}
}
async function loadOnce(){
  if(!dataPromise){
    dataPromise=nativeFetch('dados-lite.json',{cache:'no-cache'}).then(async r=>{
      if(!r.ok)throw new Error('HTTP '+r.status+' ao carregar dados-lite.json');
      const text=await r.text();
      return {text,headers:{'Content-Type':'application/json; charset=utf-8'}};
    }).catch(err=>{dataPromise=null;throw err});
  }
  return dataPromise;
}
window.fetch=async function(input,init){
  if(!isSiteData(input))return nativeFetch(input,init);
  const cached=await loadOnce();
  return new Response(cached.text,{status:200,headers:cached.headers});
};
window.__cartolaDataLoader={clear:function(){dataPromise=null;},ready:function(){return loadOnce();}};
})();
