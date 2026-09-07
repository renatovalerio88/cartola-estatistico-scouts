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

/*
 * Premium presentation layer for the public "Time Sugerido" page.
 * Deliberately isolated from optimization/model logic above.
 */
(function (root) {
  'use strict';
  if (typeof document === 'undefined') return;

  const CSS = `
    #time .hero{display:none}
    #time{--premium-line:#e2ebe7;--premium-soft:#f4f8f6;--premium-gold:#c79a32}
    #time #timeStatus{border:0;background:transparent;padding:0;margin:0 0 12px;color:inherit}
    #time .premium-status{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap}
    #time .premium-titleblock{display:flex;align-items:baseline;gap:7px;min-width:0}
    #time .premium-kicker{font-size:.72rem;font-weight:900;letter-spacing:.08em;color:#668078;text-transform:uppercase}
    #time .premium-round{font-size:.72rem;font-weight:900;color:#176b4b;background:#e7f3ed;border-radius:999px;padding:4px 8px}
    #time .premium-chips{display:flex;gap:6px;flex-wrap:wrap}
    #time .premium-chip{display:inline-flex;align-items:center;gap:5px;border:1px solid var(--premium-line);background:#fff;border-radius:999px;padding:6px 9px;font-size:.75rem;font-weight:800;color:#29463c}
    #time .premium-chip.gold{border-color:#ead9ad;background:#fffaf0;color:#7c5b13}
    #time #teamMetrics{display:grid;grid-template-columns:1.25fr 1fr .8fr;gap:0;background:#fff;border:1px solid var(--premium-line);border-radius:18px;overflow:hidden;box-shadow:0 10px 28px rgba(22,69,50,.06);margin:10px 0 14px}
    #time #teamMetrics .card{border:0;border-radius:0;box-shadow:none;padding:14px 16px;background:transparent;min-width:0}
    #time #teamMetrics .card:not(:last-child){border-right:1px solid var(--premium-line)}
    #time #teamMetrics .metric small{font-size:.68rem;text-transform:uppercase;letter-spacing:.05em;color:#7b8d86}
    #time #teamMetrics .metric b{font-size:1.25rem;color:#183128;margin-top:3px}
    #time #teamMetrics .card:first-child .metric b{font-size:1.55rem;color:#0e6948}
    #time details.premium-adjust{margin:10px 0 16px;border:1px solid var(--premium-line);border-radius:15px;background:#fff;overflow:hidden}
    #time details.premium-adjust>summary{list-style:none;cursor:pointer;padding:12px 14px;font-size:.82rem;font-weight:850;color:#176b4b;display:flex;align-items:center;justify-content:space-between}
    #time details.premium-adjust>summary::-webkit-details-marker{display:none}
    #time details.premium-adjust>summary:after{content:'＋';font-size:1rem;color:#769289}
    #time details.premium-adjust[open]>summary:after{content:'−'}
    #time details.premium-adjust .controls{margin:0;padding:0 14px 14px;border-top:1px solid #edf2ef;padding-top:12px}
    #time h2{margin:22px 0 9px;font-size:1.06rem}
    #time .pitch{min-height:390px;padding:10px 8px;border-radius:24px;background:linear-gradient(180deg,#45956d 0%,#2f7857 100%);box-shadow:0 18px 38px rgba(31,102,71,.17);border:1px solid rgba(255,255,255,.22)}
    #time .pitch:before{inset:12px;border-color:rgba(255,255,255,.34);border-radius:12px}
    #time .pitch:after{display:none}
    #time .line{min-height:72px}
    #time .player-ball{width:112px;padding:2px 3px}
    #time .ball{width:46px;height:46px;border-width:2px;box-shadow:0 7px 16px rgba(0,0,0,.14);font-size:.64rem;letter-spacing:.02em}
    #time .captain .ball{outline:3px solid rgba(218,170,58,.95);outline-offset:2px;box-shadow:0 0 0 5px rgba(218,170,58,.12),0 7px 16px rgba(0,0,0,.14)}
    #time .player-ball .name{font-size:.74rem;line-height:1.12;margin-top:5px;white-space:normal;overflow:visible;text-overflow:clip;display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:2;min-height:1.68em;text-shadow:0 1px 2px rgba(0,0,0,.22)}
    #time .player-ball .pts{font-size:.69rem;font-weight:800}
    #time .player-ball .fixture{font-size:.57rem;margin-top:2px;color:rgba(255,255,255,.84)}
    #time .bench{display:grid;grid-template-columns:1fr;gap:0;padding:0;background:#fff;border:1px solid var(--premium-line);border-radius:18px;overflow:hidden;box-shadow:0 10px 28px rgba(22,69,50,.05)}
    #time .bench .mini{border:0;border-radius:0;box-shadow:none;padding:11px 44px 11px 14px;position:relative;background:#fff;min-height:72px}
    #time .bench .mini:not(:last-child){border-bottom:1px solid var(--premium-line)}
    #time .bench .mini:after{content:'›';position:absolute;right:16px;top:50%;transform:translateY(-50%);font-size:1.55rem;font-weight:300;color:#9aaba4}
    #time .bench .mini .pill{font-size:.65rem;padding:3px 7px}
    #time .bench .mini b{font-size:.93rem;margin:5px 0 1px}
    #time .bench .mini small{font-size:.74rem;line-height:1.35}
    #time .bench .mini.luxury{background:linear-gradient(90deg,#fffaf0,#fff);box-shadow:inset 3px 0 0 #d6ad4f}
    #time .bench .mini.luxury .pill{background:#fff2cf;color:#735817}
    #time .alternatives{grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:10px}
    #time .alternatives .card{box-shadow:0 8px 24px rgba(22,69,50,.045);border-color:var(--premium-line)}
    #time .altgroup h3{font-size:.88rem;color:#2a443a;margin-bottom:4px}
    #time .altplayer{padding:11px 0;position:relative}
    #time .altplayer b{font-size:.88rem;padding-right:5px}
    #time .altplayer small{line-height:1.45}
    #time .altplayer small .good,#time .altplayer small .warn,#time .altplayer small .bad{display:inline-flex;border-radius:999px;padding:2px 6px;font-size:.66rem;font-weight:850}
    #time .altplayer small .good{background:#e7f3ed}
    #time .altplayer small .warn{background:#fff4d7}
    #time .altplayer small .bad{background:#fdeaea}
    #time .altpts{font-size:.95rem;min-width:70px;text-align:right}
    #time .altpts:before{content:'Proj. ';font-size:.62rem;font-weight:750;color:#879891;display:block;line-height:1.1}
    @media(max-width:700px){
      #time{padding-top:2px}
      #time .premium-status{align-items:flex-start}
      #time .premium-titleblock{width:100%;justify-content:space-between}
      #time .premium-chips{width:100%}
      #time .premium-chip{font-size:.71rem;padding:5px 8px}
      #time #teamMetrics{grid-template-columns:1.35fr 1fr .72fr;border-radius:16px}
      #time #teamMetrics .card{padding:11px 10px}
      #time #teamMetrics .metric small{font-size:.58rem;letter-spacing:.03em}
      #time #teamMetrics .metric b{font-size:1rem;white-space:nowrap}
      #time #teamMetrics .card:first-child .metric b{font-size:1.22rem}
      #time .pitch{min-height:342px;padding:7px 2px;border-radius:20px}
      #time .pitch:before{inset:9px}
      #time .line{min-height:62px;gap:1px}
      #time .player-ball{width:69px;padding:1px}
      #time .ball{width:37px;height:37px;font-size:.53rem}
      #time .player-ball .name{font-size:.59rem;line-height:1.08;min-height:1.3em;-webkit-line-clamp:2}
      #time .player-ball .pts{font-size:.58rem}
      #time .player-ball .fixture{font-size:.49rem;letter-spacing:-.01em}
      #time .bench .mini{padding:10px 40px 10px 12px;min-height:66px}
      #time .bench .mini b{font-size:.9rem}
      #time .alternatives{grid-template-columns:1fr}
    }
    @media(max-width:430px){
      #time #teamMetrics .card{padding:10px 8px}
      #time #teamMetrics .metric b{font-size:.93rem}
      #time #teamMetrics .card:first-child .metric b{font-size:1.12rem}
      #time .pitch{min-height:326px}
      #time .line{min-height:59px}
      #time .player-ball{width:60px}
      #time .ball{width:35px;height:35px}
      #time .player-ball .name{font-size:.56rem}
      #time .player-ball .pts{font-size:.55rem}
      #time .player-ball .fixture{font-size:.46rem}
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

  function enhanceFixtures(section) {
    section.querySelectorAll('.player-ball .fixture').forEach(el => {
      const raw = (el.textContent || '').trim();
      if (!raw || /·\s*(Casa|Fora)$/i.test(raw)) return;
      if (raw.includes(' x ')) el.textContent = `${raw} · Casa`;
      else if (raw.includes(' @ ')) el.textContent = `${raw} · Fora`;
    });
    section.querySelectorAll('.bench .mini small').forEach(el => {
      const cleaned = (el.textContent || '').replace(/\s*·?\s*toque para detalhes\s*/gi, '').trim();
      if (cleaned !== el.textContent.trim()) el.textContent = cleaned;
    });
  }

  function runEnhancements() {
    const section = document.getElementById('time');
    if (!section) return;
    compactControls(section);
    enhanceStatus(section);
    enhanceFixtures(section);
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
