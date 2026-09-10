(function () {
  'use strict';
  if (typeof document === 'undefined') return;

  const CSS = `
    #analise .hero{margin-bottom:12px}
    #analise .analysis-method-note{margin:-3px 0 12px;padding:8px 10px;border:1px solid #e0ebe5;border-radius:11px;background:#fbfdfc;color:#70827a;font-size:.67rem;line-height:1.35}
    #analise .analysis-method-note b{color:#294d40}
    #analise .round-summary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin:10px 0 18px}
    #analise .summary-card{background:#fff;border:1px solid #dfe9e4;border-radius:13px;padding:10px 11px;box-shadow:0 6px 18px rgba(22,69,50,.04);min-width:0}
    #analise .summary-card small{display:block;color:#7b8c85;font-size:.56rem;text-transform:uppercase;letter-spacing:.035em;font-weight:850;line-height:1.15}
    #analise .summary-card b{display:block;margin-top:4px;font-size:.9rem;line-height:1.12;color:#183128}
    #analise .summary-card span{display:block;margin-top:3px;color:#657a71;font-size:.63rem;line-height:1.25}
    #analise .analysis-section-title{display:flex;align-items:center;justify-content:space-between;gap:10px;margin:18px 0 9px}
    #analise .analysis-section-title h2{margin:0;font-size:1.08rem}
    #analise .analysis-section-title span{font-size:.62rem;color:#7b8b85}
    #analise #matches{grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
    #analise .decision-match{padding:0!important;overflow:hidden;border-radius:15px!important;box-shadow:0 7px 22px rgba(22,69,50,.05)!important}
    #analise .match-head-premium{padding:11px 12px 9px;background:linear-gradient(180deg,#fbfdfc,#fff);border-bottom:1px solid #e8efeb}
    #analise .fixture-line{display:flex;align-items:center;justify-content:space-between;gap:10px}
    #analise .fixture-teams{font-size:.95rem;font-weight:900;letter-spacing:-.01em;color:#183128}
    #analise .fixture-teams .venue{font-size:.72rem;font-weight:750;color:#6f8179}
    #analise .match-read{display:flex;align-items:center;gap:5px;flex-wrap:wrap;margin-top:5px;color:#60756c;font-size:.62rem;line-height:1.3}
    #analise .match-read b{color:#176b4b}
    #analise .match-badge{display:inline-flex;align-items:center;padding:3px 6px;border-radius:999px;background:#e7f3ed;color:#176b4b;font-size:.55rem;font-weight:850;white-space:nowrap}
    #analise .sector-wrap{padding:9px 12px 10px}
    #analise .sector{padding:7px 0}
    #analise .sector+ .sector{border-top:1px solid #edf2ef}
    #analise .sector-title{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:5px}
    #analise .sector-title b{font-size:.69rem;text-transform:uppercase;letter-spacing:.025em;color:#657a71}
    #analise .sector-title span{font-size:.55rem;color:#8a9892}
    #analise .sector-row{display:grid;grid-template-columns:72px minmax(80px,1fr) 38px 65px;gap:6px;align-items:center;margin:4px 0;font-size:.65rem}
    #analise .sector-team{font-weight:800;color:#29483d;white-space:nowrap}
    #analise .sector-bar{height:6px;background:#edf2ef;border-radius:999px;overflow:hidden}
    #analise .sector-bar i{display:block;height:100%;background:#1b7654;border-radius:999px}
    #analise .sector-value{font-weight:900;text-align:right;color:#183128}
    #analise .sector-rank{text-align:right;color:#778981;font-size:.56rem;font-weight:750;white-space:nowrap}
    #analise .stars-premium{border-top:1px solid #e7eeea;background:#fcfdfc;padding:9px 12px 10px}
    #analise .stars-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:5px}
    #analise .stars-head b{font-size:.68rem;text-transform:uppercase;letter-spacing:.025em;color:#657a71}
    #analise .stars-team-block+.stars-team-block{margin-top:8px;padding-top:7px;border-top:1px dashed #e0e9e4}
    #analise .stars-team-name{font-size:.64rem;font-weight:900;color:#234b3c;margin-bottom:3px}
    #analise .analysis-star{display:grid;grid-template-columns:auto minmax(0,1fr) auto auto;gap:6px;align-items:center;padding:4px 0;min-width:0}
    #analise .analysis-star.hidden-star{display:none}
    #analise .analysis-star-pos{background:#e7f3ed;color:#176b4b;border-radius:999px;padding:2px 5px;font-size:.5rem;font-weight:900}
    #analise .analysis-star-name{font-size:.65rem;font-weight:800;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
    #analise .analysis-star-score{font-size:.65rem;font-weight:900;color:#176b4b;white-space:nowrap}
    #analise .star-actions{display:flex;gap:4px}
    #analise .star-actions button{border:1px solid #c8ddd3;background:#fff;color:#176b4b;border-radius:7px;padding:4px 6px;min-height:25px;font-size:.52rem;font-weight:850;cursor:pointer;white-space:nowrap}
    #analise .star-actions .to-monte{background:#e7f3ed;border-color:#e7f3ed}
    #analise .expand-stars{width:100%;margin-top:6px;border:0;border-top:1px dashed #dfe8e3;background:transparent;color:#176b4b;padding:7px 4px 1px;font-size:.58rem;font-weight:850;cursor:pointer}
    #analysisToast{position:fixed;left:50%;bottom:22px;transform:translateX(-50%) translateY(20px);z-index:80;background:#183128;color:#fff;border-radius:999px;padding:9px 14px;font-size:.72rem;font-weight:750;opacity:0;pointer-events:none;transition:.2s;box-shadow:0 8px 30px rgba(0,0,0,.18);max-width:calc(100vw - 28px);text-align:center}
    #analysisToast.show{opacity:1;transform:translateX(-50%) translateY(0)}

    @media(max-width:700px){
      #analise .hero{padding:16px 15px!important;margin-bottom:9px!important}
      #analise .hero h1{font-size:1.35rem!important;margin-bottom:3px!important}
      #analise .hero .lead{font-size:.78rem!important;line-height:1.42!important}
      #analise .analysis-method-note{font-size:.58rem;padding:6px 8px;margin-bottom:9px}
      #analise .round-summary{grid-template-columns:1fr 1fr;gap:6px;margin:7px 0 13px}
      #analise .summary-card{padding:8px 9px;border-radius:11px}
      #analise .summary-card small{font-size:.49rem}
      #analise .summary-card b{font-size:.79rem;margin-top:3px}
      #analise .summary-card span{font-size:.55rem}
      #analise .analysis-section-title{margin:13px 0 7px}
      #analise .analysis-section-title h2{font-size:.95rem}
      #analise .analysis-section-title span{font-size:.54rem}
      #analise #matches{grid-template-columns:1fr;gap:8px}
      #analise .match-head-premium{padding:9px 10px 8px}
      #analise .fixture-teams{font-size:.86rem}
      #analise .fixture-teams .venue{font-size:.63rem}
      #analise .match-read{font-size:.56rem;margin-top:4px}
      #analise .match-badge{font-size:.49rem;padding:2px 5px}
      #analise .sector-wrap{padding:7px 10px 8px}
      #analise .sector{padding:5px 0}
      #analise .sector-title{margin-bottom:3px}
      #analise .sector-title b{font-size:.61rem}
      #analise .sector-title span{font-size:.49rem}
      #analise .sector-row{grid-template-columns:61px minmax(70px,1fr) 34px 58px;gap:5px;font-size:.59rem;margin:3px 0}
      #analise .sector-rank{font-size:.49rem}
      #analise .stars-premium{padding:7px 10px 8px}
      #analise .stars-head b{font-size:.59rem}
      #analise .stars-team-name{font-size:.58rem}
      #analise .analysis-star{grid-template-columns:auto minmax(0,1fr) auto auto;gap:5px;padding:3px 0}
      #analise .analysis-star-pos{font-size:.46rem}
      #analise .analysis-star-name,#analise .analysis-star-score{font-size:.59rem}
      #analise .star-actions button{font-size:.47rem;padding:3px 5px;min-height:23px}
      #analise .expand-stars{font-size:.52rem;padding-top:6px}
    }
  `;

  let rendering = false;
  let observer = null;

  function injectStyle() {
    let style = document.getElementById('analise-premium-style');
    if (!style) {
      style = document.createElement('style');
      style.id = 'analise-premium-style';
      document.head.appendChild(style);
    }
    style.textContent = CSS;
  }

  function getPlayers() {
    try { return Array.isArray(players) ? players : []; } catch (_) { return []; }
  }

  function fmt(v, d = 2) {
    return Number(v || 0).toLocaleString('pt-BR', {minimumFractionDigits:d, maximumFractionDigits:d});
  }

  function avg(values) {
    return values.length ? values.reduce((s, v) => s + Number(v || 0), 0) / values.length : 0;
  }

  function fixtureFor(p) {
    try { return fixture(p); } catch (_) {
      const opp = p.sigla_adversario || '—';
      return p.mando === 'casa' ? `${p.sigla_clube} x ${opp}` : `${p.sigla_clube} @ ${opp}`;
    }
  }

  function buildGames() {
    const games = {};
    getPlayers().filter(p => Number(p.status_id) === 7).forEach(p => {
      const a = p.sigla_clube, b = p.sigla_adversario;
      if (!a || !b) return;
      const key = [a,b].sort().join('-');
      games[key] ||= {teams:{}};
      games[key].teams[a] ||= [];
      games[key].teams[a].push(p);
    });
    return Object.values(games).map(g => {
      const teams = Object.entries(g.teams).map(([team, ps]) => {
        const attackPlayers = ps.filter(p => ['MEI','ATA'].includes(p.posicao));
        const defensePlayers = ps.filter(p => ['GOL','LAT','ZAG'].includes(p.posicao));
        const home = ps.filter(p => p.mando === 'casa').length >= ps.length / 2;
        return {
          team, ps, home,
          attack: avg(attackPlayers.map(p => p.projecao)),
          defense: avg(defensePlayers.map(p => p.projecao)),
          composite: avg(ps.filter(p => p.posicao !== 'TEC').map(p => p.projecao))
        };
      });
      return {teams};
    }).filter(g => g.teams.length === 2);
  }

  function teamUniverse(games) {
    return games.flatMap(g => g.teams);
  }

  function rankInfo(value, allValues) {
    const sorted = allValues.slice().sort((a,b) => b-a);
    const index = sorted.findIndex(v => Math.abs(v-value) < 1e-9);
    const rank = index >= 0 ? index + 1 : sorted.filter(v => v > value).length + 1;
    const mean = avg(allValues);
    const delta = mean ? ((value / mean) - 1) * 100 : 0;
    return {rank, total:sorted.length, mean, delta};
  }

  function relativeText(value, values) {
    const r = rankInfo(value, values);
    const delta = Math.round(Math.abs(r.delta));
    const side = r.delta >= 0 ? 'acima' : 'abaixo';
    return `${r.rank}º/${r.total} · ${delta}% ${side} da média`;
  }

  function orderedTeams(game) {
    const home = game.teams.find(t => t.home);
    const away = game.teams.find(t => !t.home);
    return home && away ? [home, away] : game.teams;
  }

  function summaryHtml(games) {
    const teams = teamUniverse(games);
    if (!teams.length) return '';
    const bestAttack = teams.slice().sort((a,b)=>b.attack-a.attack)[0];
    const bestDefense = teams.slice().sort((a,b)=>b.defense-a.defense)[0];
    const gameStats = games.map(g => {
      const [a,b] = g.teams;
      return {g, gap:Math.abs(a.composite-b.composite), leader:a.composite>=b.composite?a:b, other:a.composite>=b.composite?b:a};
    });
    const biggest = gameStats.slice().sort((a,b)=>b.gap-a.gap)[0];
    const balanced = gameStats.slice().sort((a,b)=>a.gap-b.gap)[0];
    const [bh, ba] = biggest ? orderedTeams(biggest.g) : [];
    const [eh, ea] = balanced ? orderedTeams(balanced.g) : [];
    return `<div class="round-summary">
      <div class="summary-card"><small>🔥 Maior ataque projetado</small><b>${bestAttack.team}</b><span>${fmt(bestAttack.attack)} pts médios · ${relativeText(bestAttack.attack,teams.map(t=>t.attack))}</span></div>
      <div class="summary-card"><small>🛡 Setor defensivo em destaque</small><b>${bestDefense.team}</b><span>${fmt(bestDefense.defense)} pts médios · ${relativeText(bestDefense.defense,teams.map(t=>t.defense))}</span></div>
      <div class="summary-card"><small>⚔️ Maior diferença projetada</small><b>${bh?.team||'—'} × ${ba?.team||'—'}</b><span>${biggest?`${biggest.leader.team} tem o maior conjunto médio neste recorte`:'—'}</span></div>
      <div class="summary-card"><small>⚖️ Confronto mais equilibrado</small><b>${eh?.team||'—'} × ${ea?.team||'—'}</b><span>${balanced?'menor diferença entre as projeções médias dos setores':'—'}</span></div>
    </div>`;
  }

  function starRows(team) {
    const list = team.ps.filter(p => p.posicao !== 'TEC').slice().sort((a,b)=>Number(b.projecao||0)-Number(a.projecao||0));
    return list.map((p,i)=>`<div class="analysis-star ${i>=3?'hidden-star':''}" data-star-row>
      <span class="analysis-star-pos">${p.posicao}</span>
      <span class="analysis-star-name">${p.apelido}</span>
      <span class="analysis-star-score">${fmt(p.projecao)} pts</span>
      <span class="star-actions"><button type="button" data-analysis-player="${p.atleta_id}">Análise</button><button class="to-monte" type="button" data-monte-player="${p.atleta_id}">+ Montar</button></span>
    </div>`).join('');
  }

  function sectorRows(a, b, key, values) {
    const label = key === 'attack' ? 'Ataque' : 'Setor defensivo';
    const hint = key === 'attack' ? 'média MEI + ATA' : 'média GOL + LAT + ZAG';
    const max = Math.max(...values, 1);
    return `<div class="sector"><div class="sector-title"><b>${label}</b><span>${hint}</span></div>${[a,b].map(t=>`<div class="sector-row"><span class="sector-team">${t.home?'🏠':'✈️'} ${t.team}</span><div class="sector-bar"><i style="width:${Math.max(4,(t[key]/max)*100)}%"></i></div><span class="sector-value">${fmt(t[key])}</span><span class="sector-rank">${relativeText(t[key],values)}</span></div>`).join('')}</div>`;
  }

  function gameCard(game, allTeams, index) {
    const [a,b] = orderedTeams(game);
    const leader = a.composite >= b.composite ? a : b;
    const other = leader === a ? b : a;
    const diff = Math.abs(leader.composite-other.composite);
    const attackValues = allTeams.map(t=>t.attack);
    const defenseValues = allTeams.map(t=>t.defense);
    const read = diff < 0.35
      ? 'Projeções médias muito próximas entre os setores.'
      : `<b>${leader.team}</b> apresenta o maior conjunto médio de projeções neste confronto.`;
    return `<article class="card match decision-match" data-game-index="${index}">
      <div class="match-head-premium">
        <div class="fixture-line"><div class="fixture-teams"><span class="venue">🏠</span> ${a.team} <span style="color:#8a9993;font-weight:650">×</span> ${b.team} <span class="venue">✈️</span></div><span class="match-badge">Leitura pré-rodada</span></div>
        <div class="match-read">${read} <span>Não representa probabilidade de vitória.</span></div>
      </div>
      <div class="sector-wrap">${sectorRows(a,b,'attack',attackValues)}${sectorRows(a,b,'defense',defenseValues)}</div>
      <div class="stars-premium">
        <div class="stars-head"><b>Principais opções projetadas</b><span></span></div>
        <div class="stars-team-block"><div class="stars-team-name">${a.team}</div>${starRows(a)}</div>
        <div class="stars-team-block"><div class="stars-team-name">${b.team}</div>${starRows(b)}</div>
        <button class="expand-stars" type="button" data-expand-stars>+ Ver mais opções</button>
      </div>
    </article>`;
  }

  function showToast(text) {
    let toast = document.getElementById('analysisToast');
    if (!toast) {
      toast = document.createElement('div'); toast.id = 'analysisToast'; document.body.appendChild(toast);
    }
    toast.textContent = text; toast.classList.add('show');
    clearTimeout(showToast.t); showToast.t = setTimeout(()=>toast.classList.remove('show'),2400);
  }

  function openMonte() {
    document.querySelector('#nav button[data-page="monte"]')?.click();
    setTimeout(()=>document.getElementById('customPickers')?.scrollIntoView({behavior:'smooth',block:'start'}),80);
  }

  function addToMonte(id) {
    const p = getPlayers().find(x=>String(x.atleta_id)===String(id));
    if (!p) return;
    try {
      const pos = p.posicao;
      customForced[pos] = customForced[pos] || [];
      if (customForced[pos].some(x=>String(x)===String(id))) {
        showToast(`${p.apelido} já está escolhido.`); openMonte(); return;
      }
      const form = document.getElementById('customFormation')?.value || 'auto';
      const limit = maxSlotsFor(pos, form);
      if (limit <= 0 || customForced[pos].length >= limit) {
        showToast(`Sem vaga de ${pos} na formação atual.`); openMonte(); return;
      }
      customForced[pos].push(String(id));
      renderCustomPickers();
      showToast(`${p.apelido} adicionado às suas escolhas.`);
      openMonte();
    } catch (_) {
      showToast('Abra Montar para adicionar este jogador.'); openMonte();
    }
  }

  function bind(box) {
    box.querySelectorAll('[data-analysis-player]').forEach(btn=>btn.addEventListener('click',()=>{
      try { showPlayer(btn.dataset.analysisPlayer); } catch (_) {}
    }));
    box.querySelectorAll('[data-monte-player]').forEach(btn=>btn.addEventListener('click',()=>addToMonte(btn.dataset.montePlayer)));
    box.querySelectorAll('[data-expand-stars]').forEach(btn=>btn.addEventListener('click',()=>{
      const card = btn.closest('.decision-match');
      const expanded = btn.dataset.expanded === '1';
      card.querySelectorAll('.analysis-star').forEach((row,i)=>row.classList.toggle('hidden-star', expanded ? i>=3 : false));
      btn.dataset.expanded = expanded ? '0' : '1';
      btn.textContent = expanded ? '+ Ver mais opções' : '− Mostrar somente Top 3';
    }));
  }

  function renderPremium() {
    if (rendering) return;
    const section = document.getElementById('analise');
    const box = document.getElementById('matches');
    if (!section || !box || !getPlayers().length) return;
    rendering = true;
    const games = buildGames();
    const teams = teamUniverse(games);
    let note = section.querySelector('.analysis-method-note');
    if (!note) {
      note = document.createElement('div');
      note.className = 'analysis-method-note';
      section.querySelector('.hero')?.insertAdjacentElement('afterend', note);
    }
    note.innerHTML = '<b>Como ler:</b> “Ataque” é a média das projeções de MEI/ATA; “setor defensivo” é a média de GOL/LAT/ZAG. Portanto, número maior significa <b>maior pontuação projetada para jogadores daquele setor</b> — não mede gols sofridos, chance de vitória ou força defensiva real.';
    const oldTitle = Array.from(section.querySelectorAll(':scope > h2')).find(h=>/Confrontos/i.test(h.textContent||''));
    if (oldTitle) oldTitle.style.display = 'none';
    let summary = section.querySelector('.round-summary');
    if (!summary) {
      summary = document.createElement('div');
      summary.className = 'round-summary';
      note.insertAdjacentElement('afterend', summary);
    }
    summary.outerHTML = summaryHtml(games);
    let title = section.querySelector('.analysis-section-title');
    if (!title) {
      title = document.createElement('div'); title.className='analysis-section-title';
      box.insertAdjacentElement('beforebegin',title);
    }
    title.innerHTML = '<h2>Confrontos</h2><span>comparação relativa à rodada atual</span>';
    box.innerHTML = games.length ? games.map((g,i)=>gameCard(g,teams,i)).join('') : '<div class="empty">Confrontos não disponíveis.</div>';
    bind(box);
    const lead = section.querySelector('.hero .lead');
    if (lead) lead.textContent = 'Leitura pré-rodada dos confrontos, comparação dos setores e jogadores que mais merecem atenção.';
    rendering = false;
  }

  function watchLegacy() {
    const box = document.getElementById('matches');
    if (!box || observer) return;
    observer = new MutationObserver(()=>{
      if (rendering) return;
      if (box.querySelector('.match:not(.decision-match)')) setTimeout(renderPremium,0);
    });
    observer.observe(box,{childList:true,subtree:false});
  }

  function boot() {
    injectStyle();
    const wait = setInterval(()=>{
      if (!getPlayers().length || !document.getElementById('matches')) return;
      clearInterval(wait);
      watchLegacy();
      renderPremium();
    },120);
    setTimeout(()=>clearInterval(wait),20000);
  }

  boot();
})();
