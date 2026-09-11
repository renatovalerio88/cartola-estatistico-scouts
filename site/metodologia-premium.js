(() => {
  'use strict';

  const STYLE_ID = 'metodologia-premium-style';
  const PAGE_ID = 'metodologia';

  function addStyles() {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      #${PAGE_ID}.method-premium{--mp-green:#176b4b;--mp-green-dark:#0e5439;--mp-soft:#eef7f2;--mp-line:#d9e7e0;--mp-text:#183128;--mp-muted:#6d7e77}
      #${PAGE_ID} .method-overview{display:grid;grid-template-columns:1.25fr .75fr;gap:14px;margin:0 0 18px}
      #${PAGE_ID} .method-overview-main,#${PAGE_ID} .method-guardrails{background:#fff;border:1px solid var(--mp-line);border-radius:20px;box-shadow:0 12px 32px rgba(22,69,50,.07)}
      #${PAGE_ID} .method-overview-main{padding:20px}
      #${PAGE_ID} .method-overview-kicker{display:inline-flex;align-items:center;gap:7px;padding:6px 9px;border-radius:999px;background:var(--mp-soft);color:var(--mp-green);font-size:.73rem;font-weight:900;letter-spacing:.02em;text-transform:uppercase}
      #${PAGE_ID} .method-overview-main h2{font-size:1.35rem;margin:13px 0 7px;color:var(--mp-green-dark)}
      #${PAGE_ID} .method-overview-main p{margin:0;color:var(--mp-muted);max-width:720px}
      #${PAGE_ID} .method-flow{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:8px;margin-top:17px}
      #${PAGE_ID} .method-flow-step{position:relative;min-width:0;padding:12px 10px;border:1px solid var(--mp-line);border-radius:14px;background:#fbfdfc}
      #${PAGE_ID} .method-flow-step b{display:block;color:var(--mp-green-dark);font-size:.8rem;margin-bottom:3px}
      #${PAGE_ID} .method-flow-step span{display:block;color:var(--mp-muted);font-size:.69rem;line-height:1.35}
      #${PAGE_ID} .method-flow-step:not(:last-child):after{content:'›';position:absolute;right:-8px;top:50%;transform:translateY(-50%);z-index:2;width:16px;height:16px;border-radius:50%;background:var(--mp-green);color:#fff;display:grid;place-items:center;font-weight:900;font-size:.75rem}
      #${PAGE_ID} .method-guardrails{padding:16px;display:grid;gap:9px;align-content:start}
      #${PAGE_ID} .method-guardrails h3{margin:0 0 3px;font-size:.91rem;color:var(--mp-green-dark)}
      #${PAGE_ID} .guardrail{display:grid;grid-template-columns:28px 1fr;gap:9px;align-items:start;padding:10px;border-radius:13px;background:#f8fbf9;border:1px solid #e4eee9}
      #${PAGE_ID} .guardrail-icon{width:28px;height:28px;border-radius:9px;background:var(--mp-soft);color:var(--mp-green);display:grid;place-items:center;font-weight:950;font-size:.78rem}
      #${PAGE_ID} .guardrail b{display:block;font-size:.77rem;color:var(--mp-text)}
      #${PAGE_ID} .guardrail small{display:block;color:var(--mp-muted);font-size:.67rem;line-height:1.4;margin-top:2px}
      #${PAGE_ID} .method-live-title{display:flex;justify-content:space-between;gap:12px;align-items:end;margin:25px 0 10px}
      #${PAGE_ID} .method-live-title h2{margin:0}
      #${PAGE_ID} .method-live-title p{margin:0;color:var(--mp-muted);font-size:.78rem}
      #${PAGE_ID} .method-live-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-bottom:20px}
      #${PAGE_ID} .method-live-card{background:#fff;border:1px solid var(--mp-line);border-radius:16px;padding:14px;box-shadow:0 8px 22px rgba(22,69,50,.05)}
      #${PAGE_ID} .method-live-card small{display:block;color:var(--mp-muted);font-size:.7rem;font-weight:750}
      #${PAGE_ID} .method-live-card b{display:block;color:var(--mp-green-dark);font-size:1.28rem;margin-top:4px;letter-spacing:-.02em}
      #${PAGE_ID} .method-live-card span{display:block;color:var(--mp-muted);font-size:.67rem;margin-top:3px;line-height:1.35}
      #${PAGE_ID} .method-section-nav{display:flex;gap:7px;overflow:auto;padding:2px 0 10px;margin-bottom:3px;scrollbar-width:none}
      #${PAGE_ID} .method-section-nav::-webkit-scrollbar{display:none}
      #${PAGE_ID} .method-nav-chip{border:1px solid var(--mp-line);background:#fff;color:var(--mp-green-dark);border-radius:999px;padding:7px 10px;font-size:.69rem;font-weight:800;white-space:nowrap;cursor:pointer}
      #${PAGE_ID} .method-nav-chip:hover{background:var(--mp-soft)}
      #${PAGE_ID} .method-accordion{padding:0!important;overflow:hidden}
      #${PAGE_ID} .method-accordion-head{width:100%;border:0;background:#fff;color:var(--mp-text);text-align:left;padding:18px 19px;display:grid;grid-template-columns:34px 1fr auto;gap:11px;align-items:center;cursor:pointer}
      #${PAGE_ID} .method-number{width:34px;height:34px;border-radius:11px;background:var(--mp-soft);color:var(--mp-green);display:grid;place-items:center;font-weight:950;font-size:.78rem}
      #${PAGE_ID} .method-accordion-title{font-size:.96rem;font-weight:900;letter-spacing:-.01em}
      #${PAGE_ID} .method-accordion-sub{display:block;color:var(--mp-muted);font-size:.69rem;font-weight:650;margin-top:2px}
      #${PAGE_ID} .method-toggle{color:var(--mp-green);font-size:1rem;font-weight:950;transition:transform .2s ease}
      #${PAGE_ID} .method-accordion.open .method-toggle{transform:rotate(180deg)}
      #${PAGE_ID} .method-accordion-body{display:none;border-top:1px solid #edf2ef;padding:4px 19px 18px}
      #${PAGE_ID} .method-accordion.open .method-accordion-body{display:block}
      #${PAGE_ID} .method-accordion-body p{color:#53675f}
      #${PAGE_ID} .method-accordion-body .formula{margin-top:12px}
      #${PAGE_ID} .method-tag{display:inline-flex;align-items:center;margin-top:10px;padding:5px 8px;border-radius:999px;background:#f4f8f6;border:1px solid var(--mp-line);font-size:.67rem;font-weight:850;color:var(--mp-green-dark)}
      #${PAGE_ID} .method-footer-note{margin-top:16px;padding:15px 16px;border-radius:16px;background:linear-gradient(135deg,#0e5439,#176b4b);color:#fff;box-shadow:0 12px 28px rgba(14,84,57,.14)}
      #${PAGE_ID} .method-footer-note b{display:block;margin-bottom:4px}
      #${PAGE_ID} .method-footer-note span{font-size:.78rem;line-height:1.5;color:rgba(255,255,255,.82)}
      #${PAGE_ID} #methodStats,#${PAGE_ID} #methodRuntime{margin-top:12px}
      @media(max-width:900px){#${PAGE_ID} .method-overview{grid-template-columns:1fr}#${PAGE_ID} .method-flow{grid-template-columns:repeat(3,minmax(0,1fr))}#${PAGE_ID} .method-flow-step:nth-child(3):after{display:none}#${PAGE_ID} .method-live-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
      @media(max-width:560px){#${PAGE_ID} .method-overview-main{padding:16px}#${PAGE_ID} .method-flow{grid-template-columns:1fr 1fr}#${PAGE_ID} .method-flow-step:after{display:none}#${PAGE_ID} .method-live-grid{grid-template-columns:1fr 1fr}#${PAGE_ID} .method-accordion-head{padding:15px 14px;grid-template-columns:31px 1fr auto}#${PAGE_ID} .method-number{width:31px;height:31px}#${PAGE_ID} .method-accordion-body{padding:3px 14px 15px}#${PAGE_ID} .method-live-title{display:block}#${PAGE_ID} .method-live-title p{margin-top:4px}}
    `;
    document.head.appendChild(style);
  }

  const sectionMeta = [
    ['Objetivo', 'O que o sistema tenta resolver'],
    ['Anti-vazamento', 'A regra temporal que protege a validação'],
    ['Elegibilidade', 'Quem realmente pode entrar no universo'],
    ['Scouts', 'Como a projeção é explicada'],
    ['Modelos', 'Famílias candidatas e seleção'],
    ['Walk-forward', 'Como o modelo é testado fora da amostra'],
    ['Risco', 'Titularidade, minutos e confiança'],
    ['Contexto', 'O que muda de uma rodada para outra'],
    ['Otimização', 'Como os 11 são escolhidos'],
    ['Capitão e banco', 'Regras após a escolha dos titulares'],
    ['Histórico', 'Prova prospectiva, sem reconstrução'],
    ['Escala', 'Volume real processado na rodada'],
    ['Exemplo', 'Leitura completa de uma decisão']
  ];

  function overviewMarkup() {
    return `
      <div class="method-overview">
        <div class="method-overview-main">
          <span class="method-overview-kicker">Como o modelo decide</span>
          <h2>Da informação pré-rodada até a escalação final</h2>
          <p>A metodologia separa previsão, validação e otimização. Cada etapa tem uma função própria e nenhuma pode usar informação que só ficou conhecida depois do fechamento do mercado.</p>
          <div class="method-flow">
            <div class="method-flow-step"><b>1. Snapshot</b><span>Dados disponíveis antes da rodada</span></div>
            <div class="method-flow-step"><b>2. Elegibilidade</b><span>Status, posição e chance de jogar</span></div>
            <div class="method-flow-step"><b>3. Projeção</b><span>Scouts, histórico e contexto</span></div>
            <div class="method-flow-step"><b>4. Confiança</b><span>Minutos, risco e incerteza</span></div>
            <div class="method-flow-step"><b>5. Otimização</b><span>Formação, clube e patrimônio</span></div>
            <div class="method-flow-step"><b>6. Auditoria</b><span>Real × previsto, só depois da rodada</span></div>
          </div>
        </div>
        <aside class="method-guardrails">
          <h3>Guardrails invioláveis</h3>
          <div class="guardrail"><span class="guardrail-icon">R-1</span><div><b>Corte temporal</b><small>Para prever R, só entram dados que já existiam até R-1.</small></div></div>
          <div class="guardrail"><span class="guardrail-icon">✓</span><div><b>Sem reconstrução retroativa</b><small>Rodadas sem prova prospectiva não são inventadas para melhorar o histórico.</small></div></div>
          <div class="guardrail"><span class="guardrail-icon">Σ</span><div><b>Preço não gera pontos</b><small>Patrimônio é restrição do problema, não bônus de projeção.</small></div></div>
          <div class="guardrail"><span class="guardrail-icon">11</span><div><b>Otimização separada</b><small>O motor escolhe a combinação final sem alterar a projeção individual.</small></div></div>
        </aside>
      </div>
      <div class="method-live-title"><div><h2>Raio-X do processamento atual</h2><p>Indicadores lidos do payload desta rodada, sem números decorativos.</p></div></div>
      <div class="method-live-grid" id="methodPremiumLive"></div>
      <div class="method-section-nav" id="methodSectionNav"></div>
    `;
  }

  function getLiveMetrics() {
    try {
      const ps = typeof players !== 'undefined' && Array.isArray(players) ? players : [];
      const explanation = typeof D !== 'undefined' ? (D.explicabilidade_pre_rodada?.jogadores || []) : [];
      const valid = typeof D !== 'undefined' ? (D.avaliacao_prospectiva_imutavel?.times_sugeridos || []).filter(r => r.entra_no_historico_publico === true) : [];
      const evaluated = valid.filter(r => r.status === 'AVALIADA');
      const eligible = ps.filter(p => Number(p.status_id) === 7).length;
      const scoutRows = explanation.reduce((sum, j) => sum + (Array.isArray(j.scouts) ? j.scouts.length : 0), 0);
      return [
        ['Atletas elegíveis', eligible || '—', 'Disponíveis ao motor antes da otimização'],
        ['Com explicabilidade', explanation.length || '—', 'Jogadores com decomposição da projeção'],
        ['Scouts avaliados', scoutRows || '—', 'Contribuições processadas no snapshot'],
        ['Rodadas prospectivas', evaluated.length || '0', 'Somente histórico com prova pré-fechamento']
      ];
    } catch (_) {
      return [
        ['Atletas elegíveis', '—', 'Aguardando payload'],
        ['Com explicabilidade', '—', 'Aguardando payload'],
        ['Scouts avaliados', '—', 'Aguardando payload'],
        ['Rodadas prospectivas', '—', 'Aguardando payload']
      ];
    }
  }

  function renderLiveMetrics() {
    const box = document.getElementById('methodPremiumLive');
    if (!box) return;
    box.innerHTML = getLiveMetrics().map(([label, value, note]) => `
      <div class="method-live-card"><small>${label}</small><b>${value}</b><span>${note}</span></div>
    `).join('');
  }

  function classifyTag(index) {
    if ([1, 5, 10].includes(index)) return 'Auditoria e prova';
    if ([2, 6].includes(index)) return 'Elegibilidade e risco';
    if ([3, 4, 7].includes(index)) return 'Projeção';
    if ([8, 9].includes(index)) return 'Decisão da escalação';
    if (index === 11) return 'Escala operacional';
    return 'Visão geral';
  }

  function makeAccordion(section, index) {
    const originalHeading = section.querySelector('h2');
    if (!originalHeading) return;
    const title = originalHeading.textContent.replace(/^\s*\d+\.\s*/, '').trim();
    originalHeading.remove();

    const body = document.createElement('div');
    body.className = 'method-accordion-body';
    while (section.firstChild) body.appendChild(section.firstChild);

    const meta = sectionMeta[index] || [title, 'Detalhes técnicos'];
    const head = document.createElement('button');
    head.type = 'button';
    head.className = 'method-accordion-head';
    head.setAttribute('aria-expanded', index < 3 ? 'true' : 'false');
    head.innerHTML = `
      <span class="method-number">${index + 1}</span>
      <span><span class="method-accordion-title">${title}</span><span class="method-accordion-sub">${meta[1]}</span></span>
      <span class="method-toggle">⌄</span>
    `;

    const tag = document.createElement('span');
    tag.className = 'method-tag';
    tag.textContent = classifyTag(index);
    body.appendChild(tag);

    section.classList.add('method-accordion');
    section.dataset.methodIndex = String(index + 1);
    if (index < 3) section.classList.add('open');
    section.append(head, body);

    head.addEventListener('click', () => {
      const open = section.classList.toggle('open');
      head.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
  }

  function buildNav(sections) {
    const nav = document.getElementById('methodSectionNav');
    if (!nav) return;
    nav.innerHTML = sections.map((section, index) => {
      const meta = sectionMeta[index] || [`Etapa ${index + 1}`];
      return `<button type="button" class="method-nav-chip" data-method-go="${index + 1}">${index + 1}. ${meta[0]}</button>`;
    }).join('');
    nav.querySelectorAll('[data-method-go]').forEach(btn => {
      btn.addEventListener('click', () => {
        const target = document.querySelector(`#${PAGE_ID} .method-accordion[data-method-index="${btn.dataset.methodGo}"]`);
        if (!target) return;
        target.classList.add('open');
        target.querySelector('.method-accordion-head')?.setAttribute('aria-expanded', 'true');
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    });
  }

  function addFooter(page) {
    if (page.querySelector('.method-footer-note')) return;
    const footer = document.createElement('div');
    footer.className = 'method-footer-note';
    footer.innerHTML = '<b>Regra final de confiança</b><span>Resultado real serve para medir, auditar e melhorar as próximas rodadas. Ele nunca volta no tempo para alterar uma previsão que já deveria estar congelada.</span>';
    page.appendChild(footer);
  }

  function enhance() {
    const page = document.getElementById(PAGE_ID);
    if (!page || page.dataset.premiumReady === '1') return;
    page.dataset.premiumReady = '1';
    page.classList.add('method-premium');
    addStyles();

    const hero = page.querySelector(':scope > .hero');
    if (hero) hero.insertAdjacentHTML('afterend', overviewMarkup());

    const sections = [...page.querySelectorAll(':scope > section')];
    sections.forEach(makeAccordion);
    buildNav(sections);
    addFooter(page);
    renderLiveMetrics();

    let attempts = 0;
    const timer = setInterval(() => {
      renderLiveMetrics();
      attempts += 1;
      const ready = (() => {
        try { return typeof players !== 'undefined' && Array.isArray(players) && players.length > 0; }
        catch (_) { return false; }
      })();
      if (ready || attempts >= 20) clearInterval(timer);
    }, 500);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', enhance, { once: true });
  } else {
    enhance();
  }
})();
