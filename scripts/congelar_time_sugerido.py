#!/usr/bin/env python3
"""Congela a escalação oficial do produto antes da rodada.

O arquivo criado é append-only: se já existir, nunca é regravado. A seleção usa o
mesmo objetivo do produto (maior soma de projeções), orçamento padrão de C$ 200,
limite de três atletas por clube e somente atletas com status provável (7).
"""
from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import lil_matrix

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "predictions" / "pre_round" / "2026"
RAW = ROOT / "data" / "raw"
BUDGET = 200.0
MAX_CLUBE = 3
FORMACOES = {
    "3-4-3": {"GOL": 1, "ZAG": 3, "LAT": 0, "MEI": 4, "ATA": 3},
    "3-5-2": {"GOL": 1, "ZAG": 3, "LAT": 0, "MEI": 5, "ATA": 2},
    "4-3-3": {"GOL": 1, "ZAG": 2, "LAT": 2, "MEI": 3, "ATA": 3},
    "4-4-2": {"GOL": 1, "ZAG": 2, "LAT": 2, "MEI": 4, "ATA": 2},
    "5-3-2": {"GOL": 1, "ZAG": 3, "LAT": 2, "MEI": 3, "ATA": 2},
}
BENCH_POS = ["GOL", "LAT", "ZAG", "MEI", "ATA"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def latest_snapshot() -> tuple[int, Path] | tuple[None, None]:
    files = sorted([p for p in ARCHIVE.glob("R??.csv") if ".catboost." not in p.name], reverse=True)
    if not files:
        return None, None
    p = files[0]
    return int(p.stem[1:]), p


def load_players(rodada: int, csv_path: Path) -> list[dict]:
    market_path = RAW / f"rodada-{rodada:02d}" / "jogadores.json"
    market = json.loads(market_path.read_text(encoding="utf-8")) if market_path.exists() else []
    by_id = {int(j.get("id")): j for j in market if j.get("id") is not None}
    players = []
    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            aid = int(row["atleta_id"])
            m = by_id.get(aid, {})
            players.append({
                "atleta_id": aid,
                "apelido": row.get("apelido") or m.get("apelido") or str(aid),
                "posicao": str(row.get("posicao") or m.get("posicao") or "").upper(),
                "sigla_clube": row.get("sigla_clube") or m.get("siglaClube") or "",
                "status_id": int(float(row.get("status_id") or m.get("statusId") or 0)),
                "preco": float(m.get("preco") or 0),
                "projecao": float(row.get("v3h_hibrido") or 0),
                "titularidade": float(row.get("titularidade_pre_rodada") or 0),
            })
    return players


def solve_formation(players: list[dict], formation: str) -> dict | None:
    req = dict(FORMACOES[formation])
    if any(p["posicao"] == "TEC" for p in players):
        req["TEC"] = 1
    eligible = [p for p in players if p["status_id"] == 7 and req.get(p["posicao"], 0) > 0]
    if not eligible:
        return None
    n = len(eligible)
    clubs = sorted({p["sigla_clube"] for p in eligible})
    positions = [p for p, q in req.items() if q > 0]
    rows = len(positions) + 1 + len(clubs)
    A = lil_matrix((rows, n), dtype=float)
    lb = np.full(rows, -np.inf)
    ub = np.full(rows, np.inf)
    r = 0
    for pos in positions:
        for i, p in enumerate(eligible):
            if p["posicao"] == pos:
                A[r, i] = 1.0
        lb[r] = ub[r] = float(req[pos])
        r += 1
    for i, p in enumerate(eligible):
        A[r, i] = p["preco"]
    ub[r] = BUDGET
    r += 1
    for club in clubs:
        for i, p in enumerate(eligible):
            if p["sigla_clube"] == club:
                A[r, i] = 1.0
        ub[r] = MAX_CLUBE
        r += 1
    c = -np.array([p["projecao"] for p in eligible], dtype=float)
    res = milp(
        c=c,
        integrality=np.ones(n, dtype=int),
        bounds=Bounds(np.zeros(n), np.ones(n)),
        constraints=LinearConstraint(A.tocsr(), lb, ub),
        options={"time_limit": 30.0},
    )
    if not res.success or res.x is None:
        return None
    chosen = [p for p, x in zip(eligible, res.x) if x > 0.5]
    return {
        "formacao": formation,
        "titulares": chosen,
        "projecao_base": sum(p["projecao"] for p in chosen),
        "custo": sum(p["preco"] for p in chosen),
    }


def select_bench(players: list[dict], starters: list[dict]) -> list[dict]:
    used = {p["atleta_id"] for p in starters}
    bench = []
    for pos in BENCH_POS:
        same = [p for p in starters if p["posicao"] == pos]
        if not same:
            continue
        cap = min(p["preco"] for p in same)
        candidates = [
            p for p in players
            if p["status_id"] == 7 and p["posicao"] == pos and p["atleta_id"] not in used and p["preco"] <= cap + 1e-9
        ]
        if not candidates:
            continue
        candidates.sort(key=lambda p: (-p["projecao"], p["preco"], p["atleta_id"]))
        chosen = dict(candidates[0])
        chosen["teto_preco_reserva"] = cap
        chosen["reserva_luxo"] = False
        bench.append(chosen)
        used.add(chosen["atleta_id"])
    if bench:
        def gain(reserve):
            weakest = min((p for p in starters if p["posicao"] == reserve["posicao"]), key=lambda p: (p["projecao"], p["atleta_id"]))
            return reserve["projecao"] - weakest["projecao"]
        luxury = sorted(bench, key=lambda p: (-gain(p), -p["projecao"], p["atleta_id"]))[0]
        for p in bench:
            p["reserva_luxo"] = p["atleta_id"] == luxury["atleta_id"]
    return bench


def main() -> int:
    rodada, csv_path = latest_snapshot()
    if rodada is None:
        print("Nenhum snapshot pré-rodada encontrado.")
        return 0
    out = ARCHIVE / f"R{rodada}.time-sugerido.json"
    if out.exists():
        print(f"Time sugerido R{rodada} já congelado; arquivo preservado.")
        return 0
    players = load_players(rodada, csv_path)
    solutions = [solve_formation(players, f) for f in FORMACOES]
    solutions = [s for s in solutions if s]
    if not solutions:
        raise RuntimeError(f"Não foi possível montar time sugerido para R{rodada}.")
    best = sorted(solutions, key=lambda s: (-s["projecao_base"], s["custo"], s["formacao"]))[0]
    starters = best["titulares"]
    captain = sorted(
        [p for p in starters if p["posicao"] != "TEC"],
        key=lambda p: (-p["projecao"], -p["titularidade"], p["preco"], p["atleta_id"]),
    )[0]
    bench = select_bench(players, starters)
    projection_with_captain = best["projecao_base"] + captain["projecao"]
    payload = {
        "temporada": 2026,
        "rodada": rodada,
        "gerado_em_utc": datetime.now(timezone.utc).isoformat(),
        "regra": "escalação oficial do produto congelada antes da rodada; orçamento C$ 200; máximo 3 por clube; somente status provável",
        "orcamento": BUDGET,
        "max_por_clube": MAX_CLUBE,
        "formacao": best["formacao"],
        "custo": round(best["custo"], 4),
        "projecao_titulares_sem_bonus_capitao": round(best["projecao_base"], 6),
        "projecao_time_com_capitao": round(projection_with_captain, 6),
        "capitao_atleta_id": captain["atleta_id"],
        "titulares": starters,
        "banco": bench,
        "fontes": {
            "snapshot_csv": str(csv_path.relative_to(ROOT)),
            "snapshot_csv_sha256": sha256(csv_path),
            "mercado_pre_rodada": f"data/raw/rodada-{rodada:02d}/jogadores.json",
        },
        "imutavel": True,
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Time sugerido R{rodada} congelado | {best['formacao']} | projeção com capitão={projection_with_captain:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
