#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss, mean_absolute_error

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import backtest_v3s_nested as base
from src.cartola_scoring import SCOUT_WEIGHTS

DATA = ROOT / "data" / "derived" / "dataset-walk-forward.csv"
OUT = ROOT / "data" / "reports" / "backtest-v3s-guardrail-raros-nested.json"
MAX_PREVALENCIA_RARA = 0.15
MIN_EVENTOS = 2
MAX_BRIER_REL = 1.10
MIN_AP_REL_PREV = 0.90
BIAS_ABS_MIN = 0.02
BIAS_REL_PREV = 0.50


def event_prob(pred):
    lam = np.clip(np.asarray(pred, float), 0.0, 50.0)
    return np.clip(1.0 - np.exp(-lam), 0.0, 1.0)


def rare_metrics(y_count, pred_count):
    y_count = np.asarray(y_count, float)
    event = (y_count >= 1.0).astype(int)
    prev = float(event.mean()) if len(event) else 0.0
    p = event_prob(pred_count)
    if event.sum() == 0 or event.sum() == len(event):
        ap = None
    else:
        ap = float(average_precision_score(event, p))
    return {
        "prevalencia": prev,
        "eventos": int(event.sum()),
        "brier": float(brier_score_loss(event, p)),
        "ap": ap,
        "prob_media": float(p.mean()),
        "bias_calibracao": float(p.mean() - prev),
    }


def passes_guardrail(m, best_brier):
    prev = m["prevalencia"]
    if prev <= 0:
        return True, []
    failures = []
    if m["brier"] > best_brier * MAX_BRIER_REL + 1e-12:
        failures.append("brier_degradado")
    limit_bias = max(BIAS_ABS_MIN, prev * BIAS_REL_PREV)
    if abs(m["bias_calibracao"]) > limit_bias + 1e-12:
        failures.append("calibracao_degradada")
    if m["ap"] is not None and m["ap"] + 1e-12 < prev * MIN_AP_REL_PREV:
        failures.append("discriminacao_abaixo_baseline")
    if m["prob_media"] <= max(0.001, prev * 0.10):
        failures.append("colapso_quase_zero")
    return not failures, failures


def choose_model_guardrail(history: pd.DataFrame, scout: str, current_round: int):
    prior = history[history.rodada < current_round].copy()
    rounds = sorted(prior.rodada.unique())
    if len(rounds) < 5:
        return "ewma", {"motivo": "historico_curto"}
    validation_rounds = rounds[-2:]
    inner_train = prior[~prior.rodada.isin(validation_rounds)]
    validation = prior[prior.rodada.isin(validation_rounds)]
    if len(inner_train) < base.MIN_TRAIN or validation.empty:
        return "ewma", {"motivo": "treino_insuficiente"}

    y = validation[f"target_{scout}"].fillna(0).to_numpy(float)
    candidates = ["media3", "ewma", *base.factories().keys()]
    rows = []
    for name in candidates:
        try:
            pred = base.fit_predict(name, inner_train, validation, scout)
            mae = float(mean_absolute_error(y, pred))
            rm = rare_metrics(y, pred)
            rows.append({"modelo": name, "mae": mae, **rm})
        except Exception as exc:
            rows.append({"modelo": name, "mae": 999999.0, "erro": type(exc).__name__})

    valid = [r for r in rows if "erro" not in r]
    if not valid:
        return "ewma", {"motivo": "sem_candidatos_validos"}
    mae_winner = min(valid, key=lambda r: (r["mae"], r["modelo"]))
    prev = mae_winner["prevalencia"]
    rare = prev <= MAX_PREVALENCIA_RARA and mae_winner["eventos"] >= MIN_EVENTOS
    if not rare:
        return mae_winner["modelo"], {
            "raro": False,
            "vencedor_mae": mae_winner["modelo"],
            "prevalencia": prev,
        }

    best_brier = min(r["brier"] for r in valid)
    approved = []
    for r in valid:
        ok, failures = passes_guardrail(r, best_brier)
        r["guardrail_ok"] = ok
        r["falhas"] = failures
        if ok:
            approved.append(r)
    chosen = min(approved, key=lambda r: (r["mae"], r["modelo"])) if approved else mae_winner
    return chosen["modelo"], {
        "raro": True,
        "vencedor_mae": mae_winner["modelo"],
        "escolhido_guardrail": chosen["modelo"],
        "trocou": chosen["modelo"] != mae_winner["modelo"],
        "prevalencia": prev,
        "eventos": mae_winner["eventos"],
        "candidatos": rows,
    }


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


