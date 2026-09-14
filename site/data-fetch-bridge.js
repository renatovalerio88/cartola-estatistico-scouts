(function(){
'use strict';
if(typeof window==='undefined'||typeof window.fetch!=='function')return;

const nativeFetch=window.fetch.bind(window);
let dataPromise=null;

function isDadosRequest(input){
  try{
    const raw=typeof input==='string'?input:(input&&input.url)||'';
    const url=new URL(raw,window.location.href);
    return url.origin===window.location.origin&&/\/dados\.json$/.test(url.pathname);
  }catch(_){return false;}
}

function loadData(){
  if(dataPromise)return dataPromise;
  dataPromise=nativeFetch('dados.json',{cache:'no-cache'})
    .then(response=>{
      if(!response.ok)throw new Error('HTTP '+response.status);
      return response.json();
    })
    .then(data=>{
      window.__CARTOLA_DADOS__=data;
      return data;
    })
    .catch(error=>{
      dataPromise=null;
      throw error;
    });
  window.__CARTOLA_DADOS_PROMISE__=dataPromise;
  return dataPromise;
}

function sharedResponse(data){
  return {
    ok:true,
    status:200,
    statusText:'OK',
    redirected:false,
    type:'basic',
    url:new URL('dados.json',window.location.href).href,
    headers:new Headers({'content-type':'application/json'}),
    json:()=>Promise.resolve(data),
    text:()=>Promise.resolve(JSON.stringify(data)),
    clone(){return sharedResponse(data);}
  };
}

window.fetch=function(input,init){
  if(!isDadosRequest(input))return nativeFetch(input,init);
  return loadData().then(sharedResponse);
};

loadData();
})();
