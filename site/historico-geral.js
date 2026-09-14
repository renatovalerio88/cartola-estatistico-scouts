(function(){
'use strict';
if(typeof document==='undefined')return;

const CSS=`
#historico.history-general-active>canvas,#historico.history-general-active>.legend,#historico.history-general-active>.grid,#historico.history-general-active>.notice,#historico.history-general-active>.history-list,#historico.history-general-active>#historyAudit,#historico.history-general-active>.history-premium-root,#historico.history-general-active>.history-final-root{display:none!important}
#historico .hg-root{display:grid;gap:12px;margin-top:14px}
#historico .hg-card{background:#fff;border:1px solid var(--line);border-radius:17px;padding:15px;box-shadow:var(--shadow)}
#historico .hg-card h2{margin:0 0 4px;font-size:1rem}
#historico .hg-card p{margin:0;color:var(--muted);font-size:.78rem;line-height:1.45}
#historico .hg-chart{margin-top:10px;overflow:hidden}
#historico .hg-chart svg{display:block;width:100%;height:auto;min-height:210px}
#historico .hg-legend{display:flex;gap:14px;flex-wrap:wrap;margin-top:7px;color:var(--muted);font-size:.68rem;font-weight:750}
#historico .hg-dot{width:8px;height:8px;border-radius:50%;display:inline-block;margin-right:5px}.hg-dot.proj{background:#d97706}.hg-dot.real{background:#177245}
#historico .hg-table-wrap{overflow:auto;border:1px solid var(--line);border-radius:13px;margin-top:10px;-webkit-overflow-scrolling:touch}
#historico .hg-table{width:100%;min-width:520px;border-collapse:collapse;background:#fff}
#historico .hg-table th,#historico .hg-table td{padding:10px 11px;border-bottom:1px solid var(--line);text-align:left;font-size:.78rem;white-space:nowrap}
#historico .hg-table th{font-size:.65rem;text-transform:uppercase;color:var(--muted)}
#historico .hg-empty{padding:18px;text-align:center;color:var(--muted);font-size:.8rem}
@media(max-width:700px){#historico .hg-card{padding:13px}#historico .hg-chart svg{min-height:190px}#historico .hg-table th,#historico .hg-table td{padding:9px 8px;font-size:.72rem}}
`;

function inject(){let s=document.getElementById('history-general-style');if(!s){s=document.createElement('style');s.id='history-general-style';document.head.appendChild(s)}s.textContent=CSS}
function fmt(v){const n=Number(v);return Number.isFinite(n)?n.toLocaleString('pt-BR',{minimumFractionDigits:2,maximumFractionDigits:2}):'—'}
function data(){try{return typeof D!=='undefined'?D:{}}catch(_){return{}}}
function rows(){const x=data().backtest_time_sugerido_walk_forward||{};return Array.isArray(x.rodadas)?x.rodadas.filter(r=>Number.isFinite(Number(r.projecao))&&Number.isFinite(Number(r.pontuacao_real))).sort((a,b)=>Number(a.rodada)-Number(b.rodada)):[]}
function chart(rs){if(!rs.length)return'<div class="hg-empty">Ainda não há rodadas suficientes para montar o gráfico.</div>';const W=900,H=260,L=48,R=18,T=20,B=38;const vals=rs.flatMap(r=>[Number(r.projecao),Number(r.pontuacao_real)]);let lo=Math.min(...vals),hi=Math.max(...vals),pad=Math.max(6,(hi-lo)*.12);lo=Math.max(0,lo-pad);hi+=pad;if(hi<=lo)hi=lo+10;const x=i=>rs.length===1?(L+W-R)/2:L+i*(W-L-R)/(rs.length-1),y=v=>T+(hi-v)*(H-T-B)/(hi-lo),pts=k=>rs.map((r,i)=>`${x(i).toFixed(1)},${y(Number(r[k])).toFixed(1)}`).join(' ');let grid='',labels='',dots='';for(let i=0;i<5;i++){const yy=T+i*(H-T-B)/4,val=hi-i*(hi-lo)/4;grid+=`<line x1="${L}" y1="${yy}" x2="${W-R}" y2="${yy}" stroke="#e7eeea"/><text x="${L-7}" y="${yy+4}" text-anchor="end" font-size="10" fill="#7c8d86">${Math.round(val)}</text>`}const step=Math.max(1,Math.ceil(rs.length/9));rs.forEach((r,i)=>{if(i%step===0||i===rs.length-1)labels+=`<text x="${x(i)}" y="${H-12}" text-anchor="middle" font-size="10" fill="#7c8d86">R${r.rodada}</text>`;dots+=`<circle cx="${x(i)}" cy="${y(Number(r.projecao))}" r="3" fill="#d97706"><title>R${r.rodada} projetado: ${fmt(r.projecao)} pts</title></circle><circle cx="${x(i)}" cy="${y(Number(r.pontuacao_real))}" r="3" fill="#177245"><title>R${r.rodada} real: ${fmt(r.pontuacao_real)} pts</title></circle>`});return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Projetado versus real por rodada">${grid}<polyline points="${pts('projecao')}" fill="none" stroke="#d97706" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/><polyline points="${pts('pontuacao_real')}" fill="none" stroke="#177245" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>${dots}${labels}</svg>`}
function render(){inject();const section=document.getElementById('historico');if(!section)return;section.classList.add('history-general-active');section.querySelectorAll('.hg-root').forEach(n=>n.remove());const rs=rows(),root=document.createElement('div');root.className='hg-root';const trs=rs.map(r=>{const d=Number(r.pontuacao_real)-Number(r.projecao);return `<tr><td><b>R${r.rodada}</b></td><td>${fmt(r.projecao)}</td><td>${fmt(r.pontuacao_real)}</td><td>${d>=0?'+':''}${fmt(d)}</td></tr>`}).join('');root.innerHTML=`<div class="hg-card"><h2>Projetado × Real</h2><p>Comparação geral rodada a rodada do backtest walk-forward, sempre usando apenas informações disponíveis antes de cada rodada.</p><div class="hg-chart">${chart(rs)}</div><div class="hg-legend"><span><i class="hg-dot proj"></i>Projetado</span><span><i class="hg-dot real"></i>Real</span></div></div><div class="hg-card"><h2>Rodada por rodada</h2><p>Resumo simples da projeção do time e do resultado real.</p>${rs.length?`<div class="hg-table-wrap"><table class="hg-table"><thead><tr><th>Rodada</th><th>Projetado</th><th>Real</th><th>Diferença</th></tr></thead><tbody>${trs}</tbody></table></div>`:'<div class="hg-empty">Nenhuma rodada auditável disponível.</div>'}</div>`;section.appendChild(root)}
function schedule(){let tries=0;const tick=()=>{render();if(!rows().length&&tries++<50)setTimeout(tick,120)};tick()}
document.addEventListener('click',e=>{const b=e.target&&e.target.closest&&e.target.closest('#nav button[data-page="historico"]');if(b)setTimeout(render,0)});
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',schedule);else schedule();
})();
