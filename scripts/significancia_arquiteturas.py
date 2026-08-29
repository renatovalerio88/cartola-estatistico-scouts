#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
IN = ROOT / "data" / "reports" / "backtest-v3s-nested.json"
OUT = ROOT / "data" / "reports" / "significancia-arquiteturas.json"
SEED = 42
BOOT = 5000


def carregar_previsoes(payload: dict) -> pd.DataFrame:
    rows = payload.get("previsoes") or []
    df = pd.DataFrame(rows)
    required = {"rodada", "real", "v3s_nested", "direta_rf_lab", "v3h_hibrido", "direta_ewma"}
    missing = required - set(df.columns)
    if missing:
        raise SystemExit(f"Colunas ausentes no backtest: {sorted(missing)}")
    return df


def mae_por_rodada(df: pd.DataFrame, col: str) -> pd.Series:
    return df.groupby("rodada").apply(
        lambda g: float(np.mean(np.abs(g[col].to_numpy(float) - g["real"].to_numpy(float)))),
        include_groups=False,
    )


def block_bootstrap_rounds(a: pd.Series, b: pd.Series) -> dict:
    comum = sorted(set(a.index) & set(b.index))
    if len(comum) < 3:
        return {"n_rodadas": len(comum), "erro": "rodadas insuficientes"}
    diffs = np.array([a.loc[r] - b.loc[r] for r in comum], dtype=float)
    rng = np.random.default_rng(SEED)
    samples = rng.choice(diffs, size=(BOOT, len(diffs)), replace=True).mean(axis=1)
    lo, hi = np.quantile(samples, [0.025, 0.975])
    mean = float(diffs.mean())
    wins = int(np.sum(diffs < 0))
    losses = int(np.sum(diffs > 0))
    ties = int(np.sum(np.isclose(diffs, 0.0, atol=1e-12)))
    return {
        "n_rodadas": len(comum),
        "diferenca_mae_a_menos_b": round(mean, 6),
        "ic95_block_bootstrap": [round(float(lo), 6), round(float(hi), 6)],
        "a_melhor_rodadas": wins,
        "b_melhor_rodadas": losses,
        "empates": ties,
        "probabilidade_bootstrap_a_melhor": round(float(np.mean(samples < 0)), 6),
        "interpretacao": (
            "evidencia_forte_a_melhor" if hi < 0 else
            "evidencia_forte_b_melhor" if lo > 0 else
            "inconclusivo"
        ),
    }


def main():
    if not IN.exists() or IN.stat().st_size == 0:
        raise SystemExit("backtest-v3s-nested.json ausente ou vazio")
    payload = json.loads(IN.read_text(encoding="utf-8"))
    df = carregar_previsoes(payload)
    models = ["v3s_nested", "direta_rf_lab", "v3h_hibrido", "direta_ewma"]
    round_mae = {m: mae_por_rodada(df, m) for m in models}

    comparisons = {}
    pairs = [
        ("v3s_nested", "direta_ewma"),
        ("v3s_nested", "direta_rf_lab"),
        ("v3h_hibrido", "direta_rf_lab"),
        ("v3h_hibrido", "v3s_nested"),
    ]
    for a, b in pairs:
        comparisons[f"{a}_vs_{b}"] = block_bootstrap_rounds(round_mae[a], round_mae[b])

    global_mae = {
        m: round(float(np.mean(np.abs(df[m].to_numpy(float) - df["real"].to_numpy(float)))), 6)
        for m in models
    }
    compact = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "protocolo": (
            "comparação pareada por rodada; bootstrap em blocos de rodada para preservar dependência "
            "intra-rodada; usa somente previsões OOS já produzidas pelo backtest nested anti-leakage"
        ),
        "bootstrap_amostras": BOOT,
        "seed": SEED,
        "linhas": int(len(df)),
        "rodadas": sorted(int(r) for r in df.rodada.unique()),
        "mae_global": global_mae,
        "comparacoes": comparisons,
    }
    OUT.write_text(json.dumps(compact, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(compact, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
