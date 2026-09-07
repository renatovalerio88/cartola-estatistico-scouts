(function (root) {
  'use strict';

  const EPS = 1e-9;
  const BENCH_POSITIONS = ['GOL', 'LAT', 'ZAG', 'MEI', 'ATA'];

  function num(v) {
    const n = Number(v);
    return Number.isFinite(n) ? n : 0;
  }

  function playerId(p) {
    return String(p && p.atleta_id != null ? p.atleta_id : '');
  }

  function buildGroup(pool, need) {
    const sorted = pool.slice().sort((a, b) =>
      num(b.projecao) - num(a.projecao) ||
      num(a.preco) - num(b.preco) ||
      num(a.atleta_id) - num(b.atleta_id)
    );
    const n = sorted.length;
    const scorePrefix = new Array(n + 1).fill(0);
    for (let i = 0; i < n; i++) scorePrefix[i + 1] = scorePrefix[i] + num(sorted[i].projecao);

    const minCost = Array.from({ length: n + 1 }, () => new Array(need + 1).fill(Infinity));
    minCost[n][0] = 0;
    let cheapest = [];
    for (let i = n - 1; i >= 0; i--) {
      cheapest.push(num(sorted[i].preco));
      cheapest.sort((a, b) => a - b);
      if (cheapest.length > need) cheapest.length = need;
      minCost[i][0] = 0;
      let acc = 0;
      for (let k = 1; k <= need; k++) {
        if (k <= cheapest.length) {
          acc += cheapest[k - 1];
          minCost[i][k] = acc;
        }
      }
    }

    return {
      pool: sorted,
      need,
      maxScore(start, count) {
        if (count === 0) return 0;
        if (start + count > n) return -Infinity;
        return scorePrefix[start + count] - scorePrefix[start];
      },
      minCost(start, count) {
        if (count === 0) return 0;
        if (start > n) return Infinity;
        return minCost[start][count];
      }
    };
  }

  function seedFormation(groups, budget, maxClub) {
    let states = [{ sel: [], score: 0, cost: 0, clubs: {} }];
    for (const g of groups) {
      for (let slot = 0; slot < g.need; slot++) {
        const next = [];
        for (const s of states) {
          for (const p of g.pool.slice(0, 24)) {
            if (s.sel.some(x => playerId(x) === playerId(p))) continue;
            const club = String(p.sigla_clube || '');
            if ((s.clubs[club] || 0) >= maxClub) continue;
            const cost = s.cost + num(p.preco);
            if (cost > budget + EPS) continue;
            next.push({
              sel: s.sel.concat(p),
              score: s.score + num(p.projecao),
              cost,
              clubs: { ...s.clubs, [club]: (s.clubs[club] || 0) + 1 }
            });
          }
        }
        next.sort((a, b) => b.score - a.score || a.cost - b.cost);
        states = next.slice(0, 700);
        if (!states.length) return null;
      }
    }
    return states[0] || null;
  }

  function solveFormation(players, formation, budget, options) {
    const formations = options.formations;
    const eligible = options.eligible || (() => true);
    const maxClub = options.maxClub == null ? 3 : Number(options.maxClub);
    const req = formations[formation];
    if (!req) return null;

    const eligiblePlayers = players.filter(eligible);
    const quotas = Object.entries(req).filter(([, q]) => Number(q) > 0);
    if (eligiblePlayers.some(p => p.posicao === 'TEC')) quotas.push(['TEC', 1]);

    const groups = quotas.map(([pos, need]) => {
      const pool = eligiblePlayers.filter(p => p.posicao === pos);
      return { pos, ...buildGroup(pool, Number(need)) };
    });
    if (groups.some(g => g.pool.length < g.need)) return null;

    groups.sort((a, b) => (a.pool.length / a.need) - (b.pool.length / b.need));

    const futureMax = new Array(groups.length + 1).fill(0);
    const futureMin = new Array(groups.length + 1).fill(0);
    for (let i = groups.length - 1; i >= 0; i--) {
      futureMax[i] = futureMax[i + 1] + groups[i].maxScore(0, groups[i].need);
      futureMin[i] = futureMin[i + 1] + groups[i].minCost(0, groups[i].need);
    }
    if (futureMin[0] > budget + EPS) return null;

    const seed = seedFormation(groups, budget, maxClub);
    let best = seed ? { sel: seed.sel.slice(), score: seed.score, cost: seed.cost } : null;
    let bestScore = best ? best.score : -Infinity;
    const selected = [];
    const clubs = Object.create(null);

    function solveGroup(gi, score, cost) {
      if (gi >= groups.length) {
        if (score > bestScore + EPS || (Math.abs(score - bestScore) <= EPS && (!best || cost < best.cost - EPS))) {
          bestScore = score;
          best = { sel: selected.slice(), score, cost };
        }
        return;
      }
      if (score + futureMax[gi] <= bestScore + EPS) return;
      if (cost + futureMin[gi] > budget + EPS) return;

      const g = groups[gi];

      function choose(start, left, localScore, localCost) {
        if (left === 0) {
          solveGroup(gi + 1, localScore, localCost);
          return;
        }
        if (g.pool.length - start < left) return;
        const maxHere = g.maxScore(start, left);
        if (localScore + maxHere + futureMax[gi + 1] <= bestScore + EPS) return;
        const minHere = g.minCost(start, left);
        if (localCost + minHere + futureMin[gi + 1] > budget + EPS) return;

        const last = g.pool.length - left;
        for (let i = start; i <= last; i++) {
          const p = g.pool[i];
          const club = String(p.sigla_clube || '');
          if ((clubs[club] || 0) >= maxClub) continue;
          const nextCost = localCost + num(p.preco);
          if (nextCost > budget + EPS) continue;

          const optimistic = localScore + num(p.projecao) + g.maxScore(i + 1, left - 1) + futureMax[gi + 1];
          if (optimistic <= bestScore + EPS) break;

          selected.push(p);
          clubs[club] = (clubs[club] || 0) + 1;
          choose(i + 1, left - 1, localScore + num(p.projecao), nextCost);
          clubs[club] -= 1;
          if (!clubs[club]) delete clubs[club];
          selected.pop();
        }
      }

      choose(0, g.need, score, cost);
    }

    solveGroup(0, 0, 0);
    return best;
  }

  function optimize(players, budget, forced, options) {
    const forms = forced && forced !== 'auto' ? [forced] : Object.keys(options.formations || {});
    let best = null;
    for (const formation of forms) {
      const solved = solveFormation(players, formation, Number(budget), options);
      if (solved && (!best || solved.score > best.score + EPS || (Math.abs(solved.score - best.score) <= EPS && solved.cost < best.cost - EPS))) {
        best = { ...solved, formation };
      }
    }
    return best;
  }

  function selectCaptain(starters) {
    const candidates = (starters || []).filter(p => p && p.posicao !== 'TEC');
    if (!candidates.length) return null;
    return candidates.slice().sort((a, b) =>
      num(b.projecao) - num(a.projecao) ||
      num(b.titularidade) - num(a.titularidade) ||
      num(a.preco) - num(b.preco) ||
      num(a.atleta_id) - num(b.atleta_id)
    )[0];
  }

  function selectBench(players, starters, options) {
    const eligible = options && options.eligible ? options.eligible : (() => true);
    const used = new Set((starters || []).map(playerId));
    const bench = [];

    for (const pos of BENCH_POSITIONS) {
      const samePosStarters = (starters || []).filter(p => p && p.posicao === pos);
      if (!samePosStarters.length) continue;

      const priceCap = Math.min(...samePosStarters.map(p => num(p.preco)));
      const candidates = (players || []).filter(p =>
        p &&
        p.posicao === pos &&
        !used.has(playerId(p)) &&
        eligible(p) &&
        num(p.preco) <= priceCap + EPS
      );

      if (!candidates.length) continue;
      candidates.sort((a, b) =>
        num(b.projecao) - num(a.projecao) ||
        num(a.preco) - num(b.preco) ||
        num(a.atleta_id) - num(b.atleta_id)
      );
      const chosen = candidates[0];
      bench.push({
        ...chosen,
        reserva_posicao: pos,
        teto_preco_reserva: priceCap,
        reserva_luxo: false
      });
      used.add(playerId(chosen));
    }

    let luxury = null;
    let bestGain = -Infinity;
    for (const reserve of bench) {
      const samePosStarters = (starters || []).filter(p => p && p.posicao === reserve.posicao);
      if (!samePosStarters.length) continue;
      const weakestProjectedStarter = samePosStarters.slice().sort((a, b) =>
        num(a.projecao) - num(b.projecao) || num(a.atleta_id) - num(b.atleta_id)
      )[0];
      const gain = num(reserve.projecao) - num(weakestProjectedStarter.projecao);
      if (
        luxury === null ||
        gain > bestGain + EPS ||
        (Math.abs(gain - bestGain) <= EPS && num(reserve.projecao) > num(luxury.projecao) + EPS) ||
        (Math.abs(gain - bestGain) <= EPS && Math.abs(num(reserve.projecao) - num(luxury.projecao)) <= EPS && num(reserve.atleta_id) < num(luxury.atleta_id))
      ) {
        bestGain = gain;
        luxury = reserve;
      }
    }

    if (luxury) {
      for (const reserve of bench) reserve.reserva_luxo = playerId(reserve) === playerId(luxury);
    }

    return {
      bench,
      reservaLuxo: luxury,
      reservaLuxoAtletaId: luxury ? luxury.atleta_id : null
    };
  }

  function completeTeam(players, team, options) {
    if (!team || !Array.isArray(team.sel)) return null;
    const captain = selectCaptain(team.sel);
    const benchInfo = selectBench(players, team.sel, options || {});
    return {
      ...team,
      captain,
      captainAtletaId: captain ? captain.atleta_id : null,
      bench: benchInfo.bench,
      reservaLuxo: benchInfo.reservaLuxo,
      reservaLuxoAtletaId: benchInfo.reservaLuxoAtletaId
    };
  }

  const api = { optimize, solveFormation, selectCaptain, selectBench, completeTeam };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.V3ExactOptimizer = api;
})(typeof window !== 'undefined' ? window : globalThis);

