#!/usr/bin/env python3
"""Audita o otimizador JS real do Site V3 contra uma solução MILP exata.

O teste executa o mesmo módulo carregado pelo navegador (site/optimizer.js) e
compara seu resultado com scipy.optimize.milp em vários orçamentos e cenários
de exclusão. Qualquer diferença positiva bloqueia a publicação do produto.
"""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import lil_matrix

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "site" / "dados.json"
INDEX = ROOT / "site" / "index.html"
OPTIMIZER = ROOT / "site" / "optimizer.js"

FORMACOES = {
    "3-4-3": {"GOL": 1, "ZAG": 3, "LAT": 0, "MEI": 4, "ATA": 3},
    "3-5-2": {"GOL": 1, "ZAG": 3, "LAT": 0, "MEI": 5, "ATA": 2},
    "4-3-3": {"GOL": 1, "ZAG": 2, "LAT": 2, "MEI": 3, "ATA": 3},
    "4-4-2": {"GOL": 1, "ZAG": 2, "LAT": 2, "MEI": 4, "ATA": 2},
    "5-3-2": {"GOL": 1, "ZAG": 3, "LAT": 2, "MEI": 3, "ATA": 2},
}
CLUBE_MAX = 3
TOL = 1e-6


def carregar():
    payload = json.loads(DATA.read_text(encoding="utf-8"))
    jogadores = payload.get("produto", {}).get("jogadores", [])
    return [j for j in jogadores if int(j.get("status_id") or 0) == 7]


def filtrar(jogadores, excluir_atleta=None, excluir_clube=None):
    out = []
    for j in jogadores:
        if excluir_atleta is not None and int(j.get("atleta_id") or 0) == int(excluir_atleta):
            continue
        if excluir_clube is not None and str(j.get("sigla_clube") or "") == str(excluir_clube):
            continue
        out.append(j)
    return out


def exato_formacao(jogadores, formacao, budget):
    req = dict(FORMACOES[formacao])
    if any(j.get("posicao") == "TEC" for j in jogadores):
        req["TEC"] = 1

    js = [j for j in jogadores if req.get(j.get("posicao"), 0) > 0]
    if not js:
        return None

    n = len(js)
    clubes = sorted({str(j.get("sigla_clube") or "") for j in js})
    posicoes = [p for p, q in req.items() if q > 0]
    linhas = len(posicoes) + 1 + len(clubes)
    A = lil_matrix((linhas, n), dtype=float)
    lb = np.full(linhas, -np.inf)
    ub = np.full(linhas, np.inf)

    row = 0
    for pos in posicoes:
        for i, j in enumerate(js):
            if j.get("posicao") == pos:
                A[row, i] = 1.0
        lb[row] = ub[row] = float(req[pos])
        row += 1

    for i, j in enumerate(js):
        A[row, i] = float(j.get("preco") or 0)
    ub[row] = float(budget)
    row += 1

    for clube in clubes:
        for i, j in enumerate(js):
            if str(j.get("sigla_clube") or "") == clube:
                A[row, i] = 1.0
        ub[row] = CLUBE_MAX
        row += 1

    c = -np.array([float(j.get("projecao") or 0) for j in js], dtype=float)
    res = milp(
        c=c,
        integrality=np.ones(n, dtype=int),
        bounds=Bounds(np.zeros(n), np.ones(n)),
        constraints=LinearConstraint(A.tocsr(), lb, ub),
        options={"time_limit": 30.0},
    )
    if not res.success or res.x is None:
        return None
    chosen = [j for j, x in zip(js, res.x) if x > 0.5]
    return {
        "score": sum(float(j.get("projecao") or 0) for j in chosen),
        "cost": sum(float(j.get("preco") or 0) for j in chosen),
        "ids": {int(j["atleta_id"]) for j in chosen},
    }


def melhor_exato(jogadores, budget):
    best = None
    for formacao in FORMACOES:
        sol = exato_formacao(jogadores, formacao, budget)
        if sol is not None and (best is None or sol["score"] > best["score"] + TOL):
            best = {**sol, "formacao": formacao}
    return best


def rodar_js(jogadores, budget):
    with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=False) as f:
        json.dump(jogadores, f, ensure_ascii=False)
        temp_path = Path(f.name)
    try:
        js = r"""
const fs=require('fs');
const opt=require(process.argv[1]);
const players=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const budget=Number(process.argv[3]);
const F=JSON.parse(process.argv[4]);
const result=opt.optimize(players,budget,'auto',{formations:F,eligible:()=>true,maxClub:3});
process.stdout.write(JSON.stringify(result?{score:result.score,cost:result.cost,formation:result.formation,ids:result.sel.map(x=>x.atleta_id)}:null));
"""
        proc = subprocess.run(
            [
                "node", "-e", js,
                str(OPTIMIZER), str(temp_path), str(budget), json.dumps(FORMACOES),
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
        return json.loads(proc.stdout)
    finally:
        temp_path.unlink(missing_ok=True)


def main():
    assert OPTIMIZER.exists(), "site/optimizer.js ausente"
    html = INDEX.read_text(encoding="utf-8")
    assert 'src="optimizer.js"' in html, "index.html não carrega optimizer.js"
    assert "V3ExactOptimizer.optimize" in html, "frontend não delega para o otimizador exato"

    jogadores = carregar()
    assert jogadores, "nenhum jogador elegível no payload do site"
    top = max(jogadores, key=lambda j: float(j.get("projecao") or 0))

    cenarios = [
        (90.0, None, None, "base-90"),
        (100.0, None, None, "base-100"),
        (110.0, None, None, "base-110"),
        (120.0, None, None, "base-120"),
        (150.0, None, None, "base-150"),
        (200.0, None, None, "base-200"),
        (120.0, int(top["atleta_id"]), None, "sem-top-player"),
        (120.0, None, str(top.get("sigla_clube") or ""), "sem-clube-top"),
    ]

    falhas = []
    print(f"Auditando módulo JS exato | {len(jogadores)} jogadores elegíveis | {len(cenarios)} cenários")
    for budget, excluir_atleta, excluir_clube, nome in cenarios:
        pool = filtrar(jogadores, excluir_atleta, excluir_clube)
        js_sol = rodar_js(pool, budget)
        exact = melhor_exato(pool, budget)
        if js_sol is None or exact is None:
            if js_sol is None and exact is None:
                print(f"{nome}: ambos sem solução")
                continue
            falhas.append((nome, "solução divergente", js_sol, exact))
            continue
        gap = float(exact["score"]) - float(js_sol["score"])
        print(
            f"{nome}: js={js_sol['score']:.6f} ({js_sol['formation']}) | "
            f"milp={exact['score']:.6f} ({exact['formacao']}) | gap={gap:.9f}"
        )
        if abs(gap) > TOL:
            falhas.append((nome, gap, js_sol, exact))

    if falhas:
        linhas = ["Otimizador JS divergiu do ótimo MILP:"]
        for nome, gap, js_sol, exact in falhas:
            linhas.append(f"- {nome}: gap={gap}; js={js_sol}; milp={exact}")
        raise AssertionError("\n".join(linhas))

    print("OK: o módulo JS do navegador coincidiu com o ótimo MILP em todos os cenários auditados.")


if __name__ == "__main__":
    main()