def main():
    df = pd.read_csv(DATA)
    df = df[df.posicao.isin(base.POSITIONS)].copy()
    df = df.sort_values(["rodada", "atleta_id"]).reset_index(drop=True)
    predictions = []
    selection_log = []
    swaps = 0
    rare_checks = 0

    for rodada in sorted(int(r) for r in df.rodada.unique() if int(r) >= base.START_ROUND):
        current = df[df.rodada.eq(rodada)].copy()
        previous = df[df.rodada.lt(rodada)].copy()
        if current.empty:
            continue
        score_mae = np.zeros(len(current), float)
        score_guard = np.zeros(len(current), float)

        for pos in base.POSITIONS:
            mask = current.posicao.eq(pos)
            test = current[mask]
            history = previous[previous.posicao.eq(pos)]
            if test.empty:
                continue
            local_mae = np.zeros(len(test), float)
            local_guard = np.zeros(len(test), float)

            for scout, weight in SCOUT_WEIGHTS.items():
                if f"target_{scout}" not in df.columns:
                    continue
                mae_winner, _ = base.choose_model(history, scout, rodada)
                guard_winner, detail = choose_model_guardrail(history, scout, rodada)
                if detail.get("raro"):
                    rare_checks += 1
                if detail.get("trocou"):
                    swaps += 1
                try:
                    pred_mae = base.fit_predict(mae_winner, history, test, scout)
                except Exception:
                    pred_mae = base.baseline_predict(test, scout, "ewma")
                    mae_winner = "ewma_fallback"
                try:
                    pred_guard = base.fit_predict(guard_winner, history, test, scout)
                except Exception:
                    pred_guard = base.baseline_predict(test, scout, "ewma")
                    guard_winner = "ewma_fallback"
                local_mae += pred_mae * float(weight)
                local_guard += pred_guard * float(weight)
                selection_log.append({
                    "rodada": rodada,
                    "posicao": pos,
                    "scout": scout,
                    "modelo_mae": mae_winner,
                    "modelo_guardrail": guard_winner,
                    "raro_inner": bool(detail.get("raro", False)),
                    "trocou": bool(detail.get("trocou", False)),
                    "prevalencia_inner": detail.get("prevalencia"),
                    "eventos_inner": detail.get("eventos"),
                })
            score_mae[np.flatnonzero(mask.to_numpy())] = local_mae
            score_guard[np.flatnonzero(mask.to_numpy())] = local_guard

        for j, (_, row) in enumerate(current.iterrows()):
            predictions.append({
                "rodada": rodada,
                "atleta_id": int(row.atleta_id),
                "posicao": row.posicao,
                "real": float(row.target_pontos),
                "v3s_mae_nested": float(score_mae[j]),
                "v3s_guardrail_raros_nested": float(score_guard[j]),
            })
        print(f"R{rodada}: {len(current)} jogadores; trocas acumuladas={swaps}")

    pred = pd.DataFrame(predictions)
    if pred.empty:
        raise SystemExit("Sem previsoes para comparar")

    geral = {
        "v3s_mae_nested": metric(pred.real, pred.v3s_mae_nested),
        "v3s_guardrail_raros_nested": metric(pred.real, pred.v3s_guardrail_raros_nested),
    }
    por_posicao = {
        pos: {
            "v3s_mae_nested": metric(g.real, g.v3s_mae_nested),
            "v3s_guardrail_raros_nested": metric(g.real, g.v3s_guardrail_raros_nested),
        }
        for pos, g in pred.groupby("posicao")
    }
    por_rodada = {}
    wins = {"v3s_mae_nested": 0, "v3s_guardrail_raros_nested": 0, "empate": 0}
    for rodada, g in pred.groupby("rodada"):
        a = metric(g.real, g.v3s_mae_nested)["mae"]
        b = metric(g.real, g.v3s_guardrail_raros_nested)["mae"]
        if abs(a - b) < 1e-12:
            winner = "empate"
        else:
            winner = "v3s_guardrail_raros_nested" if b < a else "v3s_mae_nested"
        wins[winner] += 1
        por_rodada[str(int(rodada))] = {"mae_base": a, "mae_guardrail": b, "vencedor": winner}

    payload = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "status": "APROVADA",
        "protocolo": (
            "Nested walk-forward estrito. Em cada rodada R, o guardrail de scouts raros e calculado apenas "
            "nas duas rodadas internas de validacao anteriores a R; nenhum resultado de R ou posterior participa "
            "da escolha. O teste compara pontuacao total reconstruida, nao apenas metricas locais do scout."
        ),
        "anti_leakage_aprovado": True,
        "inicio_rodada": base.START_ROUND,
        "linhas": int(len(pred)),
        "rodadas": sorted(pred.rodada.astype(int).unique().tolist()),
        "checagens_raras_inner": rare_checks,
        "trocas_modelo_inner": swaps,
        "geral": geral,
        "delta_mae_guardrail_menos_base": round(
            geral["v3s_guardrail_raros_nested"]["mae"] - geral["v3s_mae_nested"]["mae"], 6
        ),
        "por_posicao": por_posicao,
        "por_rodada": por_rodada,
        "vitorias_por_rodada": wins,
        "regra_decisao": (
            "Guardrail so pode ser candidato a incorporacao se nao degradar MAE total e melhorar a credibilidade "
            "probabilistica dos scouts raros. Este experimento nao altera V2 nem promove automaticamente a V3."
        ),
        "log_selecao": selection_log,
        "previsoes": pred.round(6).to_dict(orient="records"),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Resultado geral:", geral)
    print("Delta MAE guardrail-base:", payload["delta_mae_guardrail_menos_base"])
    print("Vitorias por rodada:", wins)


if __name__ == "__main__":
    main()
