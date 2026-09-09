(function(){
'use strict';
if(typeof document==='undefined')return;

const CSS=`
#monte .hero{display:none}
#monte{--mp-line:#dfe9e4;--mp-soft:#f5f9f7;--mp-green:#176b4b;--mp-muted:#72857d}
#monte>.controls{display:grid;grid-template-columns:minmax(150px,.7fr) minmax(210px,1fr) auto auto;gap:9px;align-items:end;background:#fff;border:1px solid var(--mp-line);border-radius:16px;padding:12px 14px;margin:0 0 9px;box-shadow:0 8px 24px rgba(22,69,50,.05)}
#monte>.controls .field label{font-size:.68rem;text-transform:uppercase;letter-spacing:.035em}
#monte>.controls input,#monte>.controls select{min-height:39px}
#monte .custom-help{border:0;background:transparent;padding:3px 2px 8px;font-size:.78rem}
#monte .mp-budget{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:0;border:1px solid var(--mp-line);border-radius:14px;background:#fff;overflow:hidden;margin:7px 0 12px}
#monte .mp-budget>div{padding:9px 12px}.mp-budget>div:not(:last-child){border-right:1px solid var(--mp-line)}
#monte .mp-budget small{display:block;color:#7b8c85;font-size:.59rem;text-transform:uppercase;letter-spacing:.035em;font-weight:800}.mp-budget b{display:block;margin-top:2px;font-size:.94rem;color:#29453b}.mp-budget .available b{color:var(--mp-green)}
#monte .mp-budget.over .available b{color:#b84f4f}
#monte .picker{grid-template-columns:repeat(3,minmax(0,1fr));gap:9px;margin:8px 0 14px}
#monte .picker-card{padding:10px 11px;border-radius:14px;box-shadow:0 5px 17px rgba(22,69,50,.04);overflow:visible}
#monte .picker-card h3{display:flex;justify-content:space-between;align-items:center;margin:0 0 7px;font-size:.78rem;text-transform:uppercase;letter-spacing:.025em;color:#587068}
#monte .picker-row{display:block;margin:0;position:relative}.mp-search{width:100%;min-width:0!important;min-height:37px!important;padding:7px 9px!important;font-size:.77rem}
#monte .picker-row select,#monte .picker-row>.btn{position:absolute!important;width:1px!important;height:1px!important;opacity:0!important;pointer-events:none!important;overflow:hidden!important;padding:0!important;min-height:0!important;border:0!important}
#monte .mp-results{display:none;position:absolute;z-index:40;left:0;right:0;top:42px;border:1px solid var(--mp-line);border-radius:10px;background:#fff;overflow:hidden;box-shadow:0 12px 28px rgba(22,69,50,.14);max-height:310px;overflow-y:auto}
#monte .mp-results.open{display:block}.mp-result{width:100%;border:0;border-top:1px solid #edf2ef;background:#fff;padding:8px;display:grid;grid-template-columns:minmax(0,1fr) auto;gap:2px 8px;text-align:left;cursor:pointer;color:#29453b}.mp-result:first-child{border-top:0}.mp-result:hover,.mp-result:focus{background:#f3f8f5;outline:0}.mp-result b{font-size:.77rem}.mp-result small{font-size:.62rem;color:#778a82}.mp-result strong{grid-row:1/3;grid-column:2;align-self:center;font-size:.72rem;color:var(--mp-green)}
#monte .picked-list{margin-top:6px;display:grid;gap:4px}.picked-chip.mp-picked{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:1px 6px;padding:6px 7px;border-radius:9px;background:#eef6f2;border:1px solid #dcebe4;color:#29453b}.picked-chip.mp-picked .mp-picked-name{font-size:.72rem;font-weight:800}.picked-chip.mp-picked .mp-picked-meta{font-size:.58rem;color:#70847c}.picked-chip.mp-picked button{grid-row:1/3;grid-column:2;border:0;background:transparent;color:#a34c4c;font-weight:900;cursor:pointer;padding:2px 4px}
#monte .custom-picked{font-size:.62rem;margin-top:5px}
#monte #customResult>.grid:first-child{display:grid!important;grid-template-columns:1.35fr 1fr 1fr!important;gap:0!important;border:1px solid var(--mp-line)!important;border-radius:16px!important;background:#fff!important;overflow:hidden!important;margin:10px 0 12px!important;box-shadow:0 8px 24px rgba(22,69,50,.05)!important}
#monte #customResult>.grid:first-child .card{border:0!important;border-radius:0!important;box-shadow:none!important;padding:11px 13px!important}
#monte #customResult>.grid:first-child .card:not(:last-child){border-right:1px solid var(--mp-line)!important}
#monte #customResult>.grid:first-child .metric small{font-size:.59rem!important;color:#7d8e87!important;text-transform:uppercase;font-weight:800}
#monte #customResult>.grid:first-child .metric b{font-size:1rem!important}.mp-selected-note{margin:-4px 0 10px;color:var(--mp-muted);font-size:.67rem;font-weight:700}
#monte #customPitch .user-picked .ball{box-shadow:0 0 0 3px #d8a233,0 5px 14px rgba(0,0,0,.16)}
#monte #customPitch .user-picked .name:after{content:' · você';color:#fff3c9;font-size:.54rem}
@media(max-width:800px){#monte>.controls{grid-template-columns:1fr 1fr}#monte .picker{grid-template-columns:1fr 1fr}}
@media(max-width:520px){#monte>.controls{grid-template-columns:1fr 1fr;padding:10px}#monte>.controls .btn{grid-column:auto}#monte .mp-budget{grid-template-columns:1fr!important}#monte .mp-budget>div{padding:7px 10px!important}#monte .mp-budget>div:not(:last-child){border-right:0!important;border-bottom:1px solid var(--mp-line)}#monte .picker{grid-template-columns:1fr}#monte #customResult>.grid:first-child{grid-template-columns:1fr 1fr!important}#monte #customResult>.grid:first-child .card:first-child{grid-column:1/3;border-bottom:1px solid var(--mp-line)!important}#monte #customResult>.grid:first-child .card:nth-child(2){border-right:1px solid var(--mp-line)!important}#monte #customResult>.grid:first-child .card:nth-child(3){border-right:0!important}}
`;

const labels={GOL:'Goleiros',LAT:'Laterais',ZAG:'Zagueiros',MEI:'Meias',ATA:'Atacantes',TEC:'Técnicos'};
const money=v=>'C$ '+Number(v||0).toLocaleString('pt-BR',{minimumFractionDigits:2,maximumFractionDigits:2});
let players=[];
let refreshTimer=null;

function injectStyle(){
  if(document.getElementById('monte-premium-style'))return;
  const s=document.createElement('style');s.id='monte-premium-style';s.textContent=CSS;document.head.appendChild(s);
}
function norm(s){return String(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().trim()}
function setText(el,text){if(el&&el.textContent!==text)el.textContent=text}
function cardPosition(card){
  const sel=card.querySelector('select.custom-pick');
  if(sel?.dataset.pos)return sel.dataset.pos;
  const h=norm(card.querySelector('h3')?.textContent);
  return Object.keys(labels).find(p=>h.includes(norm(labels[p])))||'';
}
function pickedEntries(){
  const out=[];
  document.querySelectorAll('#customPickers .picker-card').forEach(card=>{
    const pos=cardPosition(card);
    card.querySelectorAll('.picked-chip').forEach(ch=>{
      const name=(ch.querySelector('.mp-picked-name')?.textContent||Array.from(ch.childNodes).filter(n=>n.nodeType===3).map(n=>n.textContent).join('')).trim();
      if(name)out.push({pos,name});
    });
  });
  return out;
}
function pickedPlayers(){
  return pickedEntries().map(e=>players.find(p=>p.posicao===e.pos&&norm(p.apelido)===norm(e.name))).filter(Boolean);
}
function budgetPanel(){
  const help=document.querySelector('#monte .custom-help');if(!help)return;
  let el=document.getElementById('mpBudget');
  if(!el){el=document.createElement('div');el.id='mpBudget';el.className='mp-budget';help.parentNode.insertBefore(el,help.nextSibling)}
  const total=Number(document.getElementById('customBudget')?.value||120),spent=pickedPlayers().reduce((a,p)=>a+Number(p.preco||0),0),available=total-spent;
  const html=`<div><small>Patrimônio</small><b>${money(total)}</b></div><div><small>Comprometido</small><b>${money(spent)}</b></div><div class="available"><small>Disponível</small><b>${money(Math.max(0,available))}</b></div>`;
  if(el.innerHTML!==html)el.innerHTML=html;
  el.classList.toggle('over',available<0);
}
function decoratePicked(card,pos){
  card.querySelectorAll('.picked-chip').forEach(ch=>{
    if(ch.dataset.mpDone==='1')return;
    const button=ch.querySelector('button');
    const raw=Array.from(ch.childNodes).filter(n=>n.nodeType===3).map(n=>n.textContent).join('').trim();
    const p=players.find(x=>x.posicao===pos&&norm(x.apelido)===norm(raw));
    if(!p)return;
    Array.from(ch.childNodes).filter(n=>n.nodeType===3).forEach(n=>n.remove());
    const n=document.createElement('span');n.className='mp-picked-name';n.textContent=p.apelido;
    const m=document.createElement('span');m.className='mp-picked-meta';m.textContent=`${p.sigla_clube||'—'} · ${money(p.preco)} · ${Number(p.projecao||0).toLocaleString('pt-BR',{minimumFractionDigits:2,maximumFractionDigits:2})} pts`;
    ch.insertBefore(n,button||null);ch.insertBefore(m,button||null);ch.classList.add('mp-picked');ch.dataset.mpDone='1';
  });
}
function isEligible(p){
  const status=p?.status_id??p?.statusId;
  return status==null||Number(status)===7;
}
function searchResults(pos,q){
  const used=new Set(pickedPlayers().map(p=>String(p.atleta_id)));
  return players.filter(p=>p.posicao===pos&&isEligible(p)&&!used.has(String(p.atleta_id))&&(!q||norm(p.apelido).includes(q)||norm(p.sigla_clube).includes(q))).sort((a,b)=>Number(b.projecao||0)-Number(a.projecao||0)||Number(a.preco||0)-Number(b.preco||0)).slice(0,8);
}
function venue(p){const m=p?.mando;return m==='casa'||m===true||m===1?'🏠':'✈️'}
function decorate(){
  const root=document.getElementById('customPickers');if(!root||!players.length)return;
  root.querySelectorAll('.picker-card').forEach(card=>{
    const pos=cardPosition(card),h=card.querySelector('h3'),sel=card.querySelector('select.custom-pick');if(!pos)return;
    decoratePicked(card,pos);
    if(h){
      const picked=card.querySelectorAll('.picked-chip').length;
      const source=h.textContent;
      const match=source.match(/\d+\s*\/\s*(\d+)/);
      const cap=match?Number(match[1]):Number(sel?.dataset.max||0);
      const target=`<span>${labels[pos]}</span><span>${cap?picked+'/'+cap:''}</span>`;
      if(h.innerHTML!==target)h.innerHTML=target;
    }
    if(!sel||card.querySelector('.mp-search'))return;
    const row=card.querySelector('.picker-row');if(!row)return;
    const input=document.createElement('input');input.className='mp-search';input.type='search';input.placeholder=`Buscar ${labels[pos].toLowerCase()}...`;input.autocomplete='off';input.setAttribute('aria-label',`Buscar ${labels[pos].toLowerCase()}`);
    const res=document.createElement('div');res.className='mp-results';
    row.insertBefore(input,row.firstChild);input.after(res);
    const run=()=>{
      const q=norm(input.value),list=searchResults(pos,q);
      res.innerHTML=list.map(p=>`<button type="button" class="mp-result" data-id="${p.atleta_id}"><b>${p.apelido}</b><small>${p.sigla_clube||'—'} · ${money(p.preco)} · ${venue(p)} ${p.sigla_adversario||'—'}</small><strong>${Number(p.projecao||0).toLocaleString('pt-BR',{minimumFractionDigits:2,maximumFractionDigits:2})} pts</strong></button>`).join('')||'<div class="empty" style="padding:9px;font-size:.7rem">Nenhum jogador encontrado.</div>';
      res.classList.add('open');
      res.querySelectorAll('.mp-result').forEach(b=>b.addEventListener('click',()=>choose(b)));
    };
    const choose=b=>{
      sel.value=b.dataset.id;
      const add=card.querySelector('.add-pick');
      if(add)add.click();
      input.value='';res.classList.remove('open');scheduleRefresh(20);
    };
    input.addEventListener('input',run);input.addEventListener('focus',run);input.addEventListener('keydown',e=>{
      if(e.key==='Escape')res.classList.remove('open');
      if(e.key==='Enter'){
        const first=res.querySelector('.mp-result');
        if(first){e.preventDefault();choose(first)}
      }
    });
  });
}
function markUserPicked(){
  const names=new Set(pickedEntries().map(e=>norm(e.name)));
  document.querySelectorAll('#customPitch .player-ball').forEach(n=>{
    const on=names.has(norm(n.querySelector('.name')?.textContent));
    if(n.classList.contains('user-picked')!==on)n.classList.toggle('user-picked',on);
  });
  const r=document.getElementById('customResult');
  if(r&&document.getElementById('customPitch')){
    let note=r.querySelector('.mp-selected-note');
    if(!note){note=document.createElement('div');note.className='mp-selected-note';const pitch=document.getElementById('customPitch');r.insertBefore(note,pitch)}
    const qtd=names.size,text=qtd?`${qtd} jogador${qtd===1?'':'es'} escolhido${qtd===1?'':'s'} por você destacado${qtd===1?'':'s'} em dourado.`:'Time completado integralmente pelo modelo.';
    setText(note,text);
  }
}
function refresh(){
  injectStyle();
  const f=document.getElementById('customFormation');if(f&&f.options[0]&&f.options[0].textContent!=='Melhor formação (automática)')f.options[0].textContent='Melhor formação (automática)';
  setText(document.getElementById('buildCustom'),'Completar com o modelo');
  setText(document.querySelector('#monte .custom-help'),'Escolha os jogadores que você quer manter. O modelo monta o melhor restante do time dentro do seu patrimônio.');
  budgetPanel();decorate();markUserPicked();
}
function scheduleRefresh(ms=40){clearTimeout(refreshTimer);refreshTimer=setTimeout(refresh,ms)}
async function loadPlayers(){
  try{const d=await fetch('dados.json?mp='+Date.now()).then(r=>r.json());players=d.produto?.jogadores||[]}catch(e){console.warn('Monte Premium: dados indisponíveis',e)}
  scheduleRefresh(0);
}
document.addEventListener('input',e=>{if(e.target?.id==='customBudget')budgetPanel()});
document.addEventListener('click',e=>{if(e.target?.closest('#monte'))scheduleRefresh(50);if(!e.target?.closest('.picker-card'))document.querySelectorAll('.mp-results.open').forEach(x=>x.classList.remove('open'))});
window.addEventListener('load',()=>{
  const monte=document.getElementById('monte');
  if(monte){
    const obs=new MutationObserver(mutations=>{
      if(!monte.classList.contains('active'))return;
      if(mutations.some(m=>m.type==='childList'&&(m.addedNodes.length||m.removedNodes.length)))scheduleRefresh(35);
    });
    obs.observe(monte,{subtree:true,childList:true});
  }
  scheduleRefresh(150);
});
injectStyle();loadPlayers();scheduleRefresh(400);
})();