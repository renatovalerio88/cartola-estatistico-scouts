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
    #time{--premium-line:#e1ebe6;--premium-soft:#f4f8f6;--premium-gold:#b88b2f;--premium-gold-soft:#fff8e8}
    #time #timeStatus{border:0;background:transparent;padding:0;margin:0 0 9px;color:inherit}
    #time .premium-status{display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap}
    #time .premium-titleblock{display:flex;align-items:baseline;gap:7px;min-width:0}
    #time .premium-kicker{font-size:.69rem;font-weight:850;letter-spacing:.075em;color:#668078;text-transform:uppercase}
    #time .premium-round{font-size:.69rem;font-weight:850;color:#176b4b;background:#e7f3ed;border-radius:999px;padding:4px 8px}
    #time .premium-chips{display:flex;gap:6px;flex-wrap:wrap}
    #time .premium-chip{display:inline-flex;align-items:center;gap:5px;border:1px solid var(--premium-line);background:#fff;border-radius:999px;padding:5px 8px;font-size:.72rem;font-weight:780;color:#29463c}
    #time .premium-chip.gold{border-color:#e8d8af;background:var(--premium-gold-soft);color:#715719}

    #time #teamMetrics{display:grid;grid-template-columns:1.42fr 1fr .75fr;gap:0;background:#fff;border:1px solid var(--premium-line);border-radius:17px;overflow:hidden;box-shadow:0 9px 25px rgba(22,69,50,.055);margin:8px 0 12px}
    #time #teamMetrics .card{border:0;border-radius:0;box-shadow:none;padding:13px 15px;background:transparent;min-width:0}
    #time #teamMetrics .card:not(:last-child){border-right:1px solid var(--premium-line)}
    #time #teamMetrics .metric small{font-size:.63rem;text-transform:uppercase;letter-spacing:.04em;color:#85938e;font-weight:650}
    #time #teamMetrics .metric b{font-size:1.1rem;color:#254037;margin-top:3px;font-weight:760}
    #time #teamMetrics .card:first-child .metric b{font-size:1.58rem;color:#0e6948;font-weight:900}

    #time details.premium-adjust{margin:7px 0 13px;border:1px solid var(--premium-line);border-radius:13px;background:#fff;overflow:hidden}
    #time details.premium-adjust>summary{list-style:none;cursor:pointer;padding:9px 12px;font-size:.77rem;font-weight:780;color:#176b4b;display:flex;align-items:center;min-height:40px}
    #time details.premium-adjust>summary::-webkit-details-marker{display:none}
    #time details.premium-adjust>summary:before{content:'⚙';font-size:.76rem;margin-right:7px;color:#769289}
    #time details.premium-adjust>summary:after{content:'＋';font-size:.93rem;color:#829991;margin-left:auto}
    #time details.premium-adjust[open]>summary:after{content:'−'}
    #time details.premium-adjust .controls{margin:0;padding:9px 12px 11px;border-top:1px solid #edf2ef;gap:8px}
    #time details.premium-adjust .field{gap:3px}
    #time details.premium-adjust .field label{font-size:.7rem}
    #time details.premium-adjust input,#time details.premium-adjust select{padding:8px 9px;min-height:38px;border-radius:10px}
    #time details.premium-adjust .btn{min-height:38px;padding:8px 12px}

    #time h2{margin:19px 0 8px;font-size:1.03rem}
    #time .pitch{min-height:330px;padding:7px 5px;border-radius:22px;background:radial-gradient(circle at 50% 50%,transparent 0 31px,rgba(255,255,255,.12) 32px 33px,transparent 34px),linear-gradient(to bottom,transparent calc(50% - .5px),rgba(255,255,255,.14) calc(50% - .5px),rgba(255,255,255,.14) calc(50% + .5px),transparent calc(50% + .5px)),linear-gradient(180deg,#489970 0%,#2f7857 100%);box-shadow:0 17px 36px rgba(31,102,71,.15);border:1px solid rgba(255,255,255,.2)}
    #time .pitch:before{inset:10px;border-color:rgba(255,255,255,.3);border-radius:11px}
    #time .pitch:after{display:none}
    #time .line{min-height:60px;position:relative;z-index:2}
    #time .player-ball{width:108px;padding:2px 3px;position:relative}
    #time .ball{width:42px;height:42px;border-width:2px;box-shadow:0 6px 14px rgba(0,0,0,.13);font-size:.6rem;letter-spacing:.02em}
    #time .captain .ball{outline:2px solid rgba(195,147,42,.95);outline-offset:2px;box-shadow:0 0 0 4px rgba(195,147,42,.11),0 6px 14px rgba(0,0,0,.13)}
    #time .captain-badge{position:absolute;left:calc(50% + 11px);top:-1px;z-index:3;width:18px;height:18px;border-radius:50%;display:flex;align-items:center;justify-content:center;background:#c3972f;color:#fff;font-size:.53rem;font-weight:900;border:2px solid rgba(255,255,255,.9);box-shadow:0 3px 8px rgba(0,0,0,.18)}
    #time .player-ball .name{font-size:.71rem;line-height:1.08;margin-top:4px;white-space:normal;overflow:hidden;text-overflow:clip;display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:2;height:1.56em;text-shadow:0 1px 2px rgba(0,0,0,.2);font-weight:780}
    #time .player-ball .pts{font-size:.67rem;font-weight:850}
    #time .player-ball .fixture{font-size:.53rem;margin-top:2px;color:rgba(255,255,255,.82);display:flex;align-items:center;justify-content:center;gap:3px;white-space:nowrap;overflow:visible}
    #time .venue-badge{display:inline-flex;align-items:center;gap:2px;font-size:.43rem;font-weight:900;letter-spacing:.02em;padding:1px 4px;border-radius:999px;background:rgba(255,255,255,.16);border:1px solid rgba(255,255,255,.18);color:#fff;text-transform:uppercase;line-height:1.3}
    #time .defense-line .player-ball:first-child,#time .defense-line .player-ball:last-child{transform:translateY(3px)}
    #time .defense-line .player-ball:nth-child(2),#time .defense-line .player-ball:nth-child(3){transform:translateY(-2px)}

    #time .bench{display:grid;grid-template-columns:1fr;gap:0;padding:0;background:#fff;border:1px solid var(--premium-line);border-radius:16px;overflow:hidden;box-shadow:0 9px 25px rgba(22,69,50,.045)}
    #time .bench .mini{border:0;border-radius:0;box-shadow:none;padding:8px 40px 8px 12px;position:relative;background:#fff;min-height:56px;transition:background .14s ease,transform .14s ease}
    #time .bench .mini:not(:last-child){border-bottom:1px solid var(--premium-line)}
    #time .bench .mini:after{content:'›';position:absolute;right:14px;top:50%;transform:translateY(-50%);font-size:1.4rem;font-weight:300;color:#9aaba4}
    #time .bench .mini:active{background:#f5f8f6;transform:scale(.998)}
    #time .bench .mini .pill{font-size:.61rem;padding:3px 7px;font-weight:780}
    #time .bench .mini b{font-size:.88rem;margin:3px 0 1px;font-weight:780}
    #time .bench .mini small{font-size:.71rem;line-height:1.28;font-weight:450}
    #time .bench .mini.luxury{background:linear-gradient(90deg,#fff9eb,#fff);box-shadow:inset 3px 0 0 #c9a04a}
    #time .bench .mini.luxury .pill{background:#fff1cc;color:#6f581d}
    #time .bench-venue{display:inline-flex;margin-left:5px;font-size:.58rem;font-weight:800;color:#6f827a}

    #time .alternatives{grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:12px}
    #time .alternatives .card{box-shadow:none;border:0;background:transparent;border-radius:0;padding:0 2px 2px}
    #time .altgroup h3{font-size:.85rem;color:#2a443a;margin:0 0 3px;font-weight:780}
    #time .altplayer{padding:9px 0;position:relative;border-top:1px solid #e5ece8}
    #time .altplayer b{font-size:.86rem;padding-right:5px;font-weight:780}
    #time .altplayer small{line-height:1.38;font-weight:430}
    #time .altplayer small .good,#time .altplayer small .warn,#time .altplayer small .bad{display:inline-flex;border-radius:999px;padding:2px 6px;font-size:.63rem;font-weight:780}
    #time .altplayer small .good{background:#e8f2ed;color:#1f7152}
    #time .altplayer small .warn{background:#f7f1df;color:#8a7028}
    #time .altplayer small .bad{background:#f3f1ed;color:#7c6b55}
    #time .altpts{font-size:.98rem;min-width:64px;text-align:right;font-weight:900}
    #time .altpts:before{content:''}
    #time .altpts:after{content:' pts';font-size:.6rem;font-weight:650;color:#93a09b}
    #time .altgroup .altplayer.premium-hidden{display:none}
    #time .alt-toggle{border:0;background:transparent;color:#176b4b;font-size:.69rem;font-weight:800;padding:7px 0 2px;cursor:pointer}
    #time .alt-venue{display:inline-flex;align-items:center;margin-left:4px;font-size:.6rem;font-weight:800;color:#70827b}

    @media(max-width:700px){
      header .top{padding:8px 12px 5px}
      header .brand{font-size:.98rem}
      header .sub{font-size:.64rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:245px}
      header .roundbadge{font-size:.64rem;padding:5px 8px}
      header .nav{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:4px;padding:6px 0 2px;overflow:visible;margin:0}
      header .nav button{min-height:33px;padding:5px 4px;font-size:.72rem;border-radius:9px;overflow:hidden;text-overflow:ellipsis}
      #time{padding-top:0}
      #time .premium-status{align-items:flex-start}
      #time .premium-titleblock{width:100%;justify-content:space-between}
      #time .premium-chips{width:100%}
      #time .premium-chip{font-size:.68rem;padding:4px 7px}
      #time #teamMetrics{grid-template-columns:1.45fr 1fr .7fr;border-radius:15px}
      #time #teamMetrics .card{padding:9px 8px}
      #time #teamMetrics .metric small{font-size:.54rem;letter-spacing:.02em}
      #time #teamMetrics .metric b{font-size:.84rem;white-space:nowrap}
      #time #teamMetrics .card:first-child .metric b{font-size:1.12rem}
      #time details.premium-adjust{margin:6px 0 10px}
      #time details.premium-adjust>summary{padding:7px 10px;min-height:36px;font-size:.72rem}
      #time details.premium-adjust .controls{padding:8px 10px 10px;gap:7px}
      #time details.premium-adjust input,#time details.premium-adjust select{padding:7px 8px;min-height:36px}
      #time details.premium-adjust .btn{min-height:36px;padding:7px 10px}
      #time .pitch{min-height:292px;padding:4px 2px;border-radius:19px}
      #time .pitch:before{inset:8px}
      #time .line{min-height:52px;gap:1px}
      #time .player-ball{width:67px;padding:1px}
      #time .ball{width:34px;height:34px;font-size:.49rem}
      #time .captain-badge{left:calc(50% + 8px);width:16px;height:16px;font-size:.46rem}
      #time .player-ball .name{font-size:.56rem;line-height:1.06;height:1.22em;-webkit-line-clamp:2}
      #time .player-ball .pts{font-size:.54rem}
      #time .player-ball .fixture{font-size:.44rem;letter-spacing:-.01em;gap:2px}
      #time .venue-badge{font-size:.36rem;padding:1px 3px}
      #time .bench .mini{padding:7px 36px 7px 10px;min-height:53px}
      #time .bench .mini b{font-size:.85rem}
      #time .alternatives{grid-template-columns:1fr;gap:10px}
    }
    @media(max-width:430px){
      header .sub{max-width:215px}
      header .nav button{font-size:.69rem}
      #time #teamMetrics .card{padding:8px 6px}
      #time #teamMetrics .metric b{font-size:.8rem}
      #time #teamMetrics .card:first-child .metric b{font-size:1.06rem}
      #time .pitch{min-height:282px}
      #time .line{min-height:50px}
      #time .player-ball{width:58px}
      #time .ball{width:33px;height:33px}
      #time .player-ball .name{font-size:.53rem}
      #time .player-ball .pts{font-size:.51rem}
      #time .player-ball .fixture{font-size:.41rem}
    }
  `;

  function injectStyle() {
    let style = document.getElementById('premium-time-style');
    if (!style) {
      style = document.createElement('style');
      style.id = 'premium-time-style';
      document.head.appendChild(style);
    }
    if (style.textContent !== CSS) style.textContent = CSS;
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
    const raw = (el.dataset.premiumRaw || el.textContent || '').trim();
    const m = raw.match(/^Rodada\s+(\d+)\s*·\s*formação\s+([^·]+)\s*·\s*capitão\s+([^·]+)\s*·\s*Reserva de Luxo\s+(.+?)\.?$/i);
    if (!m) return;
    const signature = `${m[1]}|${m[2].trim()}|${m[3].trim()}|${m[4].trim()}`;
    if (el.dataset.premiumSignature === signature) return;
    el.dataset.premiumRaw = raw;
    el.dataset.premiumSignature = signature;
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
      line.classList.add('defense-line');
      const desired = [lats[0], zags[0], zags[1], lats[1]];
      if (!nodes.every((n, i) => n === desired[i])) desired.forEach(n => line.appendChild(n));
    });
  }

  function parseFixture(raw) {
    const cleaned = String(raw || '')
      .replace(/(?:🏠|✈️)?\s*(?:CASA|FORA)\s*$/i, '')
      .replace(/\s*·\s*$/,'')
      .trim();
    if (!cleaned) return null;
    if (cleaned.includes(' x ')) return { fixture: cleaned, venue: 'CASA', emoji: '🏠' };
    if (cleaned.includes(' @ ')) return { fixture: cleaned, venue: 'FORA', emoji: '✈️' };
    return null;
  }

  function enhancePitchFixtures(section) {
    section.querySelectorAll('.player-ball .fixture').forEach(el => {
      let base = el.dataset.fixtureBase || '';
      if (!base) {
        const first = el.querySelector(':scope > span:not(.venue-badge)');
        base = (first ? first.textContent : el.textContent || '').trim();
      }
      const info = parseFixture(base);
      if (!info) return;
      const signature = `${info.fixture}|${info.venue}`;
      if (el.dataset.fixtureSignature === signature && el.querySelector('.venue-badge')) return;
      el.dataset.fixtureBase = info.fixture;
      el.dataset.fixtureSignature = signature;
      el.textContent = '';
      const fixture = document.createElement('span');
      fixture.textContent = info.fixture;
      const venue = document.createElement('span');
      venue.className = 'venue-badge';
      venue.textContent = `${info.emoji} ${info.venue}`;
      venue.setAttribute('aria-label', info.venue === 'CASA' ? 'Joga em casa' : 'Joga fora de casa');
      el.append(fixture, venue);
    });
  }

  function enhanceBench(section) {
    section.querySelectorAll('.bench .mini').forEach(card => {
      card.querySelectorAll('small').forEach(el => {
        const cleaned = (el.textContent || '').replace(/\s*·?\s*toque para detalhes\s*/gi, '').trim();
        if (cleaned !== el.textContent.trim()) el.textContent = cleaned;
      });
      if (card.querySelector('.bench-venue')) return;
      const fixtureEl = card.querySelector('.fixture-tag');
      if (!fixtureEl) return;
      const info = parseFixture(fixtureEl.textContent);
      if (!info) return;
      const badge = document.createElement('span');
      badge.className = 'bench-venue';
      badge.textContent = `${info.emoji} ${info.venue === 'CASA' ? 'Casa' : 'Fora'}`;
      fixtureEl.insertAdjacentElement('afterend', badge);
    });
  }

  function shortenAlternativesIntro(section) {
    const heading = Array.from(section.querySelectorAll('h2')).find(h => (h.textContent || '').trim() === 'Outras boas opções');
    if (!heading) return;
    let node = heading.nextElementSibling;
    if (!node || node.id === 'alternatives') return;
    const text = (node.textContent || '').trim();
    if (/alternativas por posição/i.test(text)) node.textContent = 'Alternativas por posição. Toque para entender a projeção.';
  }

  function enhanceAlternatives(section) {
    section.querySelectorAll('#alternatives .altgroup').forEach(group => {
      const players = Array.from(group.querySelectorAll('.altplayer'));
      players.forEach(player => {
        if (!player.querySelector('.alt-venue')) {
          const small = player.querySelector('small');
          if (small) {
            const source = small.textContent || '';
            const match = source.match(/([A-Z]{2,4}\s+(?:x|@)\s+[A-Z]{2,4})/);
            if (match) {
              const info = parseFixture(match[1]);
              if (info) {
                const venue = document.createElement('span');
                venue.className = 'alt-venue';
                venue.textContent = `${info.emoji} ${info.venue === 'CASA' ? 'Casa' : 'Fora'}`;
                small.appendChild(venue);
              }
            }
          }
        }
      });
      if (players.length <= 2) return;
      if (!group.dataset.altExpanded) group.dataset.altExpanded = '0';
      const expanded = group.dataset.altExpanded === '1';
      players.forEach((player, index) => player.classList.toggle('premium-hidden', !expanded && index >= 2));
      let toggle = group.querySelector('.alt-toggle');
      if (!toggle) {
        toggle = document.createElement('button');
        toggle.type = 'button';
        toggle.className = 'alt-toggle';
        toggle.addEventListener('click', event => {
          event.stopPropagation();
          group.dataset.altExpanded = group.dataset.altExpanded === '1' ? '0' : '1';
          enhanceAlternatives(section);
        });
        group.appendChild(toggle);
      }
      toggle.textContent = expanded ? 'Mostrar menos' : `+ ${players.length - 2} opção${players.length - 2 > 1 ? 'ões' : ''}`;
    });
  }

  function compactMobileNav() {
    const nav = document.getElementById('nav');
    if (!nav) return;
    const labels = {
      time: 'Time',
      monte: 'Montar',
      projecoes: 'Projeções',
      analise: 'Análise',
      historico: 'Histórico',
      metodologia: 'Método'
    };
    nav.querySelectorAll('button[data-page]').forEach(button => {
      if (!button.dataset.fullLabel) button.dataset.fullLabel = button.textContent.trim();
      button.setAttribute('aria-label', button.dataset.fullLabel);
      const short = labels[button.dataset.page];
      if (window.matchMedia('(max-width:700px)').matches && short) button.textContent = short;
      else button.textContent = button.dataset.fullLabel;
    });
  }

  function runEnhancements() {
    const section = document.getElementById('time');
    compactMobileNav();
    if (!section) return;
    compactControls(section);
    enhanceStatus(section);
    refineCaptain(section);
    reorderDefense(section);
    enhancePitchFixtures(section);
    enhanceBench(section);
    shortenAlternativesIntro(section);
    enhanceAlternatives(section);
  }

  function boot() {
    injectStyle();
    runEnhancements();
    const section = document.getElementById('time');
    if (section && section.dataset.premiumObserved !== '1') {
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
    window.addEventListener('resize', compactMobileNav, { passive: true });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once: true });
  else boot();
})(typeof window !== 'undefined' ? window : globalThis);