/* Premium presentation layer for the public Time Sugerido page. */
(function (root) {
  'use strict';
  if (typeof document === 'undefined') return;

  const CSS = `
    #time .hero{display:none}
    #time{--premium-line:#e2ebe7;--premium-soft:#f4f8f6;--premium-gold:#b88b2f;--premium-gold-soft:#fff8e8}
    #time #timeStatus{border:0;background:transparent;padding:0;margin:0 0 9px;color:inherit}
    #time .premium-status{display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap}
    #time .premium-titleblock{display:flex;align-items:baseline;gap:7px;min-width:0}
    #time .premium-kicker{font-size:.69rem;font-weight:850;letter-spacing:.075em;color:#668078;text-transform:uppercase}
    #time .premium-round{font-size:.69rem;font-weight:850;color:#176b4b;background:#e7f3ed;border-radius:999px;padding:4px 8px}
    #time .premium-chips{display:flex;gap:6px;flex-wrap:wrap}
    #time .premium-chip{display:inline-flex;align-items:center;gap:5px;border:1px solid var(--premium-line);background:#fff;border-radius:999px;padding:5px 8px;font-size:.72rem;font-weight:780;color:#29463c}
    #time .premium-chip.gold{border-color:#e8d8af;background:var(--premium-gold-soft);color:#715719}
    #time #teamMetrics{display:grid;grid-template-columns:1.35fr 1fr .78fr;gap:0;background:#fff;border:1px solid var(--premium-line);border-radius:17px;overflow:hidden;box-shadow:0 9px 25px rgba(22,69,50,.055);margin:8px 0 12px}
    #time #teamMetrics .card{border:0;border-radius:0;box-shadow:none;padding:13px 15px;background:transparent;min-width:0}
    #time #teamMetrics .card:not(:last-child){border-right:1px solid var(--premium-line)}
    #time #teamMetrics .metric small{font-size:.64rem;text-transform:uppercase;letter-spacing:.045em;color:#85938e;font-weight:650}
    #time #teamMetrics .metric b{font-size:1.13rem;color:#254037;margin-top:3px;font-weight:760}
    #time #teamMetrics .card:first-child .metric b{font-size:1.58rem;color:#0e6948;font-weight:900}
    #time details.premium-adjust{margin:7px 0 13px;border:1px solid var(--premium-line);border-radius:13px;background:#fff;overflow:hidden}
    #time details.premium-adjust>summary{list-style:none;cursor:pointer;padding:10px 13px;font-size:.78rem;font-weight:780;color:#176b4b;display:flex;align-items:center;justify-content:space-between;min-height:42px}
    #time details.premium-adjust>summary::-webkit-details-marker{display:none}
    #time details.premium-adjust>summary:before{content:'⚙';font-size:.78rem;margin-right:7px;color:#769289}
    #time details.premium-adjust>summary:after{content:'＋';font-size:.95rem;color:#829991;margin-left:auto}
    #time details.premium-adjust[open]>summary:after{content:'−'}
    #time details.premium-adjust .controls{margin:0;padding:11px 13px 13px;border-top:1px solid #edf2ef}
    #time h2{margin:19px 0 8px;font-size:1.03rem}
    #time .pitch{min-height:362px;padding:8px 6px;border-radius:22px;background:radial-gradient(circle at 50% 50%,transparent 0 34px,rgba(255,255,255,.13) 35px 36px,transparent 37px),linear-gradient(to bottom,transparent calc(50% - .5px),rgba(255,255,255,.15) calc(50% - .5px),rgba(255,255,255,.15) calc(50% + .5px),transparent calc(50% + .5px)),linear-gradient(180deg,#47986f 0%,#2f7857 100%);box-shadow:0 17px 36px rgba(31,102,71,.15);border:1px solid rgba(255,255,255,.2)}
    #time .pitch:before{inset:10px;border-color:rgba(255,255,255,.3);border-radius:11px}
    #time .pitch:after{display:none}
    #time .line{min-height:67px}
    #time .player-ball{width:110px;padding:2px 3px;position:relative}
    #time .ball{width:44px;height:44px;border-width:2px;box-shadow:0 6px 14px rgba(0,0,0,.13);font-size:.62rem;letter-spacing:.02em}
    #time .captain .ball{outline:2px solid rgba(195,147,42,.95);outline-offset:2px;box-shadow:0 0 0 4px rgba(195,147,42,.11),0 6px 14px rgba(0,0,0,.13)}
    #time .captain-badge{position:absolute;left:calc(50% + 12px);top:-1px;z-index:3;width:19px;height:19px;border-radius:50%;display:flex;align-items:center;justify-content:center;background:#c3972f;color:#fff;font-size:.57rem;font-weight:900;border:2px solid rgba(255,255,255,.9);box-shadow:0 3px 8px rgba(0,0,0,.18)}
    #time .player-ball .name{font-size:.72rem;line-height:1.1;margin-top:5px;white-space:normal;overflow:hidden;text-overflow:clip;display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:2;height:1.58em;text-shadow:0 1px 2px rgba(0,0,0,.2);font-weight:780}
    #time .player-ball .pts{font-size:.68rem;font-weight:850}
    #time .player-ball .fixture{font-size:.54rem;margin-top:2px;color:rgba(255,255,255,.8);display:flex;align-items:center;justify-content:center;gap:4px;white-space:nowrap}
    #time .venue-badge{font-size:.45rem;font-weight:850;letter-spacing:.025em;padding:1px 4px;border-radius:999px;background:rgba(255,255,255,.15);border:1px solid rgba(255,255,255,.16);color:#fff;text-transform:uppercase}
    #time .bench{display:grid;grid-template-columns:1fr;gap:0;padding:0;background:#fff;border:1px solid var(--premium-line);border-radius:16px;overflow:hidden;box-shadow:0 9px 25px rgba(22,69,50,.045)}
    #time .bench .mini{border:0;border-radius:0;box-shadow:none;padding:9px 42px 9px 13px;position:relative;background:#fff;min-height:61px;transition:background .14s ease,transform .14s ease}
    #time .bench .mini:not(:last-child){border-bottom:1px solid var(--premium-line)}
    #time .bench .mini:after{content:'›';position:absolute;right:15px;top:50%;transform:translateY(-50%);font-size:1.45rem;font-weight:300;color:#9aaba4}
    #time .bench .mini:active{background:#f5f8f6;transform:scale(.998)}
    #time .bench .mini .pill{font-size:.62rem;padding:3px 7px;font-weight:780}
    #time .bench .mini b{font-size:.9rem;margin:4px 0 1px;font-weight:780}
    #time .bench .mini small{font-size:.72rem;line-height:1.3;font-weight:450}
    #time .bench .mini.luxury{background:linear-gradient(90deg,#fff9eb,#fff);box-shadow:inset 3px 0 0 #c9a04a}
    #time .bench .mini.luxury .pill{background:#fff1cc;color:#6f581d}
    #time .alternatives{grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:16px}
    #time .alternatives .card{box-shadow:none;border:0;background:transparent;border-radius:0;padding:0 2px 3px}
    #time .altgroup h3{font-size:.86rem;color:#2a443a;margin:0 0 3px;font-weight:780}
    #time .altplayer{padding:10px 0;position:relative;border-top:1px solid #e5ece8}
    #time .altplayer b{font-size:.87rem;padding-right:5px;font-weight:780}
    #time .altplayer small{line-height:1.42;font-weight:430}
    #time .altplayer small .good,#time .altplayer small .warn,#time .altplayer small .bad{display:inline-flex;border-radius:999px;padding:2px 6px;font-size:.64rem;font-weight:780}
    #time .altplayer small .good{background:#e8f2ed;color:#1f7152}
    #time .altplayer small .warn{background:#f7f1df;color:#8a7028}
    #time .altplayer small .bad{background:#f3f1ed;color:#7c6b55}
    #time .altpts{font-size:.98rem;min-width:68px;text-align:right;font-weight:900}
    #time .altpts:before{content:'proj.';font-size:.57rem;font-weight:650;color:#93a09b;display:block;line-height:1.05;text-transform:lowercase}
    @media(max-width:700px){
      header .top{padding:8px 12px 5px}
      header .brand{font-size:.98rem}
      header .sub{font-size:.64rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:270px}
      header .roundbadge{font-size:.64rem;padding:5px 8px}
      header .nav{padding-top:7px}
      header .nav button{min-height:39px;padding:7px 10px;font-size:.84rem}
      #time{padding-top:0}
      #time .premium-status{align-items:flex-start}
      #time .premium-titleblock{width:100%;justify-content:space-between}
      #time .premium-chips{width:100%}
      #time .premium-chip{font-size:.68rem;padding:4px 7px}
      #time #teamMetrics{grid-template-columns:1.42fr 1fr .7fr;border-radius:15px}
      #time #teamMetrics .card{padding:9px 9px}
      #time #teamMetrics .metric small{font-size:.55rem;letter-spacing:.025em}
      #time #teamMetrics .metric b{font-size:.88rem;white-space:nowrap}
      #time #teamMetrics .card:first-child .metric b{font-size:1.18rem}
      #time details.premium-adjust{margin:6px 0 11px}
      #time details.premium-adjust>summary{padding:8px 11px;min-height:38px;font-size:.74rem}
      #time .pitch{min-height:310px;padding:5px 2px;border-radius:19px}
      #time .pitch:before{inset:8px}
      #time .line{min-height:56px;gap:1px}
      #time .player-ball{width:68px;padding:1px}
      #time .ball{width:35px;height:35px;font-size:.51rem}
      #time .captain-badge{left:calc(50% + 9px);width:17px;height:17px;font-size:.49rem}
      #time .player-ball .name{font-size:.58rem;line-height:1.08;height:1.28em;-webkit-line-clamp:2}
      #time .player-ball .pts{font-size:.56rem}
      #time .player-ball .fixture{font-size:.46rem;letter-spacing:-.01em;gap:2px}
      #time .venue-badge{font-size:.38rem;padding:1px 3px}
      #time .bench .mini{padding:8px 38px 8px 11px;min-height:57px}
      #time .bench .mini b{font-size:.87rem}
      #time .alternatives{grid-template-columns:1fr;gap:13px}
    }
    @media(max-width:430px){
      header .sub{max-width:235px}
      #time #teamMetrics .card{padding:9px 7px}
      #time #teamMetrics .metric b{font-size:.83rem}
      #time #teamMetrics .card:first-child .metric b{font-size:1.1rem}
      #time .pitch{min-height:300px}
      #time .line{min-height:54px}
      #time .player-ball{width:59px}
      #time .ball{width:34px;height:34px}
      #time .player-ball .name{font-size:.55rem}
      #time .player-ball .pts{font-size:.53rem}
      #time .player-ball .fixture{font-size:.43rem}
    }
  `;

  function injectStyle() {
    if (document.getElementById('premium-time-style')) return;
    const style = document.createElement('style');
    style.id = 'premium-time-style';
    style.textContent = CSS;
    document.head.appendChild(style);
  }

  function compactControls(section) {
    const controls = section.querySelector(':scope > .controls');
    if (!controls || controls.closest('details.premium-adjust')) return;
    const details = document.createElement('details');
    details.className = 'premium-adjust';
    const summary = document.createElement('summary');
    summary.textContent = 'Ajustar escalação';
    controls.parentNode.insertBefore(details, controls);
    details.appendChild(summary);
    details.appendChild(controls);
  }

  function enhanceStatus(section) {
    const el = section.querySelector('#timeStatus');
    if (!el) return;
    const raw = (el.textContent || '').trim();
    const m = raw.match(/^Rodada\s+(\d+)\s*·\s*formação\s+([^·]+)\s*·\s*capitão\s+([^·]+)\s*·\s*Reserva de Luxo\s+(.+?)\.?$/i);
    if (!m || el.dataset.premiumRaw === raw) return;
    el.dataset.premiumRaw = raw;
    el.innerHTML = `<div class="premium-status"><div class="premium-titleblock"><span class="premium-kicker">Time Sugerido</span><span class="premium-round">R${m[1]} · ${m[2].trim()}</span></div><div class="premium-chips"><span class="premium-chip">© ${m[3].trim()}</span><span class="premium-chip gold">★ ${m[4].trim()}</span></div></div>`;
  }

  function positionOf(node) {
    const ball = node && node.querySelector('.ball');
    if (!ball) return '';
    return (ball.textContent || '').replace(/^C\s*·\s*/i, '').trim().toUpperCase();
  }

  function refineCaptain(section) {
    section.querySelectorAll('.player-ball.captain').forEach(node => {
      const ball = node.querySelector('.ball');
      if (!ball) return;
      ball.textContent = (ball.textContent || '').replace(/^C\s*·\s*/i, '').trim();
      if (!node.querySelector('.captain-badge')) {
        const badge = document.createElement('span');
        badge.className = 'captain-badge';
        badge.textContent = 'C';
        badge.setAttribute('aria-label', 'Capitão');
        node.appendChild(badge);
      }
    });
  }

  function reorderDefense(section) {
    section.querySelectorAll('#pitch .line').forEach(line => {
      const nodes = Array.from(line.children).filter(n => n.classList && n.classList.contains('player-ball'));
      if (nodes.length !== 4) return;
      const lats = nodes.filter(n => positionOf(n) === 'LAT');
      const zags = nodes.filter(n => positionOf(n) === 'ZAG');
      if (lats.length !== 2 || zags.length !== 2) return;
      const desired = [lats[0], zags[0], zags[1], lats[1]];
      if (nodes.every((n, i) => n === desired[i])) return;
      desired.forEach(n => line.appendChild(n));
    });
  }

  function enhanceFixtures(section) {
    section.querySelectorAll('.player-ball .fixture').forEach(el => {
      const raw = (el.textContent || '').trim().replace(/\s*·\s*(Casa|Fora)$/i, '');
      if (!raw) return;
      const venue = raw.includes(' x ') ? 'Casa' : raw.includes(' @ ') ? 'Fora' : '';
      if (!venue) return;
      const signature = `${raw}|${venue}`;
      if (el.dataset.premiumFixture === signature) return;
      el.dataset.premiumFixture = signature;
      el.innerHTML = `<span>${raw}</span><span class="venue-badge">${venue}</span>`;
    });
    section.querySelectorAll('.bench .mini small').forEach(el => {
      const cleaned = (el.textContent || '').replace(/\s*·?\s*toque para detalhes\s*/gi, '').trim();
      if (cleaned !== el.textContent.trim()) el.textContent = cleaned;
    });
  }

  function shortenAlternativesIntro(section) {
    const heading = Array.from(section.querySelectorAll('h2')).find(h => (h.textContent || '').trim() === 'Outras boas opções');
    if (!heading) return;
    let node = heading.nextElementSibling;
    if (!node || node.id === 'alternatives') return;
    const text = (node.textContent || '').trim();
    if (/Três alternativas por posição/i.test(text) || /3 alternativas por posição/i.test(text)) {
      node.textContent = '3 alternativas por posição. Toque para entender a projeção.';
    }
  }

  function runEnhancements() {
    const section = document.getElementById('time');
    if (!section) return;
    compactControls(section);
    enhanceStatus(section);
    refineCaptain(section);
    reorderDefense(section);
    enhanceFixtures(section);
    shortenAlternativesIntro(section);
  }

  function boot() {
    injectStyle();
    runEnhancements();
    const section = document.getElementById('time');
    if (!section || section.dataset.premiumObserved === '1') return;
    section.dataset.premiumObserved = '1';
    let queued = false;
    const observer = new MutationObserver(() => {
      if (queued) return;
      queued = true;
      requestAnimationFrame(() => {
        queued = false;
        runEnhancements();
      });
    });
    observer.observe(section, { childList: true, subtree: true, characterData: true });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once: true });
  else boot();
})(typeof window !== 'undefined' ? window : globalThis);