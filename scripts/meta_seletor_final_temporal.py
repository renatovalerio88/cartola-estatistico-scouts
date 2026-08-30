#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "reports" / "seletor-nested-calibracao-catboost.json"
OUT = ROOT / "data" / "reports" / "meta-seletor-final-temporal.json"
V2_RAW = "https://raw.githubusercontent.com/renatovalerio88/cartola-estatistico/main/data/historico/rodada-{rodada:02d}.json"

CANDIDATES = ["v2", "v3h", "cat_nested"]
MIN_PRIOR_ROUNDS = 3
WINDOW_SELECTION = 5
BOOTSTRAPS = 5000
SEED = 42
BIAS_LIMIT = 0.60
RMSE_TOL_V2 = 1.05


def metrics(y, p):
    y = np.asarray(y, float)
    p = np.asarray(p, float)
    e = p - y
    return {
        "n": int(len(y)),
        "mae": float(np.mean(np.abs(e))),
        "rmse": float(np.sqrt(np.mean(e ** 2))),
        "bias": float(np.mean(e)),
    }


def round6(d):
    return {k: (round(v, 6) if isinstance(v, float) else v) for k, v in d.items()}


def fetch_v2(rounds):
    rows = []
    for rodada in rounds:
        r = requests.get(V2_RAW.format(rodada=int(rodada)), timeout=30)
        if r.status_code == 404:
            continue
        r.raise_for_status()
        for j in (r.json().get("jogadores") or []):
            if not isinstance(j, dict):
                continue
            try:
                rows.append({
                    "rodada": int(rodada),
                    "atleta_id": int(j["id"]),
                    "v2": float(j["projecao"]),
                    "v2_real": float(j["real"]),
                })
            except (KeyError, TypeError, ValueError):
                pass
    return pd.DataFrame(rows)


def choose(history: pd.DataFrame):
    rounds = sorted(int(r) for r in history.rodada.unique())
    if len(rounds) < MIN_PRIOR_ROUNDS:
        return "v2", {
            "motivo": "historico_insuficiente_fallback_v2",
            "rodadas_usadas": rounds,
            "candidatos": {},
        }

    used = rounds[-WINDOW_SELECTION:]
    h = history[history.rodada.isin(used)].copy()
    ref = metrics(h.real, h.v2)
    details = {}
    eligible = []

    for col in CANDIDATES:
        m = metrics(h.real, h[col])
        checks = {
            "rmse_ate_5pct_v2": m["rmse"] <= ref["rmse"] * RMSE_TOL_V2,
            "bias_absoluto_ate_0_60": abs(m["bias"]) <= BIAS_LIMIT,
        }
        if col == "v2":
            checks = {"baseline_v2": True}
        checks["aprovado"] = all(checks.values())
        details[col] = {"metricas": round6(m), "guardrails": checks}
        if checks["aprovado"]:
            eligible.append(col)

    winner = min(eligible, key=lambda c: (details[c]["metricas"]["mae"], c))
    return winner, {
        "motivo": "menor_mae_no_passado_entre_candidatos_aprovados",
        "rodadas_usadas": used,
        "v2_referencia": round6(ref),
        "candidatos": details,
    }


def bootstrap_by_round(df: pd.DataFrame, challenger: str, baseline: str):
    diffs = []
    for _, g in df.groupby("rodada"):
        a = np.mean(np.abs(g[challenger].to_numpy(float) - g.real.to_numpy(float)))
        b = np.mean(np.abs(g[baseline].to_numpy(float) - g.real.to_numpy(float)))
        diffs.append(float(a - b))
    arr = np.asarray(diffs, float)
    rng = np.random.default_rng(SEED)
    sims = np.asarray([
        np.mean(rng.choice(arr, size=len(arr), replace=True)) for _ in range(BOOTSTRAPS)
    ])
    return {
        "diferenca_mae": round(float(np.mean(arr)), 6),
        "ic95": [round(float(np.quantile(sims, .025)), 6), round(float(np.quantile(sims, .975)), 6)],
        "probabilidade_challenger_melhor": round(float(np.mean(sims < 0)), 4),
        "rodadas_ganhas": int(np.sum(arr < 0)),
        "rodadas_perdidas": int(np.sum(arr > 0)),
    }


