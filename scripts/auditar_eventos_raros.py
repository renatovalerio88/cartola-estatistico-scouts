#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss

from benchmark_scouts import (
    MIN_ROWS,
    POSITIONS,
    SCOUTS,
    feature_cols,
    negative_binomial_predict,
    sanitize_predictions,
    shrinkage_predict,
    sklearn_models,
    temporal_folds,
)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "derived" / "dataset-walk-forward.csv"
OUT = ROOT / "data" / "reports" / "auditoria-eventos-raros.json"
MAX_PREVALENCIA_RARA = 0.15
MIN_EVENTOS = 2


def count_to_event_probability(pred: np.ndarray) -> np.ndarray:
    """Converte contagem esperada em P(evento >= 1) sob aproximação Poisson.

    A transformação é monotônica e usa apenas a própria previsão OOS. Ela serve para
    auditar discriminação/calibração de eventos raros sem alterar o campeonato por MAE.
    """
    lam = np.clip(np.asarray(pred, float), 0.0, 50.0)
    return np.clip(1.0 - np.exp(-lam), 0.0, 1.0)


def predict_oos(df: pd.DataFrame, scout: str, pos: str):
    sub = df[df.posicao.eq(pos)].copy()
    ycol = f"target_{scout}"
    feats = feature_cols(scout)
    if ycol not in sub.columns or len(sub) < MIN_ROWS:
        return None

    model_names = [
        "media3",
        "ewma",
        "shrinkage_eb",
        "negative_binomial",
        *sklearn_models().keys(),
    ]
    pred_store = {name: [] for name in model_names}
    actuals: list[float] = []
    fold_proofs = []

    for start, test_rounds in temporal_folds(sub.rodada.unique()):
        train = sub[sub.rodada < start]
        test = sub[sub.rodada.isin(test_rounds)]
        if len(train) < MIN_ROWS or test.empty:
            continue

        max_train_round = int(train.rodada.max())
        min_test_round = int(test.rodada.min())
        if max_train_round >= min_test_round:
            raise RuntimeError(
                f"Leakage temporal em auditoria rara {scout}/{pos}: "
                f"treino {max_train_round} >= teste {min_test_round}"
            )

        xtr = train[feats].fillna(0).to_numpy(float)
        ytr = train[ycol].fillna(0).to_numpy(float)
        xte = test[feats].fillna(0).to_numpy(float)
        yte = test[ycol].fillna(0).to_numpy(float)

        baselines = {
            "media3": np.clip(test[f"{scout}_media3"].fillna(0).to_numpy(float), 0, None),
            "ewma": np.clip(test[f"{scout}_ewma"].fillna(0).to_numpy(float), 0, None),
            "shrinkage_eb": shrinkage_predict(train, test, scout),
        }
        for name, raw in baselines.items():
            pred, _ = sanitize_predictions(raw, ytr, len(yte))
            pred_store[name].extend(pred)

        try:
            raw = negative_binomial_predict(train, test, scout)
            pred, _ = sanitize_predictions(raw, ytr, len(yte))
        except Exception:
            pred = np.repeat(float(np.mean(ytr)), len(yte))
        pred_store["negative_binomial"].extend(pred)

        for name, factory in sklearn_models().items():
            if float(np.sum(ytr)) == 0:
                raw = np.zeros(len(yte))
            else:
                try:
                    model = factory()
                    model.fit(xtr, ytr)
                    raw = model.predict(xte)
                except Exception:
                    raw = np.repeat(float(np.mean(ytr)), len(yte))
            pred, _ = sanitize_predictions(raw, ytr, len(yte))
            pred_store[name].extend(pred)

        actuals.extend(yte)
        fold_proofs.append(
            {
                "max_rodada_treino": max_train_round,
                "min_rodada_teste": min_test_round,
                "anti_leakage_ok": max_train_round < min_test_round,
            }
        )

    if not actuals:
        return None

    actual = np.asarray(actuals, float)
    event = (actual > 0).astype(int)
    prevalence = float(event.mean())
    n_events = int(event.sum())

    if prevalence <= 0 or prevalence > MAX_PREVALENCIA_RARA or n_events < MIN_EVENTOS:
        return None

    metrics = {}
    for name, values in pred_store.items():
        pred = np.asarray(values, float)
        if len(pred) != len(actual):
            raise RuntimeError(f"Shape inválido em {scout}/{pos}/{name}")
        prob = count_to_event_probability(pred)
        brier = float(brier_score_loss(event, prob))
        ap = float(average_precision_score(event, prob)) if len(np.unique(event)) > 1 else None
        metrics[name] = {
            "brier_evento": round(brier, 6),
            "average_precision": round(ap, 6) if ap is not None else None,
            "prob_media": round(float(prob.mean()), 6),
            "calibration_bias": round(float(prob.mean() - prevalence), 6),
        }

    ranking_brier = sorted(metrics, key=lambda n: metrics[n]["brier_evento"])
    ranking_ap = sorted(
        metrics,
        key=lambda n: (
            -(metrics[n]["average_precision"] if metrics[n]["average_precision"] is not None else -1),
            metrics[n]["brier_evento"],
        ),
    )

    return {
        "scout": scout,
        "posicao": pos,
        "n": int(len(actual)),
        "eventos": n_events,
        "prevalencia": round(prevalence, 6),
        "ranking_brier": ranking_brier,
        "ranking_average_precision": ranking_ap,
        "metricas": metrics,
        "prova_temporal_folds": fold_proofs,
    }


