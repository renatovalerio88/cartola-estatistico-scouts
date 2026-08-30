#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data" / "reports" / "backtest-v3s-dois-estagios.json"
OUT = ROOT / "data" / "reports" / "calibracao-producao-condicional-dois-estagios.json"
POSITIONS = ["GOL", "LAT", "ZAG", "MEI", "ATA"]
MIN_FIT = 40
INNER_VALID_ROUNDS = 2
BIAS_LIMIT = 0.50
RMSE_MAX_REL = 1.05


def metric(y, pred):
    y = np.asarray(y, float)
    pred = np.asarray(pred, float)
    e = pred - y
    return {
        "n": int(len(y)),
        "mae": round(float(np.mean(np.abs(e))), 6),
        "rmse": round(float(np.sqrt(np.mean(e ** 2))), 6),
        "bias": round(float(np.mean(e)), 6),
    }


def derive_conditional_points(df):
    p = np.clip(df["p_entrou"].to_numpy(float), 0.01, 1.0)
    raw = df["v3s_dois_estagios"].to_numpy(float) / p
    return np.nan_to_num(raw, nan=0.0, posinf=0.0, neginf=0.0)


def fit_params(method, train):
    participants = train[train.target_entrou.eq(1)].copy()
    if len(participants) < MIN_FIT:
        return {"method": "raw"}
    residual = participants.real.to_numpy(float) - participants.cond_points_raw.to_numpy(float)
    if method == "mean_all":
        return {"method": method, "offset": float(np.mean(residual))}
    if method == "mean5":
        rounds = sorted(participants.rodada.astype(int).unique())[-5:]
        g = participants[participants.rodada.isin(rounds)]
        return {"method": method, "offset": float(np.mean(g.real - g.cond_points_raw))}
    if method == "median5":
        rounds = sorted(participants.rodada.astype(int).unique())[-5:]
        g = participants[participants.rodada.isin(rounds)]
        return {"method": method, "offset": float(np.median(g.real - g.cond_points_raw))}
    if method == "shrink_mean":
        mean_res = float(np.mean(residual))
        shrink = len(participants) / (len(participants) + 80.0)
        return {"method": method, "offset": mean_res * shrink, "shrink": shrink}
    if method == "ridge_linear":
        x = participants[["cond_points_raw"]].to_numpy(float)
        y = participants.real.to_numpy(float)
        model = Ridge(alpha=10.0).fit(x, y)
        return {"method": method, "intercept": float(model.intercept_), "coef": float(model.coef_[0])}
    return {"method": "raw"}


def apply_params(params, frame):
    raw = frame.cond_points_raw.to_numpy(float)
    method = params.get("method", "raw")
    if method in {"mean_all", "mean5", "median5", "shrink_mean"}:
        cond = raw + float(params.get("offset", 0.0))
    elif method == "ridge_linear":
        cond = float(params.get("intercept", 0.0)) + float(params.get("coef", 1.0)) * raw
    else:
        cond = raw
    return np.nan_to_num(cond, nan=0.0, posinf=0.0, neginf=0.0)


def point_prediction(params, frame):
    cond = apply_params(params, frame)
    return frame.p_entrou.to_numpy(float) * cond


def inner_split(history, current_round):
    rounds = sorted(int(r) for r in history.rodada.unique() if int(r) < current_round)
    if len(rounds) < 5:
        return None, None
    valid_rounds = rounds[-INNER_VALID_ROUNDS:]
    train_rounds = [r for r in rounds if r not in valid_rounds]
    tr = history[history.rodada.isin(train_rounds)].copy()
    va = history[history.rodada.isin(valid_rounds)].copy()
    if tr.empty or va.empty:
        return None, None
    if int(tr.rodada.max()) >= int(va.rodada.min()) or int(va.rodada.max()) >= current_round:
        raise RuntimeError(f"vazamento no inner split antes de R{current_round}")
    return tr, va


def choose_method(history, current_round):
    tr, va = inner_split(history, current_round)
    if tr is None or len(tr[tr.target_entrou.eq(1)]) < MIN_FIT:
        return "raw", {}, None
    methods = ["raw", "mean_all", "mean5", "median5", "shrink_mean", "ridge_linear"]
    scores = {}
    for method in methods:
        params = fit_params(method, tr)
        pred = point_prediction(params, va)
        scores[method] = float(np.mean(np.abs(pred - va.real.to_numpy(float))))
    winner = min(scores, key=lambda k: (scores[k], k))
    proof = {
        "max_inner_train": int(tr.rodada.max()),
        "min_inner_valid": int(va.rodada.min()),
        "max_inner_valid": int(va.rodada.max()),
        "rodada_prevista": int(current_round),
        "ok": True,
    }
    return winner, {k: round(v, 6) for k, v in sorted(scores.items(), key=lambda kv: kv[1])}, proof


