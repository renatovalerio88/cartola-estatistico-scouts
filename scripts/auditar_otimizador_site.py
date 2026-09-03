#!/usr/bin/env python3
"""Audita o otimizador frontend do Site V3 contra uma solução MILP exata.

O objetivo é impedir que a expressão "maior força projetada" dependa apenas do
beam search do navegador. A auditoria replica a heurística atual e compara sua
pontuação com o ótimo matemático para orçamentos representativos.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import lil_matrix

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "site" / "dados.json"

FORMACOES = {
    "3-4-3": {"GOL": 1, "ZAG": 3, "LAT": 0, "MEI": 4, "ATA": 3},
    "3-5-2": {"GOL": 1, "ZAG": 3, "LAT": 0, "MEI": 5, "ATA": 2},
    "4-3-3": {"GOL": 1, "ZAG": 2, "LAT": 2, "MEI": 3, "ATA": 3},
    "4-4-2": {"GOL": 1, "ZAG": 2, "LAT": 2, "MEI": 4, "ATA": 2},
    "5-3-2": {"GOL": 1, "ZAG": 3, "LAT": 2, "MEI": 3, "ATA": 2},
}
ORCAMENTOS = (100.0, 120.0, 150.0, 200.0)
CLUBE_MAX = 3
BEAM = 700
TOP_POS = 24
TOL = 1e-6


def carregar():
    payload = json.loads(DATA.read_text(encoding="utf-8"))
    jogadores = payload.get("produto", {}).get("jogadores", [])
    return [j for j in jogadores if int(j.get("status_id") or 0) == 7]


def candidatos(jogadores, pos):
    return sorted(
        (j for j in jogadores if j.get("posicao") == pos),
        key=lambda j: float(j.get("projecao") or 0),
        reverse=True,
    )[:TOP_POS]


def beam_formacao(jogadores, formacao, budget):
    slots = []
    for pos, n in FORMACOES[formacao].items():
        slots.extend([pos] * n)
    if any(j.get("posicao") == "TEC" for j in jogadores):
        slots.append("TEC")

    states = [{"ids": frozenset(), "score": 0.0, "cost": 0.0, "clubs": Counter()}]
    for pos in slots:
        pool = candidatos(jogadores, pos)
        nxt = []
        for s in states:
            for p in pool:
                aid = int(p["atleta_id"])
                clube = str(p.get("sigla_clube") or "")
                if aid in s["ids"] or s["clubs"][clube] >= CLUBE_MAX:
                    continue
                cost = s["cost"] + float(p.get("preco") or 0)
                if cost > budget + TOL:
                    continue
                clubs = s["clubs"].copy()
                clubs[clube] += 1
                nxt.append({
                    "ids": s["ids"] | {aid},
                    "score": s["score"] + float(p.get("projecao") or 0),
                    "cost": cost,
                    "clubs": clubs,
                })
        nxt.sort(key=lambda x: x["score"], reverse=True)
        states = nxt[:BEAM]
        if not states:
            return None
    return states[0]


def exato_formacao(jogadores, formacao, budget):
    req = dict(FORMACOES[formacao])
    if any(j.get("posicao") == "TEC" for j in jogadores):
        req["TEC"] = 1

    # Remove posições sem vaga para reduzir o MILP.
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


def melhor(jogadores, budget, solver):
    best = None
    for formacao in FORMACOES:
        sol = solver(jogadores, formacao, budget)
        if sol is not None and (best is None or sol["score"] > best["score"] + TOL):
            best = {**sol, "formacao": formacao}
    return best


def main():
    jogadores = carregar()
    assert jogadores, "nenhum jogador elegível no payload do site"
    falhas = []
    print(f"Auditando {len(jogadores)} jogadores elegíveis | orçamento={ORCAMENTOS}")
    for budget in ORCAMENTOS:
        heur = melhor(jogadores, budget, beam_formacao)
        exact = melhor(jogadores, budget, exato_formacao)
        if heur is None or exact is None:
            falhas.append((budget, "sem solução", heur, exact))
            continue
        gap = exact["score"] - heur["score"]
        print(
            f"C$ {budget:.0f}: beam={heur['score']:.6f} ({heur['formacao']}) | "
            f"exato={exact['score']:.6f} ({exact['formacao']}) | gap={gap:.6f}"
        )
        if gap > TOL:
            falhas.append((budget, gap, heur, exact))

    if falhas:
        linhas = ["Otimizador frontend não atingiu o ótimo global:"]
        for budget, gap, heur, exact in falhas:
            linhas.append(
                f"- C$ {budget:.0f}: gap={gap}; beam={None if heur is None else heur['score']:.6f}; "
                f"exato={None if exact is None else exact['score']:.6f}"
                if heur is not None and exact is not None
                else f"- C$ {budget:.0f}: solução ausente"
            )
        raise AssertionError("\n".join(linhas))

    print("OK: beam atual coincidiu com o ótimo MILP em todos os orçamentos auditados.")


if __name__ == "__main__":
    main()
