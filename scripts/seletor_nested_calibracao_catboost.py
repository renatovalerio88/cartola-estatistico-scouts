#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "reports" / "calibracao-catboost-nested-temporal.json"
OUT = ROOT / "data" / "reports" / "seletor-nested-calibracao-catboost.json"
V2_RAW = "https://raw.githubusercontent.com/renatovalerio88/cartola-estatistico/main/data/historico/rodada-{rodada:02d}.json"

CANDIDATES = ["cal_pos_mean5", "cal_pos_median5", "cal_pos_mean_all"]
MIN_PRIOR_ROUNDS = 3
WINDOW_SELECTION = 5
BOOTSTRAPS = 5000
SEED = 42
BIAS_LIMIT = 0.50
RMSE_TOL = 1.05


def metrics(y, p):
    y = np.asarray(y, float)
    p = np.asarray(p, float)
    err = p - y
    return {
        "n": int(len(y)),
        "mae": float(np.mean(np.abs(err))),
        "rmse": float(np.sqrt(np.mean(err ** 2))),
        "bias": float(np.mean(err)),
    }


def round6(d):
    return {k: (round(v, 6) if isinstance(v, float) else v) for k, v in d.items()}


def passes_guardrails(candidate: dict, ref: dict):
    checks = {
        "mae_melhor_que_v3h": candidate["mae"] < ref["mae"],
        "rmse_nao_piora_mais_5pct": candidate["rmse"] <= ref["rmse"] * RMSE_TOL,
        "bias_absoluto_ate_0_50": abs(candidate["bias"]) <= BIAS_LIMIT,
    }
    checks["aprovado"] = all(checks.values())
    return checks


