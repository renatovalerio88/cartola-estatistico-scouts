(function () {
  'use strict';
  if (typeof document === 'undefined') return;

  const CSS = `
    #projecoes .hero{margin-bottom:12px}
    #projecoes .projection-toolbar{display:grid;grid-template-columns:minmax(180px,1.3fr) repeat(3,minmax(125px,.7fr));gap:8px;align-items:end;margin:10px 0 8px}
    #projecoes .projection-toolbar .field{min-width:0}
    #projecoes .projection-toolbar input,#projecoes .projection-toolbar select{width:100%;min-width:0;min-height:38px;padding:8px 10px;border-radius:10px;font-size:.8rem}
    #projecoes .pos-chips{display:flex;gap:6px;overflow:auto;padding:2px 0 6px;scrollbar-width:none}
    #projecoes .pos-chips::-webkit-scrollbar{display:none}
    #projecoes .pos-chip{border:1px solid #d8e6df;background:#fff;color:#60756c;border-radius:999px;padding:6px 10px;min-height:32px;font-size:.7rem;font-weight:800;white-space:nowrap;cursor:pointer}
    #projecoes .pos-chip.active{background:#176b4b;color:#fff;border-color:#176b4b}
    #projecoes .confidence-audit{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;margin:2px 0 10px;padding:8px 10px;border:1px solid #e0ebe5;border-radius:11px;background:#fbfdfc;color:#6f8179;font-size:.67rem}
    #projecoes .confidence-audit b{color:#254b3d}
    #projecoes .confidence-audit .audit-warning{color:#9a6c17;font-weight:750}
    #projecoes #projectionTable{overflow:visible;border:0;background:transparent;border-radius:0}
    #projecoes .projection-list{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}
    #projecoes .projection-card{position:relative;background:#fff;border:1px solid #dfe9e4;border-radius:14px;padding:11px 12px;box-shadow:0 7px 20px rgba(22,69,50,.045);min-width:0}
    #projecoes .projection-card.top3{border-color:#c8ddd3;box-shadow:0 8px 22px rgba(22,107,75,.08)}
    #projecoes .projection-rank{position:absolute;top:10px;right:11px;min-width:25px;height:25px;padding:0 6px;border-radius:999px;background:#f0f5f2;color:#6b8077;display:flex;align-items:center;justify-content:center;font-size:.65rem;font-weight:900}
    #projecoes .projection-card.top3 .projection-rank{background:#e3f1ea;color:#176b4b}
    #projecoes .projection-head{display:flex;align-items:flex-start;gap:8px;padding-right:35px;min-width:0}
    #projecoes .projection-pos{flex:0 0 auto;background:#e7f3ed;color:#176b4b;border-radius:999px;padding:4px 7px;font-size:.58rem;font-weight:900;letter-spacing:.02em}
    #projecoes .projection-name{font-size:.9rem;line-height:1.12;font-weight:900;color:#183128;min-width:0;overflow-wrap:anywhere}
    #projecoes .projection-fixture{margin:4px 0 7px;color:#176b4b;font-size:.69rem;font-weight:800}
    #projecoes .projection-kpis{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));border:1px solid #e7eeea;border-radius:10px;overflow:hidden;background:#fbfdfc}
    #projecoes .projection-kpi{padding:6px 7px;min-width:0}
    #projecoes .projection-kpi:not(:last-child){border-right:1px solid #e7eeea}
    #projecoes .projection-kpi small{display:block;color:#81918b;font-size:.52rem;text-transform:uppercase;letter-spacing:.025em;font-weight:800;line-height:1.1}
    #projecoes .projection-kpi b{display:block;margin-top:2px;font-size:.78rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    #projecoes .projection-kpi .score{color:#176b4b;font-size:.92rem}
    #projecoes .projection-signals{display:flex;gap:5px;flex-wrap:wrap;margin-top:7px;min-height:22px}
    #projecoes .signal{display:inline-flex;align-items:center;gap:3px;padding:3px 6px;border-radius:999px;background:#f2f6f4;color:#647a70;font-size:.56rem;font-weight:780;line-height:1.15}
    #projecoes .projection-actions{display:grid;grid-template-columns:1fr auto;gap:7px;margin-top:8px}
    #projecoes .projection-actions button{border:0;border-radius:9px;min-height:34px;padding:6px 10px;font-size:.68rem;font-weight:850;cursor:pointer}
    #projecoes .view-analysis{background:#e6f2ec;color:#176b4b}
    #projecoes .add-monte{background:#fff;color:#176b4b;border:1px solid #bfd8cc!important;white-space:nowrap}
    #projectionToast{position:fixed;left:50%;bottom:22px;transform:translateX(-50%) translateY(20px);z-index:80;background:#183128;color:#fff;border-radius:999px;padding:9px 14px;font-size:.72rem;font-weight:750;opacity:0;pointer-events:none;transition:.2s;box-shadow:0 8px 30px rgba(0,0,0,.18);max-width:calc(100vw - 28px);text-align:center}
    #projectionToast.show{opacity:1;transform:translateX(-50%) translateY(0)}

    @media(max-width:700px){
      #projecoes .hero{padding:16px 15px!important;margin-bottom:10px!important}
      #projecoes .hero h1{font-size:1.35rem!important;margin-bottom:3px!important}
      #projecoes .hero .lead{font-size:.78rem!important;line-height:1.42!important}
      #projecoes>.controls{display:none!important}
      #projecoes .projection-toolbar{grid-template-columns:1fr 1fr;gap:6px;margin:7px 0 5px}
      #projecoes .projection-toolbar .search-field{grid-column:1/3}
      #projecoes .projection-toolbar .sort-field{grid-column:1/2}
      #projecoes .projection-toolbar .club-field{grid-column:2/3}
      #projecoes .projection-toolbar .price-field{display:none}
      #projecoes .projection-toolbar label{font-size:.61rem!important}
      #projecoes .projection-toolbar input,#projecoes .projection-toolbar select{min-height:35px;padding:6px 8px;font-size:.73rem}
      #projecoes .pos-chips{margin:0 -1px;padding-bottom:5px}
      #projecoes .pos-chip{min-height:29px;padding:5px 9px;font-size:.64rem}
      #projecoes .confidence-audit{margin-bottom:7px;padding:6px 8px;font-size:.59rem;line-height:1.25}
      #projecoes .projection-list{grid-template-columns:1fr;gap:7px}
      #projecoes .projection-card{padding:9px 10px;border-radius:12px}
      #projecoes .projection-rank{top:8px;right:9px;height:22px;min-width:22px;font-size:.58rem}
      #projecoes .projection-head{gap:6px;padding-right:31px}
      #projecoes .projection-pos{font-size:.53rem;padding:3px 6px}
      #projecoes .projection-name{font-size:.84rem;line-height:1.08}
      #projecoes .projection-fixture{font-size:.63rem;margin:3px 0 6px}
      #projecoes .projection-kpi{padding:5px 6px}
      #projecoes .projection-kpi small{font-size:.47rem}
      #projecoes .projection-kpi b{font-size:.7rem}
      #projecoes .projection-kpi .score{font-size:.86rem}
      #projecoes .projection-signals{margin-top:6px;min-height:19px}
      #projecoes .signal{font-size:.51rem;padding:2px 5px}
      #projecoes .projection-actions{margin-top:6px;gap:6px}
      #projecoes .projection-actions button{min-height:31px;padding:5px 8px;font-size:.62rem}
    }
  `;

  let sortMode = 'projection';
  let maxPrice = '';
  let rendering = false;
  let observer = null;

  function injectStyle() {
    let style = document.getElementById('projecoes-premium-style');
    if (!style) {
      style = document.createElement('style');
      style.id = 'projecoes-premium-style';
      document.head.appendChild(style);
    }
    style.textContent = CSS;
  }

  function safeFmt(v, d = 2) {
    const n = Number(v || 0);
    return n.toLocaleString('pt-BR', {minimumFractionDigits:d, maximumFractionDigits:d});
  }

  function getPlayers() {
    try { return Array.isArray(players) ? players : []; } catch (_) { return []; }
  }

  function getConfidence(p) {
    try {
      const c = confidence(p);
      return {label:c[0], cls:c[1], rank:c[0] === 'Alta' ? 3 : c[0] === 'Média' ? 2 : 1};
    } catch (_) {
      const tit = Number(p.titularidade || 0);
      return tit >= 80 ? {label:'Alta',cls:'good',rank:3} : tit >= 50 ? {label:'Média',cls:'warn',rank:2} : {label:'Baixa',cls:'bad',rank:1};
    }
  }

  function getFixture(p) {
    try { return fixture(p); } catch (_) {
      const opp = p.sigla_adversario || '—';
      return p.mando === 'casa' ? `${p.sigla_clube} x ${opp}` : `${p.sigla_clube} @ ${opp}`;
    }
  }

  function valueScore(p) {
    const price = Number(p.preco || 0);
    return price > 0 ? Number(p.projecao || 0) / price : 0;
  }

  function signals(p) {
    const out = [];
    if (p.mando === 'casa') out.push('🏠 Casa');
    else if (p.mando) out.push('✈️ Fora');
    const tit = Number(p.titularidade || 0);
    if (tit >= 80) out.push(`✅ Titular ${safeFmt(tit,0)}%`);
    else if (tit > 0 && tit < 60) out.push(`⚠️ Titular ${safeFmt(tit,0)}%`);
    const mins = Number(p.minutos_esperados || 0);
    if (mins > 0 && mins < 70) out.push(`⏱ ${safeFmt(mins,0)} min`);
    if (['GOL','LAT','ZAG'].includes(p.posicao) && Number(p.chance_sg || 0) >= 35) out.push(`🛡 SG ${safeFmt(p.chance_sg,0)}%`);
    if (!out.length) out.push('📊 Modelo pré-rodada');
    return out.slice(0,3);
  }

  function ensureToolbar() {
    const section = document.getElementById('projecoes');
    if (!section || section.querySelector('.projection-toolbar')) return;
    const old = section.querySelector('.controls');
    const toolbar = document.createElement('div');
    toolbar.className = 'projection-toolbar';
    toolbar.innerHTML = `
      <div class="field search-field"><label>Buscar jogador</label><input id="premiumProjSearch" placeholder="Nome do jogador"></div>
      <div class="field sort-field"><label>Ordenar por</label><select id="premiumProjSort"><option value="projection">Projeção</option><option value="value">Custo-benefício</option><option value="confidence">Confiança</option></select></div>
      <div class="field club-field"><label>Clube</label><select id="premiumProjClub"><option value="">Todos</option></select></div>
      <div class="field price-field"><label>Preço máximo</label><input id="premiumProjPrice" type="number" min="0" step="1" placeholder="Sem limite"></div>`;
    const chips = document.createElement('div');
    chips.className = 'pos-chips';
    chips.setAttribute('aria-label','Filtrar por posição');
    chips.innerHTML = ['', 'GOL','LAT','ZAG','MEI','ATA','TEC'].map((p,i)=>`<button class="pos-chip ${i===0?'active':''}" type="button" data-pos="${p}">${p||'Todos'}</button>`).join('');
    const audit = document.createElement('div');
    audit.className = 'confidence-audit';
    audit.id = 'confidenceAudit';
    old.parentNode.insertBefore(toolbar, old.nextSibling);
    toolbar.parentNode.insertBefore(chips, toolbar.nextSibling);
    chips.parentNode.insertBefore(audit, chips.nextSibling);

    const clubs = [...new Set(getPlayers().map(p=>p.sigla_clube).filter(Boolean))].sort();
    const club = document.getElementById('premiumProjClub');
    club.innerHTML = '<option value="">Todos</option>' + clubs.map(c=>`<option value="${c}">${c}</option>`).join('');

    document.getElementById('premiumProjSearch').addEventListener('input', renderPremium);
    club.addEventListener('change', renderPremium);
    document.getElementById('premiumProjSort').addEventListener('change', e=>{ sortMode=e.target.value; renderPremium(); });
    document.getElementById('premiumProjPrice').addEventListener('input', e=>{ maxPrice=e.target.value; renderPremium(); });
    chips.querySelectorAll('.pos-chip').forEach(btn=>btn.addEventListener('click',()=>{
      chips.querySelectorAll('.pos-chip').forEach(x=>x.classList.toggle('active',x===btn));
      renderPremium();
    }));
  }

  function filteredPlayers() {
    const all = getPlayers();
    const active = document.querySelector('#projecoes .pos-chip.active');
    const pos = active?.dataset.pos || '';
    const club = document.getElementById('premiumProjClub')?.value || '';
    const q = (document.getElementById('premiumProjSearch')?.value || '').trim().toLowerCase();
    const priceCap = Number(maxPrice || 0);
    const list = all.filter(p =>
      (!pos || p.posicao === pos) &&
      (!club || p.sigla_clube === club) &&
      (!q || String(p.apelido || '').toLowerCase().includes(q)) &&
      (!priceCap || Number(p.preco || 0) <= priceCap)
    );
    list.sort((a,b)=>{
      if (sortMode === 'value') return valueScore(b)-valueScore(a) || Number(b.projecao||0)-Number(a.projecao||0);
      if (sortMode === 'confidence') return getConfidence(b).rank-getConfidence(a).rank || Number(b.projecao||0)-Number(a.projecao||0);
      return Number(b.projecao||0)-Number(a.projecao||0);
    });
    return list.slice(0,180);
  }

  function renderAudit(list) {
    const box = document.getElementById('confidenceAudit');
    if (!box) return;
    const dist = {Alta:0,'Média':0,Baixa:0};
    list.forEach(p=>{ const k=getConfidence(p).label; dist[k]=(dist[k]||0)+1; });
    const n = Math.max(1,list.length);
    const lowPct = Math.round((dist.Baixa||0)*100/n);
    box.innerHTML = `<span><b>${list.length}</b> jogadores · Confiança: <b>${dist.Alta||0}</b> alta · <b>${dist['Média']||0}</b> média · <b>${dist.Baixa||0}</b> baixa</span>${lowPct>=70?`<span class="audit-warning">⚠ ${lowPct}% com confiança baixa — régua mantida, sem recalibração artificial.</span>`:''}`;
  }

  function cardHtml(p, i) {
    const c = getConfidence(p);
    const value = valueScore(p);
    return `<article class="projection-card ${i<3?'top3':''}" data-projection-id="${p.atleta_id}">
      <div class="projection-rank">#${i+1}</div>
      <div class="projection-head"><span class="projection-pos">${p.posicao}</span><div class="projection-name">${p.apelido}</div></div>
      <div class="projection-fixture">${getFixture(p)} · ${p.sigla_clube||'—'}</div>
      <div class="projection-kpis">
        <div class="projection-kpi"><small>Projeção</small><b class="score">${safeFmt(p.projecao)} pts</b></div>
        <div class="projection-kpi"><small>Preço</small><b>C$ ${safeFmt(p.preco)}</b></div>
        <div class="projection-kpi"><small>Confiança</small><b class="${c.cls}">${c.label}</b></div>
      </div>
      <div class="projection-signals">${signals(p).map(s=>`<span class="signal">${s}</span>`).join('')}<span class="signal">💰 ${safeFmt(value,2)} pt/C$</span></div>
      <div class="projection-actions"><button class="view-analysis" type="button" data-analysis-id="${p.atleta_id}">Ver análise</button><button class="add-monte" type="button" data-monte-id="${p.atleta_id}">+ Montar</button></div>
    </article>`;
  }

  function renderPremium() {
    if (rendering) return;
    const box = document.getElementById('projectionTable');
    if (!box || !getPlayers().length) return;
    rendering = true;
    const list = filteredPlayers();
    box.innerHTML = list.length ? `<div class="projection-list">${list.map(cardHtml).join('')}</div>` : '<div class="empty">Nenhum jogador encontrado com esses filtros.</div>';
    renderAudit(list);
    box.querySelectorAll('[data-analysis-id]').forEach(btn=>btn.addEventListener('click',()=>{
      try { showPlayer(btn.dataset.analysisId); } catch (_) {}
    }));
    box.querySelectorAll('[data-monte-id]').forEach(btn=>btn.addEventListener('click',()=>addToMonte(btn.dataset.monteId)));
    rendering = false;
  }

  function showToast(text) {
    let toast = document.getElementById('projectionToast');
    if (!toast) {
      toast = document.createElement('div');
      toast.id = 'projectionToast';
      document.body.appendChild(toast);
    }
    toast.textContent = text;
    toast.classList.add('show');
    clearTimeout(showToast.t);
    showToast.t = setTimeout(()=>toast.classList.remove('show'),2400);
  }

  function openMonte() {
    const btn = document.querySelector('#nav button[data-page="monte"]');
    if (btn) btn.click();
    setTimeout(()=>document.getElementById('customPickers')?.scrollIntoView({behavior:'smooth',block:'start'}),80);
  }

  function addToMonte(id) {
    const p = getPlayers().find(x=>String(x.atleta_id)===String(id));
    if (!p) return;
    try {
      const pos = p.posicao;
      customForced[pos] = customForced[pos] || [];
      if (customForced[pos].some(x=>String(x)===String(id))) {
        showToast(`${p.apelido} já está escolhido.`);
        openMonte();
        return;
      }
      const form = document.getElementById('customFormation')?.value || 'auto';
      const limit = maxSlotsFor(pos, form);
      if (limit <= 0 || customForced[pos].length >= limit) {
        showToast(`Sem vaga de ${pos} na formação atual. Ajuste em Montar.`);
        openMonte();
        return;
      }
      customForced[pos].push(String(id));
      renderCustomPickers();
      showToast(`${p.apelido} adicionado às suas escolhas.`);
      openMonte();
    } catch (e) {
      showToast('Abra Montar para adicionar este jogador.');
      openMonte();
    }
  }

  function updateHero() {
    const lead = document.querySelector('#projecoes .hero .lead');
    if (lead) lead.textContent = 'Compare projeção, preço, confiança e contexto. Use “Ver análise” para os scouts ou “+ Montar” para levar o jogador à sua escalação.';
  }

  function bindLegacyFilters() {
    ['filterPos','filterClub','search'].forEach(id=>{
      const el=document.getElementById(id);
      if (el) el.addEventListener(id==='search'?'input':'change',()=>setTimeout(renderPremium,0));
    });
  }

  function watchLegacyRenderer() {
    const box = document.getElementById('projectionTable');
    if (!box || observer) return;
    observer = new MutationObserver(()=>{
      if (rendering) return;
      if (box.querySelector('table')) setTimeout(renderPremium,0);
    });
    observer.observe(box,{childList:true,subtree:false});
  }

  function boot() {
    injectStyle();
    updateHero();
    const wait = setInterval(()=>{
      if (!getPlayers().length) return;
      clearInterval(wait);
      ensureToolbar();
      bindLegacyFilters();
      watchLegacyRenderer();
      renderPremium();
    },120);
    setTimeout(()=>clearInterval(wait),20000);
  }

  boot();
})();
