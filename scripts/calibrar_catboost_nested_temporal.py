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
OUT_SUMMARY = ROOT / "data" / "reports" / "calibracao-catboost-nested-resumo.json"
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


def avaliar_guardrails(metrics: dict, v3h: dict) -> dict:
    checks = {
        "mae_melhor_que_v3h": metrics["mae"] < v3h["mae"],
        "rmse_nao_piora_mais_5pct": metrics["rmse"] <= v3h["rmse"] * 1.05,
        "bias_absoluto_ate_0_50": abs(metrics["bias"]) <= 0.50,
    }
    checks["aprovado_experimentalmente"] = all(checks.values())
    return checks


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
    v3h = geral["v3h_hibrido"]
    guardrails_por_candidato = {
        m: avaliar_guardrails(geral[m], v3h)
        for m in candidates
    }

    # O menor MAE continua sendo reportado apenas como descrição ex-post.
    best_descriptive = min(candidates, key=lambda m: geral[m]["mae"])

    # Para declarar um candidato apto aos próximos testes, guardrails vêm antes do MAE.
    # Isso impede que um MAE ligeiramente menor esconda bias/RMSE inadequados.
    eligible = [m for m in candidates if guardrails_por_candidato[m]["aprovado_experimentalmente"]]
    best_guardrail = min(eligible, key=lambda m: geral[m]["mae"]) if eligible else None

    if best_guardrail is None:
        decisao = "SEM_CANDIDATO_APROVADO_NOS_GUARDRAILS"
    else:
        decisao = "CANDIDATO_APROVADO_PARA_NESTED_SELETOR"

    temporal_ok = all(p["ok"] for p in proofs)
    if not temporal_ok:
        raise RuntimeError("Falha nas provas temporais da calibração")

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
        "melhor_calibracao_descritiva": best_descriptive,
        "guardrails_por_candidato": guardrails_por_candidato,
        "melhor_candidato_que_passa_guardrails": best_guardrail,
        "decisao": decisao,
        "provas_temporais_ok": temporal_ok,
        "observacao": (
            "O melhor MAE descritivo e reportado separadamente. Um candidato so avanca se passar MAE, RMSE e bias. "
            "Mesmo aprovado nos guardrails, ele nao e promovido diretamente: precisa de seletor nested adicional "
            "para evitar escolher ex-post o metodo de calibracao usando o proprio periodo de avaliacao."
        ),
        "provas_temporais": proofs,
        "previsoes": pred.round(6).to_dict(orient="records"),
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = {
        "gerado_em": out["gerado_em"],
        "protocolo": out["protocolo"],
        "linhas": out["linhas"],
        "rodadas": out["rodadas"],
        "geral": geral,
        "guardrails_por_candidato": guardrails_por_candidato,
        "melhor_calibracao_descritiva": best_descriptive,
        "melhor_candidato_que_passa_guardrails": best_guardrail,
        "decisao": decisao,
        "provas_temporais_ok": temporal_ok,
        "bootstrap_candidato_vs_v3h": (
            bootstrap["mean5_vs_v3h"] if best_guardrail == "cal_pos_mean5"
            else bootstrap["median5_vs_v3h"] if best_guardrail == "cal_pos_median5"
            else bootstrap["mean_all_vs_v3h"] if best_guardrail == "cal_pos_mean_all"
            else None
        ),
    }
    OUT_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Calibracao temporal concluida:")
    for m in models:
        print(m, geral[m])
    print("Melhor MAE descritivo:", best_descriptive, guardrails_por_candidato[best_descriptive])
    print("Melhor candidato nos guardrails:", best_guardrail)
    print("Decisao:", decisao)


if __name__ == "__main__":
    main()
