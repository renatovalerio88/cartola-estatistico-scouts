#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
BACKTEST = ROOT / "data" / "reports" / "backtest-v3s-nested.json"
OUT = ROOT / "data" / "reports" / "meta-seletor-v2-v3.json"
V2_RAW = "https://raw.githubusercontent.com/renatovalerio88/cartola-estatistico/main/data/historico/rodada-{rodada:02d}.json"
MIN_PRIOR_ROUNDS = 3
BOOTSTRAPS = 5000
SEED = 42


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def mae(y, p):
    return float(np.mean(np.abs(np.asarray(p, float) - np.asarray(y, float))))


def fetch_v2_round(rodada: int):
    response = requests.get(V2_RAW.format(rodada=rodada), timeout=30)
    if response.status_code == 404:
        return []
    response.raise_for_status()
    payload = response.json()
    rows = []
    for j in payload.get("jogadores") or []:
        if not isinstance(j, dict):
            continue
        try:
            rows.append({
                "rodada": rodada,
                "atleta_id": int(j["id"]),
                "v2": float(j["projecao"]),
                "v2_real": float(j["real"]),
            })
        except (KeyError, TypeError, ValueError):
            continue
    return rows


def choose_for_position(history: pd.DataFrame, pos: str):
    prior = history[history.posicao.eq(pos)].copy()
    rounds = sorted(prior.rodada.unique())
    if len(rounds) < MIN_PRIOR_ROUNDS:
        return "v2", {"motivo": "historico_insuficiente", "rodadas": len(rounds)}
    recent = rounds[-5:]
    prior = prior[prior.rodada.isin(recent)]
    scores = {
        "v2": mae(prior.real, prior.v2),
        "v3h": mae(prior.real, prior.v3h_hibrido),
    }
    winner = min(scores, key=lambda k: (scores[k], 0 if k == "v2" else 1))
    return winner, {"rodadas": [int(r) for r in recent], "mae": {k: round(v, 6) for k, v in scores.items()}}


def bootstrap_rounds(df: pd.DataFrame, challenger: str, baseline: str):
    diffs = []
    for _, g in df.groupby("rodada"):
        diffs.append(mae(g.real, g[challenger]) - mae(g.real, g[baseline]))
    values = np.asarray(diffs, float)
    rng = np.random.default_rng(SEED)
    boots = np.asarray([
        float(np.mean(rng.choice(values, size=len(values), replace=True)))
        for _ in range(BOOTSTRAPS)
    ])
    lo, hi = np.quantile(boots, [0.025, 0.975])
    return {
        "diferenca_mae": round(float(np.mean(values)), 6),
        "ic95": [round(float(lo), 6), round(float(hi), 6)],
        "probabilidade_melhor": round(float(np.mean(boots < 0)), 4),
        "rodadas_ganhas": int(np.sum(values < 0)),
        "rodadas_perdidas": int(np.sum(values > 0)),
    }


def main():
    bt = load(BACKTEST)
    v3 = pd.DataFrame(bt.get("previsoes", []))
    if v3.empty:
        raise SystemExit("Backtest V3 vazio")
    required = {"rodada", "atleta_id", "posicao", "real", "v3h_hibrido"}
    missing = required - set(v3.columns)
    if missing:
        raise SystemExit(f"Colunas ausentes: {sorted(missing)}")

    v2_rows = []
    for rodada in sorted(v3.rodada.astype(int).unique()):
        v2_rows.extend(fetch_v2_round(int(rodada)))
    v2 = pd.DataFrame(v2_rows)
    merged = v3.merge(v2, on=["rodada", "atleta_id"], how="inner")
    merged = merged[np.abs(merged.real - merged.v2_real) <= 1e-6].copy()
    merged = merged.sort_values(["rodada", "atleta_id"]).reset_index(drop=True)
    if merged.empty:
        raise SystemExit("Sem linhas comuns consistentes")

    out = []
    selection_log = []
    for rodada in sorted(merged.rodada.astype(int).unique()):
        current = merged[merged.rodada.eq(rodada)].copy()
        history = merged[merged.rodada.lt(rodada)].copy()
        for pos, g in current.groupby("posicao"):
            winner, detail = choose_for_position(history, str(pos))
            pred = g.v2.to_numpy(float) if winner == "v2" else g.v3h_hibrido.to_numpy(float)
            for (_, row), p in zip(g.iterrows(), pred):
                out.append({
                    "rodada": int(rodada),
                    "atleta_id": int(row.atleta_id),
                    "posicao": str(pos),
                    "real": float(row.real),
                    "v2": float(row.v2),
                    "v3h": float(row.v3h_hibrido),
                    "meta": float(p),
                    "arquitetura_escolhida": winner,
                })
            selection_log.append({"rodada": int(rodada), "posicao": str(pos), "escolha": winner, **detail})

    pred = pd.DataFrame(out)
    metrics = {
        "v2": {"mae": round(mae(pred.real, pred.v2), 6), "n": int(len(pred))},
        "v3h": {"mae": round(mae(pred.real, pred.v3h), 6), "n": int(len(pred))},
        "meta": {"mae": round(mae(pred.real, pred.meta), 6), "n": int(len(pred))},
    }
    by_pos = {}
    for pos, g in pred.groupby("posicao"):
        by_pos[str(pos)] = {k: round(mae(g.real, g[col]), 6) for k, col in {"v2":"v2","v3h":"v3h","meta":"meta"}.items()}

    payload = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "protocolo": (
            "meta-seletor walk-forward por posição: para cada rodada R e posição, escolhe V2 ou V3-H "
            "usando apenas MAE observado nas até 5 rodadas anteriores; mínimo de 3 rodadas anteriores; "
            "em insuficiência mantém V2. Nunca usa resultado da própria R para escolher."
        ),
        "linhas": int(len(pred)),
        "rodadas": sorted(pred.rodada.unique().astype(int).tolist()),
        "geral": metrics,
        "por_posicao": by_pos,
        "bootstrap_meta_vs_v2": bootstrap_rounds(pred, "meta", "v2"),
        "bootstrap_meta_vs_v3h": bootstrap_rounds(pred, "meta", "v3h"),
        "escolhas": selection_log,
        "contagem_escolhas": pred.arquitetura_escolhida.value_counts().to_dict(),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Meta-seletor V2/V3 por posição:", metrics)
    print("Escolhas:", payload["contagem_escolhas"])
    print("Bootstrap meta vs V2:", payload["bootstrap_meta_vs_v2"])


if __name__ == "__main__":
    main()
