(function(){
'use strict';
if(typeof document==='undefined')return;

function norm(s){return String(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().trim()}
function allPlayers(){try{return Array.isArray(players)?players:[]}catch(_){return []}}
function eligible(p){
  const raw=p&&((p.status_id!=null)?p.status_id:p.statusId);
  return raw==null||Number(raw)===7;
}
function positionOf(card){
  const sel=card&&card.querySelector('select.custom-pick');
  if(sel&&sel.dataset.pos)return sel.dataset.pos;
  const txt=norm(card&&card.querySelector('h3')&&card.querySelector('h3').textContent);
  return txt.includes('goleir')?'GOL':txt.includes('later')?'LAT':txt.includes('zagueir')?'ZAG':txt.includes('meia')?'MEI':txt.includes('atac')?'ATA':txt.includes('tecn')?'TEC':'';
}
function usedIds(){
  try{return new Set(Object.values(customForced||{}).flat().map(String))}catch(_){return new Set()}
}
function money(v){return 'C$ '+Number(v||0).toLocaleString('pt-BR',{minimumFractionDigits:2,maximumFractionDigits:2})}
function pts(v){return Number(v||0).toLocaleString('pt-BR',{minimumFractionDigits:2,maximumFractionDigits:2})+' pts'}
function venue(p){return p&&p.mando==='casa'?'🏠':'✈️'}

function rebuildResults(input){
  const card=input.closest('.picker-card');if(!card)return;
  const pos=positionOf(card),res=card.querySelector('.mp-results');if(!pos||!res)return;
  const q=norm(input.value),used=usedIds();
  const list=allPlayers().filter(p=>p.posicao===pos&&eligible(p)&&!used.has(String(p.atleta_id))&&(!q||norm(p.apelido).includes(q)||norm(p.sigla_clube).includes(q)||norm(p.sigla_adversario).includes(q))).sort((a,b)=>Number(b.projecao||0)-Number(a.projecao||0)||Number(a.preco||0)-Number(b.preco||0));
  res.innerHTML=list.map(p=>`<button type="button" class="mp-result eligibility-result" data-id="${p.atleta_id}"><b>${p.apelido}</b><small>${p.sigla_clube||'—'} · ${venue(p)} ${p.sigla_adversario||'—'} · ${money(p.preco)}</small><strong>${pts(p.projecao)}</strong></button>`).join('')||'<div class="empty" style="padding:8px;font-size:.66rem">Nenhum jogador disponível encontrado.</div>';
  res.classList.add('open');
}

function choose(button){
  const card=button.closest('.picker-card'),pos=positionOf(card),id=String(button.dataset.id||'');
  const p=allPlayers().find(x=>String(x.atleta_id)===id);if(!card||!pos||!p||!eligible(p))return;
  try{
    customForced[pos]=customForced[pos]||[];
    if(!customForced[pos].some(x=>String(x)===id))customForced[pos].push(id);
    renderCustomPickers();
    const input=card.querySelector('.mp-search');if(input)input.value='';
    const res=card.querySelector('.mp-results');if(res)res.classList.remove('open');
  }catch(e){console.warn('Falha ao selecionar jogador',e)}
}

function cleanProjections(){
  document.querySelectorAll('#projectionTable .projection-card[data-projection-id]').forEach(card=>{
    const p=allPlayers().find(x=>String(x.atleta_id)===String(card.dataset.projectionId));
    if(p&&!eligible(p))card.remove();
  });
  const cards=[...document.querySelectorAll('#projectionTable .projection-card[data-projection-id]')];
  cards.forEach((card,i)=>{const r=card.querySelector('.projection-rank');if(r)r.textContent='#'+(i+1)});
  const audit=document.getElementById('confidenceAudit');
  if(audit&&cards.length){
    const first=audit.querySelector('span');
    if(first)first.innerHTML=first.innerHTML.replace(/^<b>\d+<\/b> jogadores/,`<b>${cards.length}</b> jogadores disponíveis`);
  }
}

document.addEventListener('focusin',e=>{if(e.target&&e.target.matches('#monte .mp-search'))setTimeout(()=>rebuildResults(e.target),0)});
document.addEventListener('input',e=>{if(e.target&&e.target.matches('#monte .mp-search'))setTimeout(()=>rebuildResults(e.target),0)});
document.addEventListener('click',e=>{
  const b=e.target&&e.target.closest&&e.target.closest('#monte .eligibility-result');
  if(!b)return;
  e.preventDefault();e.stopPropagation();e.stopImmediatePropagation();choose(b);
},true);

const obs=new MutationObserver(()=>setTimeout(cleanProjections,0));
window.addEventListener('load',()=>{
  const box=document.getElementById('projectionTable');if(box)obs.observe(box,{childList:true,subtree:true});
  cleanProjections();
});
setTimeout(cleanProjections,500);setTimeout(cleanProjections,1500);
})();
