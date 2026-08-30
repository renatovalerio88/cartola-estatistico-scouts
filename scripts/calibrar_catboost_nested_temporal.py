#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "reports" / "backtest-v3s-catboost-nested.json"
OUT = ROOT / "data" / "reports" / "calibracao-catboost-nested-temporal.json"
MIN_PRIOR_ROUNDS = 3
WINDOW = 5


def metric(y, pred):
    y = np.asarray(y, float)
    pred = np.asarray(pred, float)
    err = pred - y
    return {
        "n": int(len(y)),
        "mae": round(float(np.mean(np.abs(err))), 6),
        "rmse": round(float(np.sqrt(np.mean(err ** 2))), 6),
        "bias": round(float(np.mean(err)), 6),
    }


def bootstrap_by_round(df: pd.DataFrame, challenger: str, baseline: str, draws=5000, seed=42):
    diffs = []
    for _, g in df.groupby("rodada"):
        diffs.append(
            float(np.mean(np.abs(g[challenger] - g.real)) - np.mean(np.abs(g[baseline] - g.real)))
        )
    arr = np.asarray(diffs, float)
    rng = np.random.default_rng(seed)
    sims = np.asarray([np.mean(rng.choice(arr, size=len(arr), replace=True)) for _ in range(draws)])
    return {
        "diferenca_mae_challenger_menos_baseline": round(float(np.mean(arr)), 6),
        "ic95": [round(float(np.quantile(sims, .025)), 6), round(float(np.quantile(sims, .975)), 6)],
        "probabilidade_challenger_melhor": round(float(np.mean(sims < 0)), 4),
        "rodadas_ganhas": int(np.sum(arr < 0)),
        "rodadas_perdidas": int(np.sum(arr > 0)),
    }


def prior_residuals(df: pd.DataFrame, rodada: int, posicao: str, window: int | None):
    prior = df[(df.rodada < rodada) & (df.posicao == posicao)].copy()
    rounds = sorted(int(r) for r in prior.rodada.unique())
    if len(rounds) < MIN_PRIOR_ROUNDS:
        return None, []
    if window is not None:
        used = rounds[-window:]
        prior = prior[prior.rodada.isin(used)]
    else:
        used = rounds
    residual = prior.v3s_catboost_nested - prior.real
    return residual, used


