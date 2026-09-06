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
