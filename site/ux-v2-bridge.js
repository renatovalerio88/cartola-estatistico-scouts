(function(){
'use strict';
if(typeof document==='undefined')return;

const POS_LABEL={GOL:'Goleiro',LAT:'Lateral',ZAG:'Zagueiro',MEI:'Meia',ATA:'Atacante',TEC:'Técnico'};
const MAX_BY_POS={GOL:1,LAT:2,ZAG:3,MEI:5,ATA:3,TEC:1};
let players=[];
let activeModal=null;

const css=`
#uxv2-modal{position:fixed;inset:0;background:rgba(8,25,17,.58);display:none;align-items:flex-end;justify-content:center;z-index:120;padding:0}
#uxv2-modal.open{display:flex}
#uxv2-modal .uxv2-sheet{width:min(720px,100%);max-height:86vh;background:#fff;border-radius:24px 24px 0 0;box-shadow:0 -24px 70px rgba(0,0,0,.22);overflow:hidden;display:flex;flex-direction:column}
#uxv2-modal .uxv2-head{display:flex;justify-content:space-between;align-items:center;padding:16px 18px;border-bottom:1px solid #dfe9e4;gap:12px}
#uxv2-modal .uxv2-kicker{font-size:.68rem;color:#176b4b;font-weight:900;text-transform:uppercase;letter-spacing:.06em}
#uxv2-modal h3{margin:2px 0 0;font-size:1.05rem;color:#183128}
#uxv2-modal .uxv2-close{border:0;background:#eef4f1;color:#29453b;width:38px;height:38px;border-radius:50%;font-size:1.2rem;font-weight:900;cursor:pointer}
#uxv2-modal .uxv2-search{display:grid;grid-template-columns:1fr auto;gap:8px;padding:12px 16px;border-bottom:1px solid #edf2ef}
#uxv2-modal .uxv2-search input{min-width:0;width:100%}
#uxv2-modal .uxv2-list{overflow:auto;padding:0 16px 18px}
#uxv2-modal .uxv2-row{width:100%;border:0;border-bottom:1px solid #edf2ef;background:#fff;padding:12px 2px;display:grid;grid-template-columns:minmax(0,1fr) auto;gap:3px 10px;text-align:left;cursor:pointer}
#uxv2-modal .uxv2-row b{font-size:.9rem;color:#183128;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
#uxv2-modal .uxv2-row small{font-size:.72rem;color:#72857d}
#uxv2-modal .uxv2-row strong{grid-row:1/3;grid-column:2;align-self:center;color:#176b4b;font-size:.82rem;white-space:nowrap}
#uxv2-modal .uxv2-empty{padding:24px 4px;text-align:center;color:#72857d}
#monte .picker-card{cursor:pointer;position:relative}
#monte .picker-card:after{content:'Toque para escolher';position:absolute;right:10px;bottom:7px;font-size:.48rem;color:#8a9b94;font-weight:800}
#monte .picker-card.has-choice:after{content:'Toque para alterar'}
#historico .uxv2-history-table{margin-top:14px}
#historico .uxv2-history-table table{min-width:0;width:100%}
#historico .uxv2-history-table th,#historico .uxv2-history-table td{padding:9px 10px;font-size:.78rem}
#historico .uxv2-history-table th{font-size:.66rem}
#historico .uxv2-diff.pos{color:#176b4b;font-weight:900}#historico .uxv2-diff.neg{color:#b84f4f;font-weight:900}
#historico .uxv2-history-note{margin-top:8px;color:#72857d;font-size:.72rem}
@media(min-width:701px){#uxv2-modal{align-items:center;padding:20px}#uxv2-modal .uxv2-sheet{border-radius:22px;max-height:78vh}}
`;

function style(){if(document.getElementById('uxv2-style'))return;const s=document.createElement('style');s.id='uxv2-style';s.textContent=css;document.head.appendChild(s)}
function norm(s){return String(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().trim()}
function pts(v){return Number(v||0).toLocaleString('pt-BR',{minimumFractionDigits:1,maximumFractionDigits:1})+' pts'}
function money(v){return 'C$ '+Number(v||0).toLocaleString('pt-BR',{minimumFractionDigits:2,maximumFractionDigits:2})}
function validStatus(p){const n=Number(p&&p.status_id);return !Number.isFinite(n)||[2,5,6,7].includes(n)}
function byPos(pos){return players.filter(p=>p.posicao===pos&&validStatus(p)).sort((a,b)=>Number(b.projecao||0)-Number(a.projecao||0)||Number(b.titularidade||0)-Number(a.titularidade||0))}

function ensureModal(){
 if(document.getElementById('uxv2-modal'))return;
 const el=document.createElement('div');el.id='uxv2-modal';el.innerHTML=`<div class="uxv2-sheet" role="dialog" aria-modal="true"><div class="uxv2-head"><div><div class="uxv2-kicker" id="uxv2-kicker">POSIÇÃO</div><h3 id="uxv2-title">Escolher jogador</h3></div><button class="uxv2-close" aria-label="Fechar">×</button></div><div class="uxv2-search"><input id="uxv2-query" placeholder="Buscar jogador ou clube"><button class="btn" id="uxv2-search-btn">Pesquisar</button></div><div class="uxv2-list" id="uxv2-list"></div></div>`;document.body.appendChild(el);
 el.addEventListener('click',e=>{if(e.target===el||e.target.closest('.uxv2-close'))closeModal()});
 document.getElementById('uxv2-query').addEventListener('input',renderModal);
 document.getElementById('uxv2-search-btn').addEventListener('click',renderModal);
}
function closeModal(){const el=document.getElementById('uxv2-modal');if(el)el.classList.remove('open');activeModal=null}
function renderModal(){
 if(!activeModal)return;const q=norm((document.getElementById('uxv2-query')||{}).value||'');
 const list=document.getElementById('uxv2-list');const arr=byPos(activeModal.pos).filter(p=>!q||norm(p.apelido).includes(q)||norm(p.sigla_clube).includes(q)||norm(p.sigla_adversario).includes(q)).slice(0,80);
 if(!arr.length){list.innerHTML='<div class="uxv2-empty">Nenhum jogador encontrado.</div>';return}
 list.innerHTML=arr.map((p,i)=>`<button class="uxv2-row" data-idx="${i}"><b>${p.apelido||'—'}</b><small>${p.sigla_clube||'—'} · ${money(p.preco)} · Tit. ${Math.round(Number(p.titularidade||0))}%</small><strong>${pts(p.projecao)}</strong></button>`).join('');
 list.querySelectorAll('.uxv2-row').forEach((btn,i)=>btn.addEventListener('click',()=>choose(arr[i])));
}
function choose(p){
 const card=activeModal&&activeModal.card;if(!card)return;
 const sel=card.querySelector('select.custom-pick');if(sel){
   let opt=Array.from(sel.options).find(o=>String(o.value)===String(p.atleta_id)||norm(o.textContent).includes(norm(p.apelido)));
   if(!opt){opt=document.createElement('option');opt.value=String(p.atleta_id);opt.textContent=p.apelido;sel.appendChild(opt)}
   sel.value=opt.value;sel.dispatchEvent(new Event('change',{bubbles:true}));
 }
 closeModal();setTimeout(()=>decorateCards(),120);
}
function openCard(card){
 const sel=card.querySelector('select.custom-pick');const pos=(sel&&sel.dataset.pos)||detectPos(card);if(!pos)return;
 activeModal={card,pos};ensureModal();document.getElementById('uxv2-kicker').textContent=pos;document.getElementById('uxv2-title').textContent='Escolher '+(POS_LABEL[pos]||'jogador');document.getElementById('uxv2-query').value='';document.getElementById('uxv2-modal').classList.add('open');renderModal();setTimeout(()=>document.getElementById('uxv2-query').focus(),40);
}
function detectPos(card){const t=norm((card.querySelector('h3')||{}).textContent||'');return Object.keys(POS_LABEL).find(k=>t.includes(norm(POS_LABEL[k]))||t.includes(norm({GOL:'goleiros',LAT:'laterais',ZAG:'zagueiros',MEI:'meias',ATA:'atacantes',TEC:'técnico'}[k])))||''}
function decorateCards(){document.querySelectorAll('#monte .picker-card').forEach(card=>{if(card.dataset.uxv2==='1')return;card.dataset.uxv2='1';card.addEventListener('click',e=>{if(e.target.closest('button')||e.target.closest('input'))return;openCard(card)});const inp=card.querySelector('input.mp-search');if(inp){inp.setAttribute('readonly','readonly');inp.placeholder='Toque para escolher...';inp.addEventListener('click',e=>{e.preventDefault();openCard(card)})}})}

function enhanceHistory(){
 const hist=document.getElementById('historico');if(!hist||hist.dataset.uxv2History==='1')return;
 const data=window.__CARTOLA_DADOS__||window.CARTOLA_DADOS||null;
 let series=[];
 try{
  const d=data||JSON.parse(localStorage.getItem('__cartola_dados_cache__')||'null');
  const raw=d&&d.backtest_time_sugerido_walk_forward;
  const cand=(raw&&raw.rodadas)||raw?.resultados||raw?.historico||[];
  if(Array.isArray(cand))series=cand.map(r=>({rodada:Number(r.rodada||r.round||r.r),projetado:Number(r.projecao||r.projetado||r.pontos_projetados||r.projecao_time||0),real:Number(r.real||r.pontos_reais||r.pontuacao_real||r.real_final||0)})).filter(x=>x.rodada&&Number.isFinite(x.projetado)&&Number.isFinite(x.real));
 }catch(_){ }
 if(!series.length)return;
 const target=Array.from(hist.querySelectorAll('canvas')).pop();if(!target)return;
 const box=target.closest('.card')||target.parentElement;const wrap=document.createElement('div');wrap.className='uxv2-history-table scroll';wrap.innerHTML=`<table><thead><tr><th>Rodada</th><th>Projetado</th><th>Real</th><th>Diferença</th></tr></thead><tbody>${series.map(r=>{const d=r.real-r.projetado;return `<tr><td>R${r.rodada}</td><td>${pts(r.projetado)}</td><td>${pts(r.real)}</td><td class="uxv2-diff ${d>=0?'pos':'neg'}">${d>=0?'+':''}${d.toLocaleString('pt-BR',{minimumFractionDigits:1,maximumFractionDigits:1})}</td></tr>`}).join('')}</tbody></table>`;box.appendChild(wrap);const note=document.createElement('div');note.className='uxv2-history-note';note.textContent='Tabela analítica do mesmo gráfico: rodada, projeção pré-rodada, resultado real e diferença.';box.appendChild(note);hist.dataset.uxv2History='1';
}
async function load(){
 try{const r=await fetch('dados.json?uxv2='+Date.now());const d=await r.json();window.__CARTOLA_DADOS__=d;players=(d.produto&&d.produto.jogadores)||[];try{localStorage.setItem('__cartola_dados_cache__',JSON.stringify({backtest_time_sugerido_walk_forward:d.backtest_time_sugerido_walk_forward}))}catch(_){}}
 catch(e){console.warn('UX V2 bridge: falha ao carregar dados',e)}
 decorateCards();enhanceHistory();
}
style();ensureModal();load();
new MutationObserver(()=>{decorateCards();enhanceHistory()}).observe(document.documentElement,{subtree:true,childList:true});
})();
