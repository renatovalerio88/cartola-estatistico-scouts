(function(){
'use strict';
if(typeof document==='undefined')return;

const CSS=`
#monte{--mp-line:#dfe9e4;--mp-soft:#f5f9f7;--mp-green:#176b4b;--mp-muted:#72857d;--mp-user:#0f7652}
#monte>.hero{padding:17px 19px;margin-bottom:13px;border-radius:18px}
#monte>.hero h1{font-size:1.42rem;margin-bottom:4px}
#monte>.hero .lead{font-size:.82rem;line-height:1.45}
#monte>.controls{display:grid;grid-template-columns:minmax(150px,.7fr) minmax(210px,1fr) auto auto;gap:8px;align-items:end;background:#fff;border:1px solid var(--mp-line);border-radius:15px;padding:11px 12px;margin:0 0 8px;box-shadow:0 7px 20px rgba(22,69,50,.045)}
#monte>.controls .field{gap:3px}
#monte>.controls .field label{font-size:.64rem;text-transform:uppercase;letter-spacing:.03em}
#monte>.controls input,#monte>.controls select{min-height:37px;padding:7px 9px;border-radius:9px}
#monte>.controls .btn{min-height:37px;padding:7px 12px;border-radius:9px;font-size:.76rem}
#monte .custom-help{border:0;background:transparent;padding:2px 2px 6px;margin:0;font-size:.7rem;line-height:1.35;color:var(--mp-muted)}
#monte .mp-budget{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:0;border:1px solid var(--mp-line);border-radius:12px;background:#fff;overflow:hidden;margin:5px 0 10px;box-shadow:0 5px 16px rgba(22,69,50,.035)}
#monte .mp-budget>div{padding:7px 10px;min-width:0}.mp-budget>div:not(:last-child){border-right:1px solid var(--mp-line)}
#monte .mp-budget small{display:block;color:#7b8c85;font-size:.54rem;text-transform:uppercase;letter-spacing:.03em;font-weight:800;white-space:nowrap}.mp-budget b{display:block;margin-top:1px;font-size:.82rem;color:#29453b;white-space:nowrap}.mp-budget .available b{color:var(--mp-green)}
#monte .mp-budget.over .available b{color:#b84f4f}
#monte .picker{grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin:7px 0 12px}
#monte .picker-card{padding:9px 10px;border-radius:13px;box-shadow:0 4px 14px rgba(22,69,50,.035);overflow:visible;min-height:0!important}
#monte .picker-card h3{display:flex;justify-content:space-between;align-items:center;margin:0 0 5px;font-size:.72rem;letter-spacing:.01em;color:#38594d;text-transform:none}
#monte .picker-card h3 .mp-count{font-size:.59rem;color:#7d8d87;font-weight:750;white-space:nowrap}
#monte .picker-card>.picked-list:empty{display:none}
#monte .picker-card .picked-list>.muted{display:none!important}
#monte .picker-row{display:block;margin:0;position:relative}.mp-search{width:100%;min-width:0!important;min-height:35px!important;padding:7px 9px!important;font-size:.73rem!important;border-radius:9px!important;background:#fbfdfc!important}
#monte .picker-row select,#monte .picker-row>.btn{position:absolute!important;width:1px!important;height:1px!important;opacity:0!important;pointer-events:none!important;overflow:hidden!important;padding:0!important;min-height:0!important;border:0!important}
#monte .mp-results{display:none;position:absolute;z-index:80;left:0;right:0;top:39px;border:1px solid var(--mp-line);border-radius:10px;background:#fff;overflow:hidden;box-shadow:0 14px 30px rgba(22,69,50,.16);max-height:300px;overflow-y:auto}
#monte .mp-results.open{display:block}.mp-result{width:100%;border:0;border-top:1px solid #edf2ef;background:#fff;padding:8px 9px;display:grid;grid-template-columns:minmax(0,1fr) auto;gap:2px 8px;text-align:left;cursor:pointer;color:#29453b}.mp-result:first-child{border-top:0}.mp-result:hover,.mp-result:focus{background:#f3f8f5;outline:0}.mp-result b{font-size:.75rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.mp-result small{font-size:.59rem;color:#778a82;line-height:1.25}.mp-result strong{grid-row:1/3;grid-column:2;align-self:center;font-size:.7rem;color:var(--mp-green);white-space:nowrap}.mp-status{display:inline-block;margin-left:4px;color:#4b806c;font-weight:800}
#monte .picked-list{margin-top:5px;display:grid;gap:4px}.picked-chip.mp-picked{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:1px 6px;padding:5px 7px;border-radius:8px;background:#eef6f2;border:1px solid #dcebe4;color:#29453b}.picked-chip.mp-picked .mp-picked-name{font-size:.68rem;font-weight:800;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.picked-chip.mp-picked .mp-picked-meta{font-size:.55rem;color:#70847c;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.picked-chip.mp-picked button{grid-row:1/3;grid-column:2;border:0;background:transparent;color:#a34c4c;font-weight:900;cursor:pointer;padding:1px 3px}
#monte .custom-picked{font-size:.58rem;margin-top:3px;color:var(--mp-muted)}
#monte #customResult>.grid:first-child{display:grid!important;grid-template-columns:1.35fr 1fr 1fr!important;gap:0!important;border:1px solid var(--mp-line)!important;border-radius:14px!important;background:#fff!important;overflow:hidden!important;margin:9px 0 10px!important;box-shadow:0 6px 18px rgba(22,69,50,.04)!important}
#monte #customResult>.grid:first-child .card{border:0!important;border-radius:0!important;box-shadow:none!important;padding:9px 11px!important}
#monte #customResult>.grid:first-child .card:not(:last-child){border-right:1px solid var(--mp-line)!important}
#monte #customResult>.grid:first-child .metric small{font-size:.55rem!important;color:#7d8e87!important;text-transform:uppercase;font-weight:800}
#monte #customResult>.grid:first-child .metric b{font-size:.93rem!important}.mp-selected-note{display:flex;align-items:center;gap:6px;margin:-2px 0 8px;padding:6px 8px;border:1px solid #dcebe4;border-radius:9px;background:#f7fbf9;color:#557269;font-size:.61rem;font-weight:700}
#monte #customPitch .player-ball.user-picked{position:relative}
#monte #customPitch .player-ball.user-picked:before{content:'🔒 Você';position:absolute;z-index:5;top:-5px;left:50%;transform:translateX(-50%);padding:2px 5px;border-radius:999px;background:#e6f5ee;color:#0d6547;border:1px solid #b9ddcc;font-size:.47rem;font-weight:900;white-space:nowrap;box-shadow:0 2px 6px rgba(0,0,0,.08)}
#monte #customPitch .player-ball.user-picked .ball{box-shadow:0 0 0 2px #b9ddcc,0 5px 14px rgba(0,0,0,.16)}
#monte #customPitch .player-ball .name{white-space:normal;display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:2;overflow:hidden;line-height:1.08;min-height:1.3em}
#monte #customBench{grid-template-columns:1fr!important;gap:5px!important;padding:0!important}
#monte #customBench .mini{display:grid!important;grid-template-columns:auto minmax(0,1fr) auto;grid-template-rows:auto auto;align-items:center;gap:1px 7px;min-height:0!important;padding:7px 9px!important;border-radius:11px!important;box-shadow:0 4px 12px rgba(22,69,50,.035)!important}
#monte #customBench .mini .pill{grid-column:1;grid-row:1/3;font-size:.53rem!important;padding:3px 5px!important;white-space:nowrap}
#monte #customBench .mini b{grid-column:2;margin:0!important;font-size:.73rem!important;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
#monte #customBench .mini .fixture-tag{grid-column:3;grid-row:1;font-size:.58rem!important;white-space:nowrap}
#monte #customBench .mini small.muted{grid-column:2/4;grid-row:2;font-size:.55rem!important;line-height:1.1;color:#7d8c86}
#monte #customResult>h2{font-size:.92rem;margin:14px 0 7px}
@media(max-width:800px){#monte>.controls{grid-template-columns:1fr 1fr}#monte .picker{grid-template-columns:1fr 1fr}}
@media(max-width:520px){
#monte>.hero{padding:13px 14px;margin-bottom:10px;border-radius:15px}#monte>.hero h1{font-size:1.24rem}#monte>.hero .lead{font-size:.75rem;line-height:1.38}
#monte>.controls{grid-template-columns:1fr 1fr!important;padding:9px!important;gap:6px!important;border-radius:12px!important}#monte>.controls .field label{font-size:.58rem!important}#monte>.controls input,#monte>.controls select{min-height:35px!important;font-size:.74rem!important;padding:6px 8px!important}#monte>.controls .btn{min-height:35px!important;font-size:.7rem!important;padding:6px 8px!important}
#monte .custom-help{font-size:.63rem!important;padding-bottom:5px!important}
#monte .mp-budget{grid-template-columns:repeat(3,minmax(0,1fr))!important;margin:4px 0 8px!important}#monte .mp-budget>div{padding:6px 7px!important}#monte .mp-budget>div:not(:last-child){border-right:1px solid var(--mp-line)!important;border-bottom:0!important}#monte .mp-budget small{font-size:.48rem!important}#monte .mp-budget b{font-size:.7rem!important}
#monte .picker{grid-template-columns:1fr!important;gap:6px!important;margin-top:6px!important}#monte .picker-card{padding:8px 9px!important;border-radius:12px!important}#monte .picker-card h3{font-size:.69rem!important;margin-bottom:4px!important}.mp-search{min-height:34px!important;font-size:.7rem!important}.mp-results{top:38px!important}.mp-result{padding:7px 8px!important}.mp-result b{font-size:.71rem!important}.mp-result small{font-size:.56rem!important}.mp-result strong{font-size:.66rem!important}
#monte #customResult>.grid:first-child{grid-template-columns:repeat(3,minmax(0,1fr))!important;margin-top:7px!important}#monte #customResult>.grid:first-child .card{padding:7px 7px!important}#monte #customResult>.grid:first-child .card:not(:last-child){border-right:1px solid var(--mp-line)!important;border-bottom:0!important}#monte #customResult>.grid:first-child .metric small{font-size:.49rem!important}#monte #customResult>.grid:first-child .metric b{font-size:.74rem!important;white-space:nowrap}
#monte .mp-selected-note{font-size:.56rem!important;padding:5px 7px!important}
#monte #customPitch{margin-top:8px!important}#monte #customPitch .player-ball{width:67px!important}#monte #customPitch .name{font-size:.59rem!important}#monte #customPitch .pts{font-size:.57rem!important}#monte #customPitch .fixture{font-size:.5rem!important}
#monte #customBench .mini{padding:6px 8px!important}#monte #customBench .mini b{font-size:.7rem!important}#monte #customBench .mini .fixture-tag{font-size:.55rem!important}#monte #customBench .mini small.muted{font-size:.52rem!important}
}
`;

const labels={GOL:'Goleiros',LAT:'Laterais',ZAG:'Zagueiros',MEI:'Meias',ATA:'Atacantes',TEC:'Técnico'};
const autoCaps={GOL:1,LAT:2,ZAG:3,MEI:5,ATA:3,TEC:1};
const money=v=>'C$ '+Number(v||0).toLocaleString('pt-BR',{minimumFractionDigits:2,maximumFractionDigits:2});
const pts=v=>Number(v||0).toLocaleString('pt-BR',{minimumFractionDigits:2,maximumFractionDigits:2})+' pts';
let players=[];
let refreshTimer=null;
let decorating=false;

function injectStyle(){
  let s=document.getElementById('monte-premium-style');
  if(!s){s=document.createElement('style');s.id='monte-premium-style';document.head.appendChild(s)}
  if(s.textContent!==CSS)s.textContent=CSS;
}
function norm(s){return String(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().trim()}
function setText(el,text){if(el&&el.textContent!==text)el.textContent=text}
function cardPosition(card){
  const sel=card.querySelector('select.custom-pick');
  if(sel&&sel.dataset.pos)return sel.dataset.pos;
  const h=norm(card.querySelector('h3')&&card.querySelector('h3').textContent);
  return Object.keys(labels).find(p=>h.includes(norm(labels[p])))||'';
}
function pickedEntries(){
  const out=[];
  document.querySelectorAll('#customPickers .picker-card').forEach(card=>{
    const pos=cardPosition(card);
    card.querySelectorAll('.picked-chip').forEach(ch=>{
      const named=ch.querySelector('.mp-picked-name');
      const raw=named?named.textContent:Array.from(ch.childNodes).filter(n=>n.nodeType===3).map(n=>n.textContent).join('');
      const name=String(raw||'').trim();
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
  const total=Number((document.getElementById('customBudget')||{}).value||120);
  const spent=pickedPlayers().reduce((a,p)=>a+Number(p.preco||0),0),available=total-spent;
  const html=`<div><small>Patrimônio</small><b>${money(total)}</b></div><div><small>Escolhido</small><b>${money(spent)}</b></div><div class="available"><small>Disponível</small><b>${money(available)}</b></div>`;
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
    const m=document.createElement('span');m.className='mp-picked-meta';m.textContent=`${p.sigla_clube||'—'} · ${money(p.preco)} · ${pts(p.projecao)}${Number.isFinite(Number(p.titularidade))?' · Tit. '+Math.round(Number(p.titularidade))+'%':''}`;
    ch.insertBefore(n,button||null);ch.insertBefore(m,button||null);ch.classList.add('mp-picked');ch.dataset.mpDone='1';
  });
}
function isEligible(p){const status=p&&((p.status_id!=null)?p.status_id:p.statusId);return status==null||Number(status)===7}
function searchResults(pos,q){
  const used=new Set(pickedPlayers().map(p=>String(p.atleta_id)));
  return players.filter(p=>p.posicao===pos&&isEligible(p)&&!used.has(String(p.atleta_id))&&(!q||norm(p.apelido).includes(q)||norm(p.sigla_clube).includes(q)||norm(p.sigla_adversario).includes(q))).sort((a,b)=>Number(b.projecao||0)-Number(a.projecao||0)||Number(a.preco||0)-Number(b.preco||0)).slice(0,10);
}
function venue(p){const m=p&&p.mando;return m==='casa'||m===true||m===1?'🏠':'✈️'}
function statusText(p){
  const t=Number(p&&p.titularidade);
  return Number.isFinite(t)?`Tit. ${Math.round(t)}%`:'Provável';
}
function countText(pos,picked){
  const f=document.getElementById('customFormation');
  const auto=!f||f.value==='auto';
  if(auto)return `${picked} escolhido${picked===1?'':'s'} · até ${autoCaps[pos]||1}`;
  const card=[...document.querySelectorAll('#customPickers .picker-card')].find(c=>cardPosition(c)===pos);
  const sel=card&&card.querySelector('select.custom-pick');
  const source=card&&card.querySelector('h3')?card.querySelector('h3').textContent:'';
  const match=String(source).match(/\d+\s*\/\s*(\d+)/);
  const cap=match?Number(match[1]):Number(sel&&sel.dataset.max||0);
  return cap?`${picked}/${cap}`:`${picked} escolhido${picked===1?'':'s'}`;
}
function decorate(){
  if(decorating)return;
  const root=document.getElementById('customPickers');if(!root||!players.length)return;
  decorating=true;
  try{
    root.querySelectorAll('.picker-card').forEach(card=>{
      const pos=cardPosition(card),h=card.querySelector('h3'),sel=card.querySelector('select.custom-pick');if(!pos)return;
      decoratePicked(card,pos);
      const picked=card.querySelectorAll('.picked-chip').length;
      if(h){const target=`<span>${labels[pos]}</span><span class="mp-count">${countText(pos,picked)}</span>`;if(h.innerHTML!==target)h.innerHTML=target}
      const empty=card.querySelector('.picked-list>.muted');if(empty)empty.remove();
      if(!sel||card.querySelector('.mp-search'))return;
      const row=card.querySelector('.picker-row');if(!row)return;
      sel.value='';
      const input=document.createElement('input');input.className='mp-search';input.type='search';input.placeholder=`🔎 Buscar ${labels[pos].toLowerCase()}...`;input.autocomplete='off';input.setAttribute('aria-label',`Buscar ${labels[pos].toLowerCase()}`);
      const res=document.createElement('div');res.className='mp-results';
      row.insertBefore(input,row.firstChild);input.after(res);
      const choose=button=>{
        sel.value=button.dataset.id;
        const add=card.querySelector('.add-pick');
        if(add)add.click();
        input.value='';res.classList.remove('open');scheduleRefresh(25);
      };
      const run=()=>{
        const q=norm(input.value),list=searchResults(pos,q);
        res.innerHTML=list.map(p=>`<button type="button" class="mp-result" data-id="${p.atleta_id}"><b>${p.apelido}</b><small>${p.sigla_clube||'—'} · ${venue(p)} ${p.sigla_adversario||'—'} · ${money(p.preco)} <span class="mp-status">${statusText(p)}</span></small><strong>${pts(p.projecao)}</strong></button>`).join('')||'<div class="empty" style="padding:8px;font-size:.66rem">Nenhum jogador encontrado.</div>';
        res.classList.add('open');
        res.querySelectorAll('.mp-result').forEach(b=>b.addEventListener('click',()=>choose(b)));
      };
      input.addEventListener('input',run);input.addEventListener('focus',run);input.addEventListener('keydown',e=>{if(e.key==='Escape')res.classList.remove('open');if(e.key==='Enter'){const first=res.querySelector('.mp-result');if(first){e.preventDefault();choose(first)}}});
    });
  }finally{decorating=false}
}
function markUserPicked(){
  const ids=new Set(pickedPlayers().map(p=>String(p.atleta_id)));
  document.querySelectorAll('#customPitch .player-ball').forEach(n=>n.classList.toggle('user-picked',ids.has(String(n.dataset.id))));
  const r=document.getElementById('customResult');
  if(r&&document.getElementById('customPitch')){
    let note=r.querySelector('.mp-selected-note');
    if(!note){note=document.createElement('div');note.className='mp-selected-note';const pitch=document.getElementById('customPitch');r.insertBefore(note,pitch)}
    const qtd=ids.size,total=document.querySelectorAll('#customPitch .player-ball').length;
    setText(note,qtd?`🔒 ${qtd} escolhido${qtd===1?'':'s'} por você · ${Math.max(0,total-qtd)} completado${total-qtd===1?'':'s'} pelo modelo`:'Time completado integralmente pelo modelo.');
  }
}
function compactBench(){
  document.querySelectorAll('#customBench .mini small.muted').forEach(el=>{const t=String(el.textContent||'').replace(/\s*·\s*toque para detalhes\s*$/i,'');setText(el,t)});
}
function refresh(){
  injectStyle();
  const f=document.getElementById('customFormation');if(f&&f.options[0])f.options[0].textContent='Melhor formação (automática)';
  setText(document.getElementById('buildCustom'),'Completar meu time');
  setText(document.querySelector('#monte .custom-help'),'Escolha quem você quer manter. Toque na busca e selecione o jogador; o modelo completa o restante dentro do patrimônio.');
  budgetPanel();decorate();markUserPicked();compactBench();
}
function scheduleRefresh(ms=40){clearTimeout(refreshTimer);refreshTimer=setTimeout(refresh,ms)}
async function loadPlayers(){
  try{const r=await fetch('dados.json?mp='+Date.now());if(!r.ok)throw new Error('HTTP '+r.status);const d=await r.json();players=(d.produto&&d.produto.jogadores)||[]}catch(e){console.warn('Monte Premium: dados indisponíveis',e)}
  scheduleRefresh(0);
}
document.addEventListener('input',e=>{if(e.target&&e.target.id==='customBudget')budgetPanel()});
document.addEventListener('change',e=>{if(e.target&&e.target.id==='customFormation')scheduleRefresh(30)});
document.addEventListener('click',e=>{if(e.target&&e.target.closest&&e.target.closest('#monte'))scheduleRefresh(60);if(!(e.target&&e.target.closest&&e.target.closest('.picker-card')))document.querySelectorAll('.mp-results.open').forEach(x=>x.classList.remove('open'))});
window.addEventListener('load',()=>{scheduleRefresh(120);setTimeout(refresh,500);setTimeout(refresh,1200)});
injectStyle();loadPlayers();setTimeout(refresh,350);
})();