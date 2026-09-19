(function(){
'use strict';
if(typeof window==='undefined'||typeof window.fetch!=='function')return;

const nativeFetch=window.fetch.bind(window);
let dataPromise=null;

function isDadosRequest(input){
  try{
    const raw=typeof input==='string'?input:(input&&input.url)||'';
    const url=new URL(raw,window.location.href);
    return url.origin===window.location.origin&&/\/dados(?:-lite)?\.json$/.test(url.pathname);
  }catch(_){return false;}
}

function loadData(){
  if(dataPromise)return dataPromise;
  dataPromise=nativeFetch('dados-lite.json',{cache:'no-cache'})
    .then(response=>{
      if(!response.ok)throw new Error('HTTP '+response.status+' ao carregar dados-lite.json');
      return response.text();
    })
    .then(text=>{
      const data=JSON.parse(text);
      window.__CARTOLA_DADOS__=data;
      return {data,text};
    })
    .catch(error=>{
      dataPromise=null;
      throw error;
    });
  window.__CARTOLA_DADOS_PROMISE__=dataPromise.then(x=>x.data);
  return dataPromise;
}

function sharedResponse(cached){
  return {
    ok:true,
    status:200,
    statusText:'OK',
    redirected:false,
    type:'basic',
    url:new URL('dados-lite.json',window.location.href).href,
    headers:new Headers({'content-type':'application/json; charset=utf-8'}),
    json:()=>Promise.resolve(cached.data),
    text:()=>Promise.resolve(cached.text),
    clone(){return sharedResponse(cached);}
  };
}

window.fetch=function(input,init){
  if(!isDadosRequest(input))return nativeFetch(input,init);
  return loadData().then(sharedResponse);
};

function loadEligibilityFix(){
  if(document.querySelector('script[data-eligibilidade-ui]'))return;
  const s=document.createElement('script');
  s.src='eligibilidade-ui.js?v=20260919a';
  s.defer=true;
  s.dataset.eligibilidadeUi='1';
  document.head.appendChild(s);
}

loadData();
loadEligibilityFix();
})();
