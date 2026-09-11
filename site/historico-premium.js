(function(){
'use strict';
if(typeof document==='undefined')return;

const CSS=`
#historico .history-premium-wrap{display:grid;gap:14px}
#historico .history-empty-premium,
#historico .history-audit-premium,
#historico .history-maturity-premium,
#historico .history-future-premium{background:#fff;border:1px solid var(--line);border-radius:18px;padding:18px;box-shadow:var(--shadow)}
#historico .history-empty-premium{padding:22px;background:linear-gradient(180deg,#fbfdfc,#fff)}
#historico .history-empty-premium h2,
#historico .history-audit-premium h3,
#historico .history-maturity-premium h3,
#historico .history-future-premium h3{margin:0 0 7px;color:var(--text)}
#historico .history-empty-premium p,
#historico .history-audit-premium p,
#historico .history-maturity-premium p,
#historico .history-future-premium p{margin:0;color:var(--muted);font-size:.88rem;line-height:1.5}
#historico .history-empty-icon{width:46px;height:46px;border-radius:14px;background:var(--brand2);display:grid;place-items:center;font-size:1.35rem;margin-bottom:12px}
#historico .history-steps{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-top:15px}
#historico .history-step{border:1px solid var(--line);border-radius:12px;padding:10px;background:#f8fbf9}
#historico .history-step b{display:block;font-size:.74rem;margin-bottom:3px}
#historico .history-step small{font-size:.65rem;color:var(--muted);line-height:1.35;display:block}
#historico .history-kpi-preview{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:0;border:1px solid var(--line);border-radius:16px;overflow:hidden;background:#fff}
#historico .history-kpi-preview .history-kpi-cell{padding:12px 14px;min-width:0}
#historico .history-kpi-preview .history-kpi-cell:not(:last-child){border-right:1px solid var(--line)}
#historico .history-kpi-preview small{font-size:.61rem;color:var(--muted);text-transform:uppercase;font-weight:800;letter-spacing:.025em}
#historico .history-kpi-preview b{display:block;font-size:.98rem;margin-top:3px;line-height:1.2}
#historico .history-kpi-preview .locked{color:#8b9994;font-weight:750}
#historico .history-audit-head{display:flex;justify-content:space-between;gap:12px;align-items:start}
#historico .history-audit-badge{background:#f3f6f4;border-radius:999px;padding:5px 8px;font-size:.66rem;font-weight:850;color:#6e8078;white-space:nowrap}
#historico .history-maturity-bar{height:8px;background:#edf2ef;border-radius:99px;margin:10px 0 6px;overflow:hidden}
#historico .history-maturity-bar i{display:block;height:100%;width:0;background:var(--brand);border-radius:99px}
#historico .history-chart-head{display:flex;justify-content:space-between;align-items:end;gap:12px;margin:18px 2px 8px}
#historico .history-chart-head h2{margin:0;font-size:1.05rem;color:var(--text)}
#historico .history-chart-head span{font-size:.68rem;color:var(--muted);text-align:right}
#historico .history-future-kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin-top:13px}
#historico .history-future-kpi{border:1px solid var(--line);background:#f8fbf9;border-radius:12px;padding:10px;min-width:0}
#historico .history-future-kpi small{display:block;font-size:.58rem;color:var(--muted);text-transform:uppercase;font-weight:800;letter-spacing:.025em}
#historico .history-future-kpi b{display:block;font-size:1rem;margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
#historico .history-rounds{display:grid;gap:8px;margin-top:14px}
#historico .history-round-card{border:1px solid var(--line);border-radius:14px;padding:12px;background:#fff}
#historico .history-round-head{display:flex;justify-content:space-between;align-items:center;gap:10px}
#historico .history-round-head b{font-size:.9rem}
#historico .history-round-head span{font-size:.66rem;color:var(--muted);font-weight:750}
#historico .history-round-metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px;margin-top:8px}
#historico .history-round-metrics div{background:#f7faf8;border-radius:9px;padding:7px 8px}
#historico .history-round-metrics small{display:block;font-size:.55rem;color:var(--muted);text-transform:uppercase;font-weight:800}
#historico .history-round-metrics b{display:block;font-size:.82rem;margin-top:2px}
#historico .history-lineup-details{margin-top:8px;border-top:1px dashed var(--line);padding-top:8px}
#historico .history-lineup-details summary{cursor:pointer;color:var(--brand);font-size:.7rem;font-weight:800;list-style:none}
#historico .history-lineup-list{display:flex;gap:5px;flex-wrap:wrap;margin-top:7px}
#historico .history-lineup-list span{background:var(--brand2);color:var(--brand3);border-radius:999px;padding:4px 7px;font-size:.62rem;font-weight:700}
#historico.history-premium-empty>canvas,
#historico.history-premium-empty>.legend,
#historico.history-premium-empty>.grid,
#historico.history-premium-empty>.notice,
#historico.history-premium-empty>.history-list,
#historico.history-premium-empty>#historyAudit{display:none!important}
#historico.history-premium-ready>#historyAudit{display:none!important}
@media(max-width:700px){
  #historico .history-steps{grid-template-columns:1fr}
  #historico .history-kpi-preview{grid-template-columns:1fr 1fr 1fr}
  #historico .history-kpi-preview .history-kpi-cell{padding:10px 8px}
  #historico .history-kpi-preview small{font-size:.52rem}
  #historico .history-kpi-preview b{font-size:.78rem}
  #historico .history-future-kpis{grid-template-columns:repeat(2,minmax(0,1fr))}
  #historico .history-round-metrics{grid-template-columns:repeat(3,minmax(0,1fr))}
  #historico .history-chart-head{align-items:start}
  #historico .history-chart-head span{max-width:145px}
  .history-empty-premium,.history-audit-premium,.history-maturity-premium,.history-future-premium{padding:14px!important}
  #historico .history-empty-premium{padding:17px!important}
}
`;

function injectStyle(){
  let s=document.getElementById('history-premium-style');
  if(!s){s=document.createElement('style');s.id='history-premium-style';document.head.appendChild(s)}
  s.textContent=CSS;
}

function numAfter(text,label){
  const m=text.match(new RegExp(label+'\\s*(\\d+)','i'));
  return m?Number(m[1]):null;
}

function findCounts(section){
  const text=(section.innerText||'').replace(/\s+/g,' ');
  return{
    valid:numAfter(text,'Rodadas avaliadas'),
    waiting:numAfter(text,'Aguardando'),
    rejected:numAfter(text,'Rejeitados pela auditoria')
  };
}

function sourceTeams(){
  try{
    if(typeof D==='undefined')return[];
    const a=D.avaliacao_prospectiva_imutavel||{};
    return Array.isArray(a.times_sugeridos)?a.times_sugeridos:[];
  }catch(_){return[]}
}

function publicTeams(){
  return sourceTeams().filter(r=>r&&r.entra_no_historico_publico===true);
}

function evaluatedTeams(){
  return publicTeams().filter(r=>r.status==='AVALIADA');
}

function rejectedCount(){
  return sourceTeams().filter(r=>!r||r.entra_no_historico_publico!==true).length;
}

function fmtNum(v,d=2){
  const n=Number(v);
  return Number.isFinite(n)?n.toLocaleString('pt-BR',{minimumFractionDigits:d,maximumFractionDigits:d}):'—';
}

function mean(values){
  const xs=values.map(Number).filter(Number.isFinite);
  return xs.length?xs.reduce((a,b)=>a+b,0)/xs.length:null;
}

function lineupOf(r){
  const candidates=[r?.jogadores,r?.escalacao,r?.time,r?.atletas,r?.titulares];
  const arr=candidates.find(Array.isArray)||[];
  return arr.map(x=>{
    if(typeof x==='string')return x;
    return x?.apelido||x?.nome||x?.nome_atleta||x?.atleta||null;
  }).filter(Boolean);
}

function renderEmpty(section,counts){
  if(section.querySelector('.history-premium-wrap'))return;
  section.classList.add('history-premium-empty');
  section.classList.remove('history-premium-ready');
  const rejected=Number.isFinite(counts.rejected)?counts.rejected:rejectedCount();
  const wrap=document.createElement('div');
  wrap.className='history-premium-wrap';
  wrap.innerHTML=`
  <div class="history-empty-premium">
    <div class="history-empty-icon">📈</div>
    <h2>Histórico ainda em formação</h2>
    <p>A vitrine pública só começa quando existe uma escalação congelada <b>antes do fechamento do mercado</b> e a pontuação real pode ser comparada com aquela mesma escolha. Não reconstruímos times depois da rodada para preencher o histórico.</p>
    <div class="history-steps">
      <div class="history-step"><b>1 · Congelar</b><small>Time sugerido salvo com mercado aberto.</small></div>
      <div class="history-step"><b>2 · Validar</b><small>Auditoria confirma a prova prospectiva.</small></div>
      <div class="history-step"><b>3 · Comparar</b><small>Projeção e pontuação real entram na vitrine.</small></div>
    </div>
  </div>
  <div class="history-maturity-premium">
    <h3>Maturidade da amostra</h3>
    <p><b>Amostra insuficiente.</b> Ainda não há rodada prospectiva válida para avaliar desempenho público. A leitura de evolução só será exibida quando houver base suficiente.</p>
    <div class="history-maturity-bar"><i></i></div>
    <p style="font-size:.72rem">0 rodadas válidas · sem conclusões de performance</p>
  </div>
  <div class="history-kpi-preview">
    <div class="history-kpi-cell"><small>Rodadas válidas</small><b>0</b></div>
    <div class="history-kpi-cell"><small>Projetado × Real</small><b class="locked">Aguardando</b></div>
    <div class="history-kpi-cell"><small>Erro médio</small><b class="locked">Aguardando</b></div>
  </div>
  <div class="history-audit-premium">
    <div class="history-audit-head">
      <div><h3>Qualidade dos dados</h3><p>${rejected?`Há <b>${rejected}</b> snapshot${rejected===1?'':'s'} preservado${rejected===1?'':'s'} para auditoria, mas excluído${rejected===1?'':'s'} da vitrine por não possuir prova prospectiva suficiente.`:'Nenhum snapshot rejeitado identificado nesta leitura.'} Isso protege o histórico contra vazamento temporal.</p></div>
      <span class="history-audit-badge">Auditoria ativa</span>
    </div>
  </div>`;
  const hero=section.querySelector('.hero');
  if(hero&&hero.nextSibling)section.insertBefore(wrap,hero.nextSibling);else section.appendChild(wrap);
}

function ensureChartHead(section){
  const canvas=section.querySelector('#historyChart');
  const legend=section.querySelector('.legend');
  if(!canvas||section.querySelector('.history-chart-head'))return;
  const head=document.createElement('div');
  head.className='history-chart-head';
  head.innerHTML='<h2>Projetado × Real por rodada</h2><span>Linhas exibem somente rodadas com prova prospectiva válida.</span>';
  section.insertBefore(head,legend||canvas);
}

function renderFuture(section,valid){
  section.classList.remove('history-premium-empty');
  section.classList.add('history-premium-ready');
  const old=section.querySelector('.history-premium-wrap');
  if(old)old.remove();
  ensureChartHead(section);
  const evaluated=evaluatedTeams();
  const projected=evaluated.map(r=>r.projecao);
  const actual=evaluated.map(r=>r.pontuacao_real);
  const errors=evaluated.map(r=>Math.abs(Number(r.pontuacao_real)-Number(r.projecao))).filter(Number.isFinite);
  const avgProj=mean(projected),avgReal=mean(actual),mae=mean(errors);
  const diffs=evaluated.map(r=>({r,d:Number(r.pontuacao_real)-Number(r.projecao)})).filter(x=>Number.isFinite(x.d));
  const best=diffs.length?diffs.slice().sort((a,b)=>b.d-a.d)[0]:null;
  const worst=diffs.length?diffs.slice().sort((a,b)=>a.d-b.d)[0]:null;
  let label=valid<5?'Amostra inicial':valid<10?'Amostra em formação':valid<20?'Amostra moderada':'Amostra mais robusta';
  const pct=Math.min(100,valid/20*100);
  const wrap=document.createElement('div');
  wrap.className='history-premium-wrap history-future-wrap';
  wrap.innerHTML=`
    <div class="history-maturity-premium">
      <h3>Maturidade da amostra</h3>
      <p><b>${label}</b> · ${valid} rodada${valid===1?'':'s'} prospectiva${valid===1?'':'s'} validada${valid===1?'':'s'}.</p>
      <div class="history-maturity-bar"><i style="width:${pct}%"></i></div>
      <p style="font-size:.72rem">A maturidade indica apenas tamanho de amostra; não é uma nota de qualidade do modelo.</p>
    </div>
    <div class="history-future-premium">
      <h3>Desempenho prospectivo</h3>
      <p>Resumo calculado somente com rodadas congeladas antes do fechamento e já avaliadas.</p>
      <div class="history-future-kpis">
        <div class="history-future-kpi"><small>Rodadas avaliadas</small><b>${evaluated.length}</b></div>
        <div class="history-future-kpi"><small>Média projetada</small><b>${fmtNum(avgProj)} pts</b></div>
        <div class="history-future-kpi"><small>Média real</small><b>${fmtNum(avgReal)} pts</b></div>
        <div class="history-future-kpi"><small>Erro médio absoluto</small><b>${fmtNum(mae)} pts</b></div>
      </div>
      ${(best||worst)?`<div class="history-future-kpis" style="grid-template-columns:repeat(2,minmax(0,1fr))"><div class="history-future-kpi"><small>Melhor diferença</small><b>${best?`R${best.r.rodada} · ${best.d>=0?'+':''}${fmtNum(best.d)}`:'—'}</b></div><div class="history-future-kpi"><small>Pior diferença</small><b>${worst?`R${worst.r.rodada} · ${worst.d>=0?'+':''}${fmtNum(worst.d)}`:'—'}</b></div></div>`:''}
      <div class="history-rounds">${evaluated.slice().sort((a,b)=>Number(b.rodada)-Number(a.rodada)).map(r=>{
        const diff=Number(r.pontuacao_real)-Number(r.projecao);
        const names=lineupOf(r);
        return `<div class="history-round-card"><div class="history-round-head"><b>Rodada ${r.rodada}</b><span>${r.formacao||'Formação não informada'}</span></div><div class="history-round-metrics"><div><small>Projetado</small><b>${fmtNum(r.projecao)} pts</b></div><div><small>Real</small><b>${fmtNum(r.pontuacao_real)} pts</b></div><div><small>Diferença</small><b>${Number.isFinite(diff)?`${diff>=0?'+':''}${fmtNum(diff)}`:'—'}</b></div></div>${names.length?`<details class="history-lineup-details"><summary>Ver escalação congelada</summary><div class="history-lineup-list">${names.map(n=>`<span>${String(n).replace(/[<>&]/g,'')}</span>`).join('')}</div></details>`:''}</div>`;
      }).join('')}</div>
    </div>`;
  const canvas=section.querySelector('#historyChart');
  if(canvas)canvas.insertAdjacentElement('afterend',wrap);else section.appendChild(wrap);
}

function run(){
  injectStyle();
  const section=document.getElementById('historico');
  if(!section)return;
  const teams=publicTeams();
  const c=findCounts(section);
  const valid=teams.length||c.valid||0;
  if(valid===0)renderEmpty(section,c);else if(!section.querySelector('.history-future-wrap'))renderFuture(section,valid);
}

let tries=0;
const timer=setInterval(()=>{run();if(++tries>35)clearInterval(timer)},400);
document.addEventListener('click',e=>{if(e.target.closest&&e.target.closest('[data-page="historico"]'))setTimeout(run,120)});
run();
})();