def main():
    payload = json.loads(SRC.read_text(encoding="utf-8"))
    pred = pd.DataFrame(payload.get("previsoes", []))
    required = {"rodada", "atleta_id", "posicao", "real", "v3s_catboost_nested", "v3h_hibrido"}
    missing = required - set(pred.columns)
    if missing:
        raise SystemExit(f"Colunas ausentes: {sorted(missing)}")

    pred = pred.sort_values(["rodada", "atleta_id"]).reset_index(drop=True)
    pred["cal_pos_mean5"] = pred.v3s_catboost_nested.astype(float)
    pred["cal_pos_median5"] = pred.v3s_catboost_nested.astype(float)
    pred["cal_pos_mean_all"] = pred.v3s_catboost_nested.astype(float)
    proofs = []

    for rodada in sorted(int(r) for r in pred.rodada.unique()):
        for pos in sorted(pred.loc[pred.rodada.eq(rodada), "posicao"].unique()):
            mask = pred.rodada.eq(rodada) & pred.posicao.eq(pos)
            residual5, used5 = prior_residuals(pred, rodada, pos, WINDOW)
            residual_all, used_all = prior_residuals(pred, rodada, pos, None)
            if residual5 is not None and len(residual5):
                bias_mean = float(residual5.mean())
                bias_median = float(residual5.median())
                pred.loc[mask, "cal_pos_mean5"] = pred.loc[mask, "v3s_catboost_nested"] - bias_mean
                pred.loc[mask, "cal_pos_median5"] = pred.loc[mask, "v3s_catboost_nested"] - bias_median
            else:
                bias_mean = 0.0
                bias_median = 0.0
            if residual_all is not None and len(residual_all):
                bias_all = float(residual_all.mean())
                pred.loc[mask, "cal_pos_mean_all"] = pred.loc[mask, "v3s_catboost_nested"] - bias_all
            else:
                bias_all = 0.0

            max_used = max(used_all) if used_all else None
            if max_used is not None and max_used >= rodada:
                raise RuntimeError(f"Vazamento na calibração: R{rodada}/{pos}, max prior={max_used}")
            proofs.append({
                "rodada_prevista": rodada,
                "posicao": pos,
                "rodadas_prior_mean5": used5,
                "rodadas_prior_all": used_all,
                "bias_mean5": round(bias_mean, 6),
                "bias_median5": round(bias_median, 6),
                "bias_mean_all": round(bias_all, 6),
                "max_rodada_usada": max_used,
                "ok": max_used is None or max_used < rodada,
            })

    models = ["v3s_catboost_nested", "cal_pos_mean5", "cal_pos_median5", "cal_pos_mean_all", "v3h_hibrido"]
    geral = {m: metric(pred.real, pred[m]) for m in models}
    por_posicao = {
        pos: {m: metric(g.real, g[m]) for m in models}
        for pos, g in pred.groupby("posicao")
    }
    bootstrap = {
        "mean5_vs_raw": bootstrap_by_round(pred, "cal_pos_mean5", "v3s_catboost_nested"),
        "median5_vs_raw": bootstrap_by_round(pred, "cal_pos_median5", "v3s_catboost_nested"),
        "mean_all_vs_raw": bootstrap_by_round(pred, "cal_pos_mean_all", "v3s_catboost_nested"),
        "mean5_vs_v3h": bootstrap_by_round(pred, "cal_pos_mean5", "v3h_hibrido"),
        "median5_vs_v3h": bootstrap_by_round(pred, "cal_pos_median5", "v3h_hibrido"),
        "mean_all_vs_v3h": bootstrap_by_round(pred, "cal_pos_mean_all", "v3h_hibrido"),
    }
    candidates = ["cal_pos_mean5", "cal_pos_median5", "cal_pos_mean_all"]
    best = min(candidates, key=lambda m: geral[m]["mae"])
    best_metrics = geral[best]
    v3h = geral["v3h_hibrido"]
    guardrails = {
        "mae_melhor_que_v3h": best_metrics["mae"] < v3h["mae"],
        "rmse_nao_piora_mais_5pct": best_metrics["rmse"] <= v3h["rmse"] * 1.05,
        "bias_absoluto_ate_0_50": abs(best_metrics["bias"]) <= 0.50,
    }
    guardrails["aprovado_experimentalmente"] = all(guardrails.values())

    out = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "protocolo": (
            "calibracao residual estritamente temporal; para cada R/posicao usa somente residuos OOS "
            "de rodadas anteriores a R; nenhuma estatistica de R participa da calibracao"
        ),
        "linhas": int(len(pred)),
        "rodadas": sorted(pred.rodada.astype(int).unique().tolist()),
        "configuracao": {"janela_rodadas": WINDOW, "minimo_rodadas_previas": MIN_PRIOR_ROUNDS},
        "geral": geral,
        "por_posicao": por_posicao,
        "bootstrap": bootstrap,
        "melhor_calibracao_descritiva": best,
        "guardrails_melhor_calibracao": guardrails,
        "observacao": (
            "A escolha do melhor metodo acima e apenas descritiva ex-post; nao deve ser usada para previsao futura "
            "sem um seletor nested adicional. Os tres metodos sao reportados separadamente para evitar cherry-picking."
        ),
        "provas_temporais": proofs,
        "previsoes": pred.round(6).to_dict(orient="records"),
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Calibracao temporal concluida:")
    for m in models:
        print(m, geral[m])
    print("Melhor descritiva:", best, guardrails)


if __name__ == "__main__":
    main()
