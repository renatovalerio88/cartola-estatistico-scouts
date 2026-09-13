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
      const data=JSON.parse(text);
      return {text,data,headers:{'Content-Type':'application/json; charset=utf-8'}};
    }).catch(err=>{
      dataPromise=null;
      throw err;
    });
  }
  return dataPromise;
}

function responseFromCached(cached){
  const response=new Response(cached.text,{status:200,headers:cached.headers});
  response.json=async()=>cached.data;
  return response;
}

window.fetch=async function(input,init){
  if(!isSiteData(input))return nativeFetch(input,init);
  const cached=await loadOnce();
  return responseFromCached(cached);
};

window.__cartolaDataLoader={
  clear:function(){dataPromise=null;},
  ready:async function(){return (await loadOnce()).data;}
};
})();