def choose_method(history: pd.DataFrame):
    rounds = sorted(int(r) for r in history.rodada.unique())
    if len(rounds) < MIN_PRIOR_ROUNDS:
        return "v3h_hibrido", {
            "motivo": "historico_insuficiente",
            "rodadas_disponiveis": rounds,
            "rodadas_usadas": rounds,
            "candidatos": {},
        }

    used = rounds[-WINDOW_SELECTION:]
    h = history[history.rodada.isin(used)].copy()
    ref = metrics(h.real, h.v3h_hibrido)
    details = {}
    eligible = []
    for col in CANDIDATES:
        m = metrics(h.real, h[col])
        checks = passes_guardrails(m, ref)
        details[col] = {"metricas": round6(m), "guardrails": checks}
        if checks["aprovado"]:
            eligible.append(col)

    if not eligible:
        return "v3h_hibrido", {
            "motivo": "nenhum_candidato_passou_guardrails_no_passado",
            "rodadas_disponiveis": rounds,
            "rodadas_usadas": used,
            "v3h": round6(ref),
            "candidatos": details,
        }

    winner = min(eligible, key=lambda c: (details[c]["metricas"]["mae"], c))
    return winner, {
        "motivo": "menor_mae_entre_candidatos_que_passaram_guardrails_no_passado",
        "rodadas_disponiveis": rounds,
        "rodadas_usadas": used,
        "v3h": round6(ref),
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


def main():
    payload = json.loads(SRC.read_text(encoding="utf-8"))
    df = pd.DataFrame(payload.get("previsoes", []))
    required = {"rodada", "atleta_id", "posicao", "real", "v3h_hibrido", *CANDIDATES}
    missing = required - set(df.columns)
    if missing:
        raise SystemExit(f"Colunas ausentes: {sorted(missing)}")
    df = df.sort_values(["rodada", "atleta_id"]).reset_index(drop=True)

    predictions = []
    choices = []
    for rodada in sorted(int(r) for r in df.rodada.unique()):
        current = df[df.rodada.eq(rodada)].copy()
        history_all = df[df.rodada.lt(rodada)].copy()
        for pos, g in current.groupby("posicao"):
            history = history_all[history_all.posicao.eq(pos)].copy()
            method, detail = choose_method(history)
            used = detail.get("rodadas_usadas", [])
            max_used = max(used) if used else None
            if max_used is not None and max_used >= rodada:
                raise RuntimeError(f"Vazamento no seletor nested R{rodada}/{pos}: {max_used}")
            values = g[method].to_numpy(float)
            for (_, row), p in zip(g.iterrows(), values):
                predictions.append({
                    "rodada": rodada,
                    "atleta_id": int(row.atleta_id),
                    "posicao": str(pos),
                    "real": float(row.real),
                    "v3h": float(row.v3h_hibrido),
                    "nested_calibrado": float(p),
                    "metodo": method,
                })
            choices.append({
                "rodada_prevista": rodada,
                "posicao": str(pos),
                "metodo": method,
                "max_rodada_selecao": max_used,
                "ok_temporal": max_used is None or max_used < rodada,
                **detail,
            })

    pred = pd.DataFrame(predictions)
    if not all(c["ok_temporal"] for c in choices):
        raise RuntimeError("Falha nas provas temporais do seletor nested")

    overall = {
        "nested_calibrado": round6(metrics(pred.real, pred.nested_calibrado)),
        "v3h": round6(metrics(pred.real, pred.v3h)),
    }
    by_pos = {
        str(pos): {
            "nested_calibrado": round6(metrics(g.real, g.nested_calibrado)),
            "v3h": round6(metrics(g.real, g.v3h)),
        }
        for pos, g in pred.groupby("posicao")
    }

    v2 = fetch_v2(sorted(pred.rodada.unique()))
    v2_result = None
    if not v2.empty:
        common = pred.merge(v2, on=["rodada", "atleta_id"], how="inner")
        common = common[np.abs(common.real - common.v2_real) <= 1e-6].copy()
        if not common.empty:
            v2_result = {
                "linhas_comuns": int(len(common)),
                "v2": round6(metrics(common.real, common.v2)),
                "nested_calibrado": round6(metrics(common.real, common.nested_calibrado)),
                "v3h": round6(metrics(common.real, common.v3h)),
                "bootstrap_nested_vs_v2": bootstrap_by_round(common, "nested_calibrado", "v2"),
            }

    counts = pred.metodo.value_counts().to_dict()
    out = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "protocolo": (
            "seletor nested estritamente temporal da calibracao CatBoost: para cada rodada R/posicao, "
            "avalia os metodos apenas nas ate 5 rodadas OOS anteriores, aplica guardrails de MAE/RMSE/bias "
            "somente nesse passado e escolhe o menor MAE entre os aprovados; se nenhum passa ou ha menos de "
            "3 rodadas anteriores, usa V3-H. Resultado de R nunca participa da selecao de R."
        ),
        "linhas": int(len(pred)),
        "rodadas": sorted(pred.rodada.astype(int).unique().tolist()),
        "configuracao": {
            "minimo_rodadas_previas": MIN_PRIOR_ROUNDS,
            "janela_selecao": WINDOW_SELECTION,
            "limite_bias_absoluto": BIAS_LIMIT,
            "tolerancia_rmse_vs_v3h": RMSE_TOL,
        },
        "geral": overall,
        "por_posicao": by_pos,
        "bootstrap_nested_vs_v3h": bootstrap_by_round(pred, "nested_calibrado", "v3h"),
        "comparacao_v2_oficial": v2_result,
        "contagem_metodos": {str(k): int(v) for k, v in counts.items()},
        "provas_temporais_ok": True,
        "escolhas": choices,
        "previsoes": pred.round(6).to_dict(orient="records"),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Seletor nested calibracao CatBoost concluido")
    print("Geral:", overall)
    print("Metodos:", out["contagem_metodos"])
    print("Bootstrap vs V3-H:", out["bootstrap_nested_vs_v3h"])
    if v2_result:
        print("Comparacao V2 oficial:", v2_result)


if __name__ == "__main__":
    main()