def main():
    payload = json.loads(SRC.read_text(encoding="utf-8"))
    base = pd.DataFrame(payload.get("previsoes", []))
    required = {"rodada", "atleta_id", "posicao", "real", "v3h", "nested_calibrado"}
    missing = required - set(base.columns)
    if missing:
        raise SystemExit(f"Colunas ausentes no seletor CatBoost: {sorted(missing)}")

    base = base.rename(columns={"nested_calibrado": "cat_nested"})
    rounds = sorted(int(r) for r in base.rodada.unique())
    v2 = fetch_v2(rounds)
    if v2.empty:
        raise SystemExit("V2 oficial arquivada indisponivel")

    df = base.merge(v2, on=["rodada", "atleta_id"], how="inner")
    df = df[np.abs(df.real - df.v2_real) <= 1e-6].copy()
    if len(df) != len(base):
        raise RuntimeError(f"Cobertura V2 incompleta: {len(df)}/{len(base)}")
    df = df.sort_values(["rodada", "atleta_id"]).reset_index(drop=True)

    predictions = []
    choices = []
    for rodada in rounds:
        cur = df[df.rodada.eq(rodada)].copy()
        hist_all = df[df.rodada.lt(rodada)].copy()
        for pos, g in cur.groupby("posicao"):
            hist = hist_all[hist_all.posicao.eq(pos)].copy()
            method, detail = choose(hist)
            used = detail.get("rodadas_usadas", [])
            max_used = max(used) if used else None
            if max_used is not None and max_used >= rodada:
                raise RuntimeError(f"Vazamento R{rodada}/{pos}: {max_used}")
            for _, row in g.iterrows():
                predictions.append({
                    "rodada": int(rodada),
                    "atleta_id": int(row.atleta_id),
                    "posicao": str(pos),
                    "real": float(row.real),
                    "v2": float(row.v2),
                    "v3h": float(row.v3h),
                    "cat_nested": float(row.cat_nested),
                    "meta_final": float(row[method]),
                    "metodo": method,
                })
            choices.append({
                "rodada_prevista": int(rodada),
                "posicao": str(pos),
                "metodo": method,
                "max_rodada_selecao": max_used,
                "ok_temporal": max_used is None or max_used < rodada,
                **detail,
            })

    pred = pd.DataFrame(predictions)
    if not all(x["ok_temporal"] for x in choices):
        raise RuntimeError("Falha temporal no meta seletor final")

    geral = {c: round6(metrics(pred.real, pred[c])) for c in ["meta_final", "v2", "v3h", "cat_nested"]}
    por_posicao = {
        str(pos): {c: round6(metrics(g.real, g[c])) for c in ["meta_final", "v2", "v3h", "cat_nested"]}
        for pos, g in pred.groupby("posicao")
    }
    out = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "protocolo": (
            "meta-seletor final estritamente temporal por posicao. Para prever R, compara V2 oficial arquivada, "
            "V3-H e CatBoost nested calibrado somente nas ate 5 rodadas OOS anteriores. Exige no passado "
            "RMSE <= 105% da V2 e |bias| <= 0.60 para challengers; V2 e fallback seguro. Nenhum resultado de R "
            "participa da escolha de R."
        ),
        "linhas": int(len(pred)),
        "rodadas": rounds,
        "configuracao": {
            "minimo_rodadas_previas": MIN_PRIOR_ROUNDS,
            "janela_selecao": WINDOW_SELECTION,
            "limite_bias_absoluto": BIAS_LIMIT,
            "tolerancia_rmse_vs_v2": RMSE_TOL_V2,
        },
        "geral": geral,
        "por_posicao": por_posicao,
        "bootstrap_meta_vs_v2": bootstrap_by_round(pred, "meta_final", "v2"),
        "bootstrap_meta_vs_v3h": bootstrap_by_round(pred, "meta_final", "v3h"),
        "bootstrap_meta_vs_cat_nested": bootstrap_by_round(pred, "meta_final", "cat_nested"),
        "contagem_metodos": {str(k): int(v) for k, v in pred.metodo.value_counts().to_dict().items()},
        "provas_temporais_ok": True,
        "escolhas": choices,
        "previsoes": pred.round(6).to_dict(orient="records"),
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Meta-seletor final temporal concluido")
    print("Geral:", geral)
    print("Metodos:", out["contagem_metodos"])
    print("Bootstrap meta vs V2:", out["bootstrap_meta_vs_v2"])


if __name__ == "__main__":
    main()