def bootstrap_by_round(df, challenger, baseline, draws=5000, seed=42):
    deltas = []
    for _, g in df.groupby("rodada"):
        deltas.append(float(np.mean(np.abs(g[challenger] - g.real)) - np.mean(np.abs(g[baseline] - g.real))))
    arr = np.asarray(deltas, float)
    rng = np.random.default_rng(seed)
    sims = np.asarray([np.mean(rng.choice(arr, size=len(arr), replace=True)) for _ in range(draws)])
    return {
        "n_rodadas": int(len(arr)),
        "delta_mae": round(float(np.mean(arr)), 6),
        "ic95": [round(float(np.quantile(sims, 0.025)), 6), round(float(np.quantile(sims, 0.975)), 6)],
        "probabilidade_calibrado_melhor": round(float(np.mean(sims < 0)), 4),
        "rodadas_ganhas": int(np.sum(arr < 0)),
        "rodadas_perdidas": int(np.sum(arr > 0)),
    }


def main():
    if not BASE.exists():
        raise SystemExit("Rode backtest_v3s_dois_estagios.py antes")
    payload = json.loads(BASE.read_text(encoding="utf-8"))
    pred = pd.DataFrame(payload.get("previsoes", []))
    required = {"rodada", "atleta_id", "posicao", "real", "target_entrou", "p_entrou", "v3s_dois_estagios"}
    missing = required - set(pred.columns)
    if missing:
        raise SystemExit(f"Colunas ausentes no backtest dois estágios: {sorted(missing)}")
    pred = pred[pred.posicao.isin(POSITIONS)].sort_values(["rodada", "atleta_id"]).reset_index(drop=True)
    pred["cond_points_raw"] = derive_conditional_points(pred)
    pred["v3s_dois_estagios_prod_cal"] = pred.v3s_dois_estagios.astype(float)

    logs = []
    method_counts = {}
    for rodada in sorted(pred.rodada.astype(int).unique()):
        for pos in POSITIONS:
            idx = pred.index[(pred.rodada.eq(rodada)) & (pred.posicao.eq(pos))]
            if len(idx) == 0:
                continue
            history = pred[(pred.rodada < rodada) & (pred.posicao.eq(pos))].copy()
            current = pred.loc[idx].copy()
            method, scores, proof = choose_method(history, rodada)
            params = fit_params(method, history)
            calibrated = point_prediction(params, current)
            pred.loc[idx, "v3s_dois_estagios_prod_cal"] = calibrated
            method_counts[method] = method_counts.get(method, 0) + 1
            logs.append({
                "rodada": int(rodada),
                "posicao": pos,
                "metodo": method,
                "mae_inner": scores.get(method),
                "scores": scores,
                "parametros": {k: round(float(v), 6) if isinstance(v, (float, np.floating)) else v for k, v in params.items()},
                "prova_temporal": proof,
            })

    raw = metric(pred.real, pred.v3s_dois_estagios)
    calibrated = metric(pred.real, pred.v3s_dois_estagios_prod_cal)
    boot = bootstrap_by_round(pred, "v3s_dois_estagios_prod_cal", "v3s_dois_estagios")
    by_pos = {}
    for pos, g in pred.groupby("posicao"):
        by_pos[pos] = {
            "raw": metric(g.real, g.v3s_dois_estagios),
            "producao_calibrada": metric(g.real, g.v3s_dois_estagios_prod_cal),
        }
    by_round = {}
    for r, g in pred.groupby("rodada"):
        by_round[str(int(r))] = {
            "raw_mae": metric(g.real, g.v3s_dois_estagios)["mae"],
            "cal_mae": metric(g.real, g.v3s_dois_estagios_prod_cal)["mae"],
        }

    checks = {
        "mae_melhora": calibrated["mae"] < raw["mae"],
        "rmse_dentro_guardrail": calibrated["rmse"] <= raw["rmse"] * RMSE_MAX_REL,
        "bias_abs_ate_050": abs(calibrated["bias"]) <= BIAS_LIMIT,
        "bootstrap_ic95_favoravel": boot["ic95"][1] < 0,
    }
    approved = bool(checks["mae_melhora"] and checks["rmse_dentro_guardrail"] and checks["bias_abs_ate_050"])
    decision = "PRODUCAO_CONDICIONAL_APROVADA_COMO_CHALLENGER" if approved else "NAO_INTEGRAR_PRODUCAO_CONDICIONAL_CALIBRADA"

    out = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "protocolo": "Calibracao nested da producao condicional. Para prever R, cada posicao escolhe o metodo apenas por OOS de rodadas anteriores; parametros sao ajustados somente com participantes anteriores. A selecao usa MAE final de pontos na validacao temporal anterior, nunca o resultado de R.",
        "linhas": int(len(pred)),
        "rodadas": sorted(pred.rodada.astype(int).unique().tolist()),
        "raw": raw,
        "producao_condicional_calibrada": calibrated,
        "bootstrap_vs_raw": boot,
        "por_posicao": by_pos,
        "por_rodada": by_round,
        "metodos": dict(sorted(method_counts.items(), key=lambda kv: (-kv[1], kv[0]))),
        "checks": checks,
        "decisao": decision,
        "log_selecao": logs,
        "previsoes": pred[["rodada", "atleta_id", "posicao", "real", "target_entrou", "p_entrou", "cond_points_raw", "v3s_dois_estagios", "v3s_dois_estagios_prod_cal"]].round(6).to_dict(orient="records"),
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Calibracao nested da producao condicional concluida")
    print("Raw:", raw)
    print("Calibrada:", calibrated)
    print("Bootstrap:", boot)
    print("Decisao:", decision)


if __name__ == "__main__":
    main()
