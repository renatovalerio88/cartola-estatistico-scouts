(function(){
'use strict';
if(typeof window==='undefined'||typeof window.fetch!=='function')return;
const nativeFetch=window.fetch.bind(window);
function currentData(){
  try{if(typeof D!=='undefined'&&D&&D.produto)return D}catch(_){}
  return window.__CARTOLA_DADOS__&&window.__CARTOLA_DADOS__.produto?window.__CARTOLA_DADOS__:null;
}
function fakeResponse(data){
  return {
    ok:true,status:200,statusText:'OK',url:'dados.json',headers:new Headers({'content-type':'application/json'}),
    json:async()=>data,
    text:async()=>JSON.stringify(data),
    clone(){return fakeResponse(data)}
  };
}
function isDataRequest(input){
  const url=typeof input==='string'?input:(input&&input.url)||'';
  return /(^|\/)dados\.json(?:[?#]|$)/.test(url);
}
window.fetch=function(input,init){
  if(!isDataRequest(input))return nativeFetch(input,init);
  const ready=currentData();
  if(ready){window.__CARTOLA_DADOS__=ready;return Promise.resolve(fakeResponse(ready));}
  return new Promise((resolve,reject)=>{
    const started=Date.now();
    const timer=setInterval(()=>{
      const data=currentData();
      if(data){clearInterval(timer);window.__CARTOLA_DADOS__=data;resolve(fakeResponse(data));return;}
      if(Date.now()-started>=90000){clearInterval(timer);nativeFetch(input,init).then(resolve,reject);}
    },50);
  });
};
})();
