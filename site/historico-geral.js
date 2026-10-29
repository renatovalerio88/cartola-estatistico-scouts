(() => {
  'use strict';

  const STYLE = `
    #historico .hg-wrap{display:grid;gap:14px;margin-top:14px}
    #historico .hg-card{background:#fff;border:1px solid var(--line);border-radius:18px;padding:16px;box-shadow:var(--shadow);min-width:0}
    #historico .hg-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;margin-bottom:10px}
    #historico .hg-head h2{margin:0;font-size:1.05rem}
    #historico .hg-head p{margin:4px 0 0;color:var(--muted);font-size:.78rem}
    #historico .hg-badge{background:var(--brand2);color:var(--brand3);border-radius:999px;padding:5px 9px;font-size:.66rem;font-weight:850;white-space:nowrap}
    #historico .hg-chart{width:100%;overflow:hidden}
    #historico .hg-chart svg{display:block;width:100%;height:auto;min-height:220px}
    #historico .hg-legend{display:flex;gap:16px;margin-top:8px;color:var(--muted);font-size:.75rem;font-weight:750}
    #historico .hg-dot{width:9px;height:9px;border-radius:50%;display:inline-block;margin-right:5px}.hg-dot.proj{background:#d97706}.hg-dot.real{background:#177245}
    #historico .hg-table{overflow-x:auto;border:1px solid var(--line);border-radius:14px;-webkit-overflow-scrolling:touch}
    #historico .hg-table table{width:100%;min-width:520px;border-collapse:collapse;background:#fff}
    #historico .hg-table th,#historico .hg-table td{padding:10px 12px;border-bottom:1px solid var(--line);text-align:left}
    #historico .hg-table th{font-size:.68rem;text-transform:uppercase;color:var(--muted)}
    #historico .hg-table td{font-size:.82rem}.hg-pos{color:var(--brand);font-weight:850}.hg-neg{color:var(--danger);font-weight:850}
    #historico .hg-empty{padding:20px;text-align:center;color:var(--muted);font-size:.82rem}
    /* V34 — histórico geral responsivo: KPIs, gráfico explorável e cards no celular. */
    #historico .hg-kpis{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}
    #historico .hg-kpi{background:#f7fbf9;border:1px solid #dbeae3;border-radius:14px;padding:14px 15px;min-width:0}
    #historico .hg-kpi small{display:block;font-size:.7rem;font-weight:750;color:#668077;margin-bottom:7px}
    #historico .hg-kpi b{display:block;color:#173d37;font-size:1.22rem;font-weight:900;line-height:1.15;overflow-wrap:anywhere}
    #historico .hg-kpi .hg-pos{color:#08704c}
    #historico .hg-kpi .hg-neg{color:#aa4040}
    #historico .hg-mobile-tip{display:none;color:#627b79;font-size:.74rem;line-height:1.4;margin:9px 0 0}
    @media(max-width:700px){
      #historico .hg-card{padding:13px}
      #historico .hg-head{display:block}
      #historico .hg-badge{display:inline-block;margin-top:7px}
      #historico .hg-kpis{grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}
      #historico .hg-kpi{padding:12px}
      #historico .hg-kpi:first-child{grid-column:1/-1}
      #historico .hg-kpi b{font-size:1.08rem}
      #historico .hg-chart{overflow-x:auto;overscroll-behavior-x:contain;-webkit-overflow-scrolling:touch;scrollbar-color:#a8c8ba transparent;border-radius:10px}
      #historico .hg-chart svg{width:800px;min-width:800px;max-width:none;min-height:220px}
      #historico .hg-mobile-tip{display:block}
      #historico .hg-table{overflow:visible;border:0}
      #historico .hg-table table,#historico .hg-table tbody{display:block;min-width:0;width:100%}
      #historico .hg-table thead{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
      #historico .hg-table tbody{display:grid;gap:9px}
      #historico .hg-table tr{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px 12px;border:1px solid #e0eae6;border-radius:13px;padding:13px;background:#fff;box-shadow:0 4px 14px rgba(11,39,49,.035)}
      #historico .hg-table td{display:flex;flex-direction:column;gap:3px;padding:0;border:0;min-width:0;font-size:.91rem;font-weight:800;line-height:1.3;overflow-wrap:anywhere}
      #historico .hg-table td::before{display:block;color:#718781;font-size:.66rem;font-weight:750;letter-spacing:.045em;text-transform:uppercase}
      #historico .hg-table td:nth-child(1){grid-column:1/-1;padding-bottom:8px;border-bottom:1px solid #e5eeee;color:#0d7050;font-size:1.05rem}
      #historico .hg-table td:nth-child(1)::before{content:"Rodada"}
      #historico .hg-table td:nth-child(2)::before{content:"Projetado"}
      #historico .hg-table td:nth-child(3)::before{content:"Real"}
      #historico .hg-table td:nth-child(4){grid-column:1/-1;display:inline-flex;align-items:center;justify-self:start;gap:4px;border-radius:8px;padding:7px 9px;background:#e9f5ee}
      #historico .hg-table td:nth-child(4).hg-neg{background:#fff0f0}
      #historico .hg-table td:nth-child(4)::before{content:"Diferença:";font-size:.68rem}
    }
  `;

  function injectStyle(){
    let s=document.getElementById('historico-geral-style');
    if(!s){s=document.createElement('style');s.id='historico-geral-style';document.head.appendChild(s)}
    s.textContent=STYLE;
  }

  function fmt(v){
    const n=Number(v);
    return Number.isFinite(n)?n.toLocaleString('pt-BR',{minimumFractionDigits:1,maximumFractionDigits:1}):'—';
  }

  function getData(){
    try{
      if(window.__CARTOLA_DADOS__) return window.__CARTOLA_DADOS__;
      if(typeof D!=='undefined' && D) return D;
    }catch(_){}
    return {};
  }

  function normalizeRows(){
    const data=getData();
    const wf=data.backtest_time_sugerido_walk_forward||{};
    const raw=Array.isArray(wf.rodadas)?wf.rodadas:[];
    const rows=raw.map(r=>({
      rodada:Number(r.rodada),
      projecao:Number(r.projecao),
      real:Number(r.pontuacao_real ?? r.real)
    })).filter(r=>Number.isFinite(r.rodada)&&Number.isFinite(r.projecao)&&Number.isFinite(r.real));
    if(rows.length) return rows.sort((a,b)=>a.rodada-b.rodada);

    if(typeof normalizeHistory==='function'){
      try{
        return normalizeHistory().filter(r=>r&&r.status==='AVALIADA'&&Number.isFinite(Number(r.projecao))&&Number.isFinite(Number(r.pontuacao_real))).map(r=>({rodada:Number(r.rodada),projecao:Number(r.projecao),real:Number(r.pontuacao_real)})).sort((a,b)=>a.rodada-b.rodada);
      }catch(_){}
    }
    return [];
  }

  function chart(rows){
    if(!rows.length) return '<div class="hg-empty">Ainda não há rodadas auditáveis disponíveis para o histórico geral.</div>';
    const W=900,H=280,L=48,R=18,T=24,B=42;
    const vals=rows.flatMap(r=>[r.projecao,r.real]);
    let lo=Math.min(...vals),hi=Math.max(...vals);const pad=Math.max(5,(hi-lo)*.12);lo=Math.max(0,lo-pad);hi+=pad;if(hi<=lo)hi=lo+10;
    const x=i=>rows.length===1?(L+W-R)/2:L+i*(W-L-R)/(rows.length-1);
    const y=v=>T+(hi-v)*(H-T-B)/(hi-lo);
    let grid='',labels='',dots='',valueLabels='';
    for(let i=0;i<5;i++){const yy=T+i*(H-T-B)/4;const val=hi-i*(hi-lo)/4;grid+=`<line x1="${L}" y1="${yy}" x2="${W-R}" y2="${yy}" stroke="#e7eeea"/><text x="${L-7}" y="${yy+4}" text-anchor="end" font-size="10" fill="#7c8d86">${Math.round(val)}</text>`}
    const step=Math.max(1,Math.ceil(rows.length/9));
    rows.forEach((r,i)=>{
      const xx=x(i),yp=y(r.projecao),yr=y(r.real);
      if(i%step===0||i===rows.length-1){labels+=`<text x="${xx}" y="${H-12}" text-anchor="middle" font-size="10" fill="#7c8d86">R${r.rodada}</text>`;valueLabels+=`<text x="${xx}" y="${Math.max(11,yp-7)}" text-anchor="middle" font-size="9" fill="#b76105">${fmt(r.projecao)}</text><text x="${xx}" y="${Math.min(H-B+12,yr+14)}" text-anchor="middle" font-size="9" fill="#12623b">${fmt(r.real)}</text>`}
      dots+=`<circle cx="${xx}" cy="${yp}" r="3" fill="#d97706"/><circle cx="${xx}" cy="${yr}" r="3" fill="#177245"/>`;
    });
    const pp=rows.map((r,i)=>`${x(i)},${y(r.projecao)}`).join(' '),rp=rows.map((r,i)=>`${x(i)},${y(r.real)}`).join(' ');
    return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Gráfico Projetado versus Real por rodada">${grid}<polyline points="${pp}" fill="none" stroke="#d97706" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/><polyline points="${rp}" fill="none" stroke="#177245" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>${dots}${valueLabels}${labels}</svg>`;
  }

  function render(){
    const section=document.getElementById('historico');
    if(!section) return;
    injectStyle();
    const rows=normalizeRows();
    let root=section.querySelector('.hg-wrap');
    if(!root){root=document.createElement('div');root.className='hg-wrap';section.appendChild(root)}
    const body=rows.map(r=>{const d=r.real-r.projecao;return `<tr><td><b>R${r.rodada}</b></td><td>${fmt(r.projecao)} pts</td><td>${fmt(r.real)} pts</td><td class="${d>=0?'hg-pos':'hg-neg'}">${d>=0?'+':''}${fmt(d)} pts</td></tr>`}).join('');
    const latest=rows.length?rows[rows.length-1]:null;
    const latestDiff=latest?latest.real-latest.projecao:null;
    const diffClass=latestDiff==null?'':(latestDiff>=0?'hg-pos':'hg-neg');
    const diffText=latestDiff==null?'—':`${latestDiff>=0?'+':''}${fmt(latestDiff)} pts`;
    const summary=`<div class="hg-kpis" aria-label="Resumo do histórico geral">
      <div class="hg-kpi"><small>Rodadas avaliadas</small><b>${rows.length}</b></div>
      <div class="hg-kpi"><small>Última rodada</small><b>${latest?'R'+latest.rodada:'—'}</b></div>
      <div class="hg-kpi"><small>Diferença na última rodada</small><b class="${diffClass}">${diffText}</b></div>
    </div>`;
    root.innerHTML=`${summary}<div class="hg-card"><div class="hg-head"><div><h2>Projetado × Real</h2><p>Simulação retrospectiva walk-forward; não representa times publicados antes das rodadas.</p></div><span class="hg-badge">Simulação histórica</span></div><div class="hg-chart" role="region" tabindex="0" aria-label="Gráfico de projeção e resultado real por rodada, com rolagem horizontal no celular">${chart(rows)}</div><p class="hg-mobile-tip">Deslize o gráfico para os lados para explorar as rodadas.</p><div class="hg-legend"><span><i class="hg-dot proj"></i>Projetado</span><span><i class="hg-dot real"></i>Real</span></div></div><div class="hg-card"><div class="hg-head"><div><h2>Resultado por rodada</h2><p>Projetado, pontuação real e diferença.</p></div></div>${body?`<div class="hg-table"><table><thead><tr><th>Rodada</th><th>Projetado</th><th>Real</th><th>Diferença</th></tr></thead><tbody>${body}</tbody></table></div>`:'<div class="hg-empty">Ainda não há rodadas auditáveis disponíveis.</div>'}</div>`;
  }

  window.renderHistory=render;
  document.addEventListener('click',e=>{const b=e.target.closest&&e.target.closest('#nav button[data-page="historico"]');if(b)setTimeout(render,0)});
  if(window.__CARTOLA_DADOS_PROMISE__) window.__CARTOLA_DADOS_PROMISE__.then(()=>{if(document.querySelector('#historico.page.active'))render()}).catch(()=>{});
  if(document.querySelector('#historico.page.active')) setTimeout(render,0);
})();