def main():
    df = pd.read_csv(DATA)
    results = []
    for scout in SCOUTS:
        for pos in POSITIONS:
            result = predict_oos(df, scout, pos)
            if result:
                results.append(result)
                print(
                    f"{scout}/{pos}: prev={result['prevalencia']:.3f} "
                    f"Brier={result['ranking_brier'][0]} "
                    f"AP={result['ranking_average_precision'][0]}"
                )

    brier_wins = {}
    ap_wins = {}
    for result in results:
        brier_winner = result["ranking_brier"][0]
        ap_winner = result["ranking_average_precision"][0]
        brier_wins[brier_winner] = brier_wins.get(brier_winner, 0) + 1
        ap_wins[ap_winner] = ap_wins.get(ap_winner, 0) + 1

    payload = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "objetivo": (
            "Complementar MAE/RMSE para scouts raros. MAE pode favorecer previsões quase-zero; "
            "esta auditoria mede ocorrência, calibração e discriminação sem alterar o ranking principal."
        ),
        "protocolo": (
            "Mesmos folds walk-forward do campeonato; P(evento>=1)=1-exp(-lambda_prevista); "
            "nenhum dado da rodada teste entra no treino."
        ),
        "criterio_evento_raro": {
            "prevalencia_maxima": MAX_PREVALENCIA_RARA,
            "min_eventos_oos": MIN_EVENTOS,
        },
        "anti_leakage_aprovado": all(
            fold["anti_leakage_ok"]
            for result in results
            for fold in result["prova_temporal_folds"]
        ),
        "competicoes_raras_validas": len(results),
        "vitorias_brier": dict(sorted(brier_wins.items(), key=lambda x: (-x[1], x[0]))),
        "vitorias_average_precision": dict(sorted(ap_wins.items(), key=lambda x: (-x[1], x[0]))),
        "resultados": results,
        "regra_de_decisao": (
            "Não promover modelo de scout raro só por MAE. Exigir que o challenger não apresente "
            "degradação material de Brier/calibração e observar average precision antes de uso definitivo."
        ),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"Auditoria concluída: {len(results)} scout×posição raros; "
        f"anti-leakage={payload['anti_leakage_aprovado']}."
    )


if __name__ == "__main__":
    main()
