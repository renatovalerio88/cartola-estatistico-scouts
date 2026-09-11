(function(){
'use strict';
if(typeof document==='undefined')return;

const CSS=`
#historico .history-premium-root{display:grid;gap:14px;margin-top:14px}
#historico .history-panel{background:#fff;border:1px solid var(--line);border-radius:18px;padding:18px;box-shadow:var(--shadow)}
#historico .history-panel h2,#historico .history-panel h3{margin:0;color:var(--text)}
#historico .history-panel p{margin:6px 0 0;color:var(--muted);font-size:.82rem;line-height:1.5}
#historico .history-head{display:flex;justify-content:space-between;gap:14px;align-items:flex-start}
#historico .history-badge{border-radius:999px;padding:5px 9px;font-size:.62rem;font-weight:850;white-space:nowrap;background:var(--brand2);color:var(--brand3)}
#historico .history-badge.audit{background:#f3f6f4;color:#687a72}
#historico .history-kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin-top:14px}
#historico .history-kpi{border:1px solid var(--line);border-radius:12px;background:#f8fbf9;padding:10px;min-width:0}
#historico .history-kpi small{display:block;font-size:.57rem;color:var(--muted);text-transform:uppercase;font-weight:850;letter-spacing:.02em}
#historico .history-kpi b{display:block;margin-top:3px;font-size:1rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
#historico .history-chart-shell{margin-top:14px;border:1px solid var(--line);border-radius:16px;padding:12px;background:linear-gradient(180deg,#fbfdfc,#fff);overflow:hidden}
#historico .history-chart-title{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:8px}
#historico .history-chart-title b{font-size:.8rem}
#historico .history-chart-title span{font-size:.62rem;color:var(--muted)}
#historico .history-chart-shell svg{display:block;width:100%;height:auto;min-height:220px}
#historico .history-chart-legend{display:flex;gap:14px;align-items:center;margin-top:6px;font-size:.65rem;color:var(--muted);font-weight:750}
#historico .history-dot{width:8px;height:8px;border-radius:50%;display:inline-block;margin-right:5px}
#historico .history-dot.projected{background:#177245}.history-dot.actual{background:#d97706}
#historico .history-note{margin-top:12px;padding:10px 12px;border-radius:12px;background:#f7faf8;border:1px solid var(--line);font-size:.7rem;color:var(--muted);line-height:1.45}
#historico .history-note strong{color:var(--text)}
#historico .history-maturity{margin-top:12px}
#historico .history-maturity-bar{height:7px;background:#edf2ef;border-radius:99px;overflow:hidden;margin:7px 0 5px}
#historico .history-maturity-bar i{display:block;height:100%;background:var(--brand);border-radius:99px}
#historico .history-comparison{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:10px}
#historico .history-comparison div{background:#f7faf8;border-radius:10px;padding:9px;border:1px solid var(--line)}
#historico .history-comparison small{display:block;color:var(--muted);font-size:.58rem;text-transform:uppercase;font-weight:800}
#historico .history-comparison b{display:block;margin-top:2px;font-size:.86rem}
#historico .history-rounds{display:grid;gap:8px;margin-top:12px}
#historico .history-round-card{border:1px solid var(--line);border-radius:14px;padding:11px 12px;background:#fff}
#historico .history-round-head{display:flex;justify-content:space-between;gap:10px;align-items:center}
#historico .history-round-head b{font-size:.86rem}.history-round-head span{font-size:.61rem;color:var(--muted);font-weight:750}
#historico .history-round-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;margin-top:8px}
#historico .history-round-grid div{border-radius:9px;background:#f7faf8;padding:7px}
#historico .history-round-grid small{display:block;font-size:.52rem;color:var(--muted);text-transform:uppercase;font-weight:800}
#historico .history-round-grid b{display:block;font-size:.76rem;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
#historico details.history-lineup{margin-top:8px;border-top:1px dashed var(--line);padding-top:7px}
#historico details.history-lineup summary{cursor:pointer;color:var(--brand);font-weight:800;font-size:.68rem;list-style:none}
#historico .history-lineup-list{display:flex;flex-wrap:wrap;gap:5px;margin-top:7px}
#historico .history-lineup-list span{font-size:.6rem;font-weight:700;background:var(--brand2);color:var(--brand3);border-radius:999px;padding:4px 7px}
#historico .history-prospective-empty{display:flex;align-items:flex-start;gap:11px}
#historico .history-prospective-icon{width:40px;height:40px;flex:0 0 40px;border-radius:12px;background:#f3f6f4;display:grid;place-items:center}
#historico.history-premium-active>canvas,#historico.history-premium-active>.legend,#historico.history-premium-active>.grid,#historico.history-premium-active>.notice,#historico.history-premium-active>.history-list,#historico.history-premium-active>#historyAudit,#historico.history-premium-active>.history-premium-wrap{display:none!important}
@media(max-width:700px){
 #historico .history-panel{padding:14px}
 #historico .history-kpis{grid-template-columns:repeat(2,minmax(0,1fr))}
 #historico .history-round-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
 #historico .history-head{display:block}
 #historico .history-badge{display:inline-block;margin-top:8px}
 #historico .history-chart-title{display:block}.history-chart-title span{display:block;margin-top:3px}
 #historico .history-chart-shell svg{min-height:190px}
}
`;

function injectStyle(){let s=document.getElementById('history-premium-style');if(!s){s=document.createElement('style');s.id='history-premium-style';document.head.appendChild(s)}s.textContent=CSS}
function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function fmt(v,d=2){const n=Number(v);return Number.isFinite(n)?n.toLocaleString('pt-BR',{minimumFractionDigits:d,maximumFractionDigits:d}):'—'}
function mean(xs){const a=xs.map(Number).filter(Number.isFinite);return a.length?a.reduce((x,y)=>x+y,0)/a.length:null}
function data(){try{return typeof D!=='undefined'?D:{}}catch(_){return{}}}
function walk(){const x=data().backtest_time_sugerido_walk_forward||{};return Array.isArray(x.rodadas)?x:null}
function prospective(){const a=data().avaliacao_prospectiva_imutavel||{};const rows=Array.isArray(a.times_sugeridos)?a.times_sugeridos:[];return rows.filter(r=>r&&r.entra_no_historico_publico===true&&r.status==='AVALIADA')}

function maturity(n){if(n<5)return['Amostra inicial',25];if(n<10)return['Amostra em formação',45];if(n<20)return['Amostra moderada',70];return['Amostra mais robusta',100]}

function chartSvg(rows){
 const W=900,H=275,L=48,R=18,T=22,B=38;
 const vals=rows.flatMap(r=>[Number(r.projecao),Number(r.pontuacao_real)]).filter(Number.isFinite);
 if(!vals.length)return'';
 let lo=Math.min(...vals),hi=Math.max(...vals);let pad=Math.max(8,(hi-lo)*.14);lo=Math.max(0,lo-pad);hi+=pad;if(hi<=lo)hi=lo+10;
 const x=i=>rows.length===1?(L+(W-R))/2:L+i*(W-L-R)/(rows.length-1);
 const y=v=>T+(hi-v)*(H-T-B)/(hi-lo);
 const pts=k=>rows.map((r,i)=>`${x(i).toFixed(1)},${y(Number(r[k])).toFixed(1)}`).join(' ');
 let grid='';for(let i=0;i<5;i++){const yy=T+i*(H-T-B)/4;const val=hi-i*(hi-lo)/4;grid+=`<line x1="${L}" y1="${yy}" x2="${W-R}" y2="${yy}" stroke="#e8eeeb" stroke-width="1"/><text x="${L-7}" y="${yy+4}" text-anchor="end" font-size="10" fill="#7a8b84">${Math.round(val)}</text>`}
 let labels='';const step=Math.max(1,Math.ceil(rows.length/9));rows.forEach((r,i)=>{if(i%step===0||i===rows.length-1)labels+=`<text x="${x(i)}" y="${H-12}" text-anchor="middle" font-size="10" fill="#7a8b84">R${r.rodada}</text>`});
 let dots='';rows.forEach((r,i)=>{dots+=`<circle cx="${x(i)}" cy="${y(Number(r.projecao))}" r="3.2" fill="#177245"><title>R${r.rodada} projetado: ${fmt(r.projecao)} pts</title></circle><circle cx="${x(i)}" cy="${y(Number(r.pontuacao_real))}" r="3.2" fill="#d97706"><title>R${r.rodada} real: ${fmt(r.pontuacao_real)} pts</title></circle>`});
 return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Gráfico de linhas da pontuação projetada e real por rodada">${grid}<polyline points="${pts('projecao')}" fill="none" stroke="#177245" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/><polyline points="${pts('pontuacao_real')}" fill="none" stroke="#d97706" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>${dots}${labels}</svg>`;
}

function lineup(r){const arr=Array.isArray(r.jogadores)?r.jogadores:[];if(!arr.length)return'';return `<details class="history-lineup"><summary>Ver XI reconstruído no corte temporal</summary><div class="history-lineup-list">${arr.map(p=>`<span>${p.capitao?'© ':''}${esc(p.apelido)} · ${esc(p.posicao)}</span>`).join('')}</div></details>`}

function renderWalk(payload){
 const rows=payload.rodadas.slice().sort((a,b)=>Number(a.rodada)-Number(b.rodada));
 const k=payload.kpis||{};const [mLabel,mPct]=maturity(rows.length);
 const last5=rows.slice(-5);const mae5=mean(last5.map(r=>r.erro_abs));const maeAll=Number(k.erro_medio_absoluto);
 const compare=rows.length>=10?`<div class="history-comparison"><div><small>Erro · últimas 5</small><b>${fmt(mae5)} pts</b></div><div><small>Erro · temporada avaliada</small><b>${fmt(maeAll)} pts</b></div></div>`:'';
 const missing=payload.escopo?.indisponiveis_antes_do_modelo||[];
 return `<div class="history-panel">
  <div class="history-head"><div><h2>Evolução do modelo · Projetado × Real</h2><p>Backtest <b>walk-forward</b>: cada rodada é projetada usando somente informações disponíveis antes dela. O resultado da própria rodada entra apenas depois, para medir o erro.</p></div><span class="history-badge">Sem vazamento temporal</span></div>
  <div class="history-kpis"><div class="history-kpi"><small>Rodadas avaliadas</small><b>${rows.length}</b></div><div class="history-kpi"><small>Média projetada</small><b>${fmt(k.media_projetada)} pts</b></div><div class="history-kpi"><small>Média real</small><b>${fmt(k.media_real)} pts</b></div><div class="history-kpi"><small>Erro médio absoluto</small><b>${fmt(k.erro_medio_absoluto)} pts</b></div></div>
  <div class="history-chart-shell"><div class="history-chart-title"><b>Projetado × Real por rodada</b><span>Quanto mais próximas as linhas, maior a aderência da projeção do XI.</span></div>${chartSvg(rows)}<div class="history-chart-legend"><span><i class="history-dot projected"></i>Projetado</span><span><i class="history-dot actual"></i>Real</span></div></div>
  <div class="history-maturity"><p><b>${mLabel}.</b> A maturidade abaixo representa apenas o tamanho da amostra, não uma nota científica do modelo.</p><div class="history-maturity-bar"><i style="width:${mPct}%"></i></div></div>${compare}
  <div class="history-note"><strong>Leitura metodológica:</strong> este é um backtest histórico, não uma afirmação de que esses times foram publicados naquela data. ${missing.length?`A série começa na <b>R${rows[0].rodada}</b>; R${missing[0]}–R${missing[missing.length-1]} não são preenchidas artificialmente porque a arquitetura V3H atual exige histórico mínimo de treino.`:''} Os snapshots antigos também não preservam preço e status pré-rodada com confiabilidade; por isso orçamento/status provável não são reconstruídos neste bloco. A prova prospectiva real permanece separada abaixo.</div>
 </div>
 <div class="history-panel"><div class="history-head"><div><h3>Rodada a rodada</h3><p>Abra uma rodada para conferir o XI escolhido pelo corte temporal e o capitão.</p></div><span class="history-badge audit">Backtest auditável</span></div><div class="history-rounds">${rows.slice().reverse().map(r=>{const err=Number(r.pontuacao_real)-Number(r.projecao);return `<div class="history-round-card"><div class="history-round-head"><b>Rodada ${r.rodada}</b><span>${esc(r.formacao||'')}</span></div><div class="history-round-grid"><div><small>Projetado</small><b>${fmt(r.projecao)} pts</b></div><div><small>Real</small><b>${fmt(r.pontuacao_real)} pts</b></div><div><small>Erro</small><b>${Number.isFinite(err)?`${err>=0?'+':''}${fmt(err)}`:'—'} pts</b></div><div><small>Capitão</small><b>${esc(r.capitao?.apelido||'—')}</b></div></div>${lineup(r)}</div>`}).join('')}</div></div>`;
}

function renderProspective(){
 const rows=prospective();
 if(!rows.length)return `<div class="history-panel"><div class="history-prospective-empty"><div class="history-prospective-icon">🔒</div><div><h3>Histórico prospectivo publicado</h3><p>Ainda não há rodada com escalação comprovadamente congelada em mercado aberto e depois avaliada. Esta seção começará automaticamente quando existir a primeira prova prospectiva válida. Backtest e histórico publicado continuam separados.</p></div></div></div>`;
 const proj=mean(rows.map(r=>r.projecao)),real=mean(rows.map(r=>r.pontuacao_real)),mae=mean(rows.map(r=>Math.abs(Number(r.pontuacao_real)-Number(r.projecao))));
 return `<div class="history-panel"><div class="history-head"><div><h3>Histórico prospectivo publicado</h3><p>Somente escalações realmente congeladas antes do fechamento do mercado.</p></div><span class="history-badge">Prova prospectiva</span></div><div class="history-kpis"><div class="history-kpi"><small>Rodadas</small><b>${rows.length}</b></div><div class="history-kpi"><small>Média projetada</small><b>${fmt(proj)} pts</b></div><div class="history-kpi"><small>Média real</small><b>${fmt(real)} pts</b></div><div class="history-kpi"><small>Erro médio</small><b>${fmt(mae)} pts</b></div></div></div>`;
}

function renderWaiting(){return `<div class="history-panel"><div class="history-prospective-empty"><div class="history-prospective-icon">📈</div><div><h2>Histórico estatístico sendo preparado</h2><p>O relatório walk-forward ainda não chegou ao payload publicado. Nenhum ponto é inventado enquanto os dados auditáveis não estiverem disponíveis.</p></div></div></div>`}

function run(){
 injectStyle();const section=document.getElementById('historico');if(!section)return;
 const payload=walk();const signature=payload?`${payload.gerado_em||''}:${payload.rodadas.length}`:'waiting';
 const current=section.querySelector('.history-premium-root');if(current&&current.dataset.signature===signature)return;
 if(current)current.remove();section.classList.add('history-premium-active');
 const root=document.createElement('div');root.className='history-premium-root';root.dataset.signature=signature;root.innerHTML=(payload?renderWalk(payload):renderWaiting())+renderProspective();
 const hero=section.querySelector('.hero');if(hero&&hero.nextSibling)section.insertBefore(root,hero.nextSibling);else section.appendChild(root);
}

let tries=0;const timer=setInterval(()=>{run();if(++tries>60)clearInterval(timer)},400);
document.addEventListener('click',e=>{if(e.target.closest&&e.target.closest('[data-page="historico"]'))setTimeout(run,100)});
run();
})();
