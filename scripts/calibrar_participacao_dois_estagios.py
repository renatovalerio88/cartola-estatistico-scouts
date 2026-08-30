#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "reports" / "backtest-v3s-dois-estagios.json"
OUT = ROOT / "data" / "reports" / "calibracao-participacao-dois-estagios.json"
MIN_ROUNDS = 5
EPS = 1e-5


def clip_p(x):
    return np.clip(np.asarray(x, float), EPS, 1.0 - EPS)


def logit(x):
    p = clip_p(x)
    return np.log(p / (1.0 - p))


def position_rates(train: pd.DataFrame) -> tuple[dict[str, float], float]:
    global_rate = float(train.target_entrou.mean()) if len(train) else 0.5
    rates = train.groupby("posicao").target_entrou.mean().to_dict()
    return {str(k): float(v) for k, v in rates.items()}, global_rate


def predict_method(name: str, train: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
    raw = clip_p(test.p_entrou.to_numpy(float))
    if name == "raw":
        return raw

    rates, global_rate = position_rates(train)
    pos_rate = clip_p([rates.get(str(p), global_rate) for p in test.posicao])
    if name == "pos_rate":
        return pos_rate

    if name.startswith("blend_"):
        alpha = float(name.split("_", 1)[1])
        return clip_p(alpha * raw + (1.0 - alpha) * pos_rate)

    if name == "platt":
        y = train.target_entrou.astype(int).to_numpy()
        if len(train) < 100 or len(np.unique(y)) < 2:
            return pos_rate
        model = LogisticRegression(C=1.0, max_iter=500, random_state=42)
        model.fit(logit(train.p_entrou.to_numpy(float)).reshape(-1, 1), y)
        return clip_p(model.predict_proba(logit(raw).reshape(-1, 1))[:, 1])

    raise ValueError(name)


def diagnostics(y, p):
    y = np.asarray(y, int)
    p = clip_p(p)
    out = {
        "n": int(len(y)),
        "brier": round(float(brier_score_loss(y, p)), 6),
        "logloss": round(float(log_loss(y, p, labels=[0, 1])), 6),
        "taxa_real": round(float(np.mean(y)), 6),
        "prob_media": round(float(np.mean(p)), 6),
        "gap_calibracao": round(float(np.mean(p) - np.mean(y)), 6),
    }
    if len(np.unique(y)) > 1:
        out["auc"] = round(float(roc_auc_score(y, p)), 6)
    return out


def reliability(y, p, bins=10):
    frame = pd.DataFrame({"y": np.asarray(y, int), "p": clip_p(p)})
    edges = np.linspace(0, 1, bins + 1)
    frame["bin"] = pd.cut(frame.p, bins=edges, include_lowest=True, duplicates="drop")
    rows = []
    ece = 0.0
    for label, g in frame.groupby("bin", observed=True):
        if g.empty:
            continue
        obs, pred = float(g.y.mean()), float(g.p.mean())
        weight = len(g) / len(frame)
        ece += weight * abs(obs - pred)
        rows.append({"faixa": str(label), "n": int(len(g)), "previsto": round(pred, 6), "real": round(obs, 6), "gap": round(pred - obs, 6)})
    return rows, round(float(ece), 6)


def choose_method(history: pd.DataFrame, current_round: int):
    rounds = sorted(int(r) for r in history.rodada.unique())
    methods = ["raw", "pos_rate", "blend_0.25", "blend_0.50", "blend_0.75", "platt"]
    if len(rounds) < MIN_ROUNDS:
        return "raw", {}, None
    valid_rounds = rounds[-2:]
    tr = history[~history.rodada.isin(valid_rounds)].copy()
    va = history[history.rodada.isin(valid_rounds)].copy()
    if tr.empty or va.empty or int(tr.rodada.max()) >= int(va.rodada.min()) or int(va.rodada.max()) >= current_round:
        return "raw", {}, None
    scores = {}
    for name in methods:
        try:
            scores[name] = float(brier_score_loss(va.target_entrou.astype(int), predict_method(name, tr, va)))
        except Exception:
            scores[name] = 999999.0
    winner = min(scores, key=lambda k: (scores[k], k))
    proof = {"max_inner_train": int(tr.rodada.max()), "min_inner_valid": int(va.rodada.min()), "max_inner_valid": int(va.rodada.max()), "rodada_prevista": int(current_round), "ok": True}
    return winner, {k: round(v, 6) for k, v in sorted(scores.items(), key=lambda kv: kv[1])}, proof


def point_metrics(y, p):
    y, p = np.asarray(y, float), np.asarray(p, float)
    e = p - y
    return {"n": int(len(y)), "mae": round(float(np.mean(np.abs(e))), 6), "rmse": round(float(np.sqrt(np.mean(e ** 2))), 6), "bias": round(float(np.mean(e)), 6)}


def main():
    if not SRC.exists():
        raise SystemExit("Rode backtest_v3s_dois_estagios.py primeiro")
    payload = json.loads(SRC.read_text(encoding="utf-8"))
    pred = pd.DataFrame(payload.get("previsoes", []))
    needed = {"rodada", "posicao", "target_entrou", "p_entrou", "real", "v3s_dois_estagios"}
    missing = needed - set(pred.columns)
    if missing:
        raise SystemExit(f"Previsoes sem colunas: {sorted(missing)}")
    pred = pred.sort_values(["rodada", "atleta_id"]).reset_index(drop=True)
    calibrated = np.zeros(len(pred), float)
    methods_used, selection_log = {}, []

    for rodada in sorted(pred.rodada.astype(int).unique()):
        mask = pred.rodada.eq(rodada)
        history = pred[pred.rodada.lt(rodada)].copy()
        current = pred[mask].copy()
        method, scores, proof = choose_method(history, rodada)
        try:
            pcal = predict_method(method, history, current) if not history.empty else clip_p(current.p_entrou)
        except Exception:
            method, pcal = "raw_fallback", clip_p(current.p_entrou)
        calibrated[np.where(mask)[0]] = pcal
        methods_used[method] = methods_used.get(method, 0) + 1
        selection_log.append({"rodada": int(rodada), "metodo": method, "brier_inner": scores.get(method), "scores": scores, "prova_temporal": proof})

    pred["p_entrou_cal"] = clip_p(calibrated)
    raw_p = clip_p(pred.p_entrou)
    # A produção condicional implícita é recuperável porque o modelo original usa p * soma ponderada de scouts condicionais.
    conditional_points = np.divide(pred.v3s_dois_estagios.to_numpy(float), raw_p, out=np.zeros(len(pred), float), where=raw_p > EPS)
    pred["v3s_dois_estagios_pcal"] = pred.p_entrou_cal.to_numpy(float) * conditional_points

    raw_diag = diagnostics(pred.target_entrou, raw_p)
    cal_diag = diagnostics(pred.target_entrou, pred.p_entrou_cal)
    raw_rel, raw_ece = reliability(pred.target_entrou, raw_p)
    cal_rel, cal_ece = reliability(pred.target_entrou, pred.p_entrou_cal)
    raw_diag["ece10"] = raw_ece
    cal_diag["ece10"] = cal_ece

    points_raw = point_metrics(pred.real, pred.v3s_dois_estagios)
    points_cal = point_metrics(pred.real, pred.v3s_dois_estagios_pcal)
    improves_brier = cal_diag["brier"] < raw_diag["brier"]
    improves_point_mae = points_cal["mae"] < points_raw["mae"]
    improves_abs_bias = abs(points_cal["bias"]) < abs(points_raw["bias"])
    decision = "PARTICIPACAO_CALIBRADA_APROVADA_PARA_CHALLENGER" if (improves_brier and improves_point_mae and improves_abs_bias) else "NAO_INTEGRAR_CALIBRACAO_DE_PARTICIPACAO_NA_PONTUACAO"

    out = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "protocolo": "Calibracao nested exclusivamente sobre previsoes OOS anteriores. Para R, candidatos sao escolhidos por Brier nas duas ultimas rodadas anteriores e ajustados somente com dados anteriores a R; nenhum target de R participa da escolha ou ajuste.",
        "linhas": int(len(pred)),
        "rodadas": sorted(pred.rodada.astype(int).unique().tolist()),
        "participacao_raw": raw_diag,
        "participacao_calibrada": cal_diag,
        "reliability_raw": raw_rel,
        "reliability_calibrada": cal_rel,
        "pontos_raw": points_raw,
        "pontos_com_p_calibrada": points_cal,
        "metodos_por_rodada": dict(sorted(methods_used.items(), key=lambda kv: (-kv[1], kv[0]))),
        "checks": {"brier_melhora": improves_brier, "mae_pontos_melhora": improves_point_mae, "bias_abs_pontos_melhora": improves_abs_bias},
        "decisao": decision,
        "diagnostico": "A calibracao de participacao deve melhorar a probabilidade como probabilidade; ela so entra na pontuacao se tambem melhorar MAE e bias da pontuacao reconstruida.",
        "log_selecao": selection_log,
        "previsoes": pred[["rodada", "atleta_id", "posicao", "target_entrou", "p_entrou", "p_entrou_cal", "real", "v3s_dois_estagios", "v3s_dois_estagios_pcal"]].round(6).to_dict(orient="records"),
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Calibracao nested de participacao concluida")
    print("Raw:", raw_diag)
    print("Calibrada:", cal_diag)
    print("Pontos raw:", points_raw)
    print("Pontos p-cal:", points_cal)
    print("Decisao:", decision)


if __name__ == "__main__":
    main()
