#!/usr/bin/env python3
from __future__ import annotations

import json
import warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.ensemble import (
    ExtraTreesRegressor,
    GradientBoostingRegressor,
    HistGradientBoostingRegressor,
    RandomForestRegressor,
)
from sklearn.linear_model import BayesianRidge, ElasticNet, PoissonRegressor, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "derived" / "dataset-walk-forward.csv"
OUT = ROOT / "data" / "reports" / "campeonato-modelos.json"
SCOUTS = ["G","A","FT","FD","FF","FS","PS","I","DS","SG","DP","DE","GC","CV","CA","GS","FC","PC","PP"]
POSITIONS = ["GOL", "LAT", "ZAG", "MEI", "ATA"]
MIN_ROWS = 80
SHRINK_K = 5.0


def feature_cols(scout):
    return [
        "historico_jogos", "mando", "pontos_media3", "pontos_media5", "pontos_ewma",
        f"{scout}_media3", f"{scout}_media5", f"{scout}_ewma",
    ]


def sklearn_models():
    return {
        "ridge": lambda: make_pipeline(StandardScaler(), Ridge(alpha=2.0)),
        "elastic_net": lambda: make_pipeline(StandardScaler(), ElasticNet(alpha=.02, l1_ratio=.25, max_iter=2000, random_state=42)),
        "bayesian_ridge": lambda: make_pipeline(StandardScaler(), BayesianRidge()),
        "poisson": lambda: make_pipeline(StandardScaler(), PoissonRegressor(alpha=.2, max_iter=300)),
        "random_forest": lambda: RandomForestRegressor(n_estimators=80, min_samples_leaf=5, random_state=42, n_jobs=-1),
        "extra_trees": lambda: ExtraTreesRegressor(n_estimators=80, min_samples_leaf=5, random_state=42, n_jobs=-1),
        "gradient_boosting": lambda: GradientBoostingRegressor(n_estimators=80, max_depth=2, min_samples_leaf=5, learning_rate=.04, loss="huber", random_state=42),
        "hist_gradient_boosting": lambda: HistGradientBoostingRegressor(max_iter=80, max_leaf_nodes=15, l2_regularization=1.0, random_state=42),
    }


def temporal_folds(rounds):
    rounds = sorted(int(r) for r in set(rounds))
    candidates = [r for r in rounds if r >= 7]
    if len(candidates) <= 4:
        return [(r, [r]) for r in candidates]
    idx = np.linspace(0, len(candidates) - 1, 4, dtype=int)
    starts = sorted(set(candidates[i] for i in idx))
    folds = []
    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else max(candidates) + 1
        folds.append((start, [r for r in candidates if start <= r < end]))
    return folds


def shrinkage_predict(train, test, scout):
    """Empirical-Bayes simples: média recente do atleta encolhida ao prior da posição.

    O prior é calculado SOMENTE no bloco de treino anterior ao teste.
    """
    ycol = f"target_{scout}"
    prior = float(train[ycol].fillna(0).mean()) if len(train) else 0.0
    recent = test[f"{scout}_media5"].fillna(0).to_numpy(float)
    n = np.minimum(test["historico_jogos"].fillna(0).to_numpy(float), 5.0)
    return np.clip((n * recent + SHRINK_K * prior) / (n + SHRINK_K), 0, None)


def negative_binomial_predict(train, test, scout):
    """GLM Negative Binomial para contagens; treino estritamente anterior ao bloco de teste."""
    ycol = f"target_{scout}"
    feats = feature_cols(scout)
    y = train[ycol].fillna(0).to_numpy(float)
    if not len(y) or float(y.sum()) == 0:
        return np.zeros(len(test), float)
    scaler = StandardScaler()
    xtr = scaler.fit_transform(train[feats].fillna(0).to_numpy(float))
    xte = scaler.transform(test[feats].fillna(0).to_numpy(float))
    xtr = sm.add_constant(xtr, has_constant="add")
    xte = sm.add_constant(xte, has_constant="add")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = sm.GLM(y, xtr, family=sm.families.NegativeBinomial(alpha=1.0))
        fit = model.fit(maxiter=60, disp=0)
    return np.clip(np.asarray(fit.predict(xte), float), 0, None)


def evaluate(df, scout, pos):
    sub = df[df.posicao.eq(pos)].copy()
    ycol = f"target_{scout}"
    feats = feature_cols(scout)
    if ycol not in sub.columns or len(sub) < MIN_ROWS:
        return None

    model_names = [
        "media3", "ewma", "shrinkage_eb", "negative_binomial", *sklearn_models().keys()
    ]
    pred_store = {name: [] for name in model_names}
    actuals = []
    rounds_used = []
    fold_proofs = []

    for start, test_rounds in temporal_folds(sub.rodada.unique()):
        train = sub[sub.rodada < start]
        test = sub[sub.rodada.isin(test_rounds)]
        if len(train) < MIN_ROWS or test.empty:
            continue
        max_train_round = int(train.rodada.max())
        min_test_round = int(test.rodada.min())
        if max_train_round >= min_test_round:
            raise RuntimeError(f"Leakage temporal em {scout}/{pos}: treino {max_train_round} >= teste {min_test_round}")

        Xtr = train[feats].fillna(0).to_numpy(float)
        ytr = train[ycol].fillna(0).to_numpy(float)
        Xte = test[feats].fillna(0).to_numpy(float)
        yte = test[ycol].fillna(0).to_numpy(float)

        pred_store["media3"].extend(np.clip(test[f"{scout}_media3"].fillna(0).to_numpy(float), 0, None))
        pred_store["ewma"].extend(np.clip(test[f"{scout}_ewma"].fillna(0).to_numpy(float), 0, None))
        pred_store["shrinkage_eb"].extend(shrinkage_predict(train, test, scout))
        try:
            pred_store["negative_binomial"].extend(negative_binomial_predict(train, test, scout))
        except Exception:
            pred_store["negative_binomial"].extend(np.repeat(float(np.mean(ytr)), len(yte)))

        for name, factory in sklearn_models().items():
            if float(np.sum(ytr)) == 0:
                pred = np.zeros(len(yte))
            else:
                try:
                    model = factory()
                    model.fit(Xtr, ytr)
                    pred = np.clip(model.predict(Xte), 0, None)
                except Exception:
                    pred = np.repeat(float(np.mean(ytr)), len(yte))
            pred_store[name].extend(pred)

        actuals.extend(yte)
        rounds_used.extend(test.rodada.astype(int).tolist())
        fold_proofs.append({
            "max_rodada_treino": max_train_round,
            "min_rodada_teste": min_test_round,
            "rodadas_teste": sorted(test.rodada.astype(int).unique().tolist()),
            "anti_leakage_ok": max_train_round < min_test_round,
        })

    if not actuals:
        return None

    actual = np.asarray(actuals, float)
    metrics = {}
    for name, preds in pred_store.items():
        p = np.asarray(preds, float)
        metrics[name] = {
            "mae": round(float(mean_absolute_error(actual, p)), 6),
            "rmse": round(float(mean_squared_error(actual, p) ** .5), 6),
            "bias": round(float(np.mean(p - actual)), 6),
            "n": int(len(actual)),
        }
    ranking = sorted(metrics, key=lambda n: (metrics[n]["mae"], metrics[n]["rmse"]))
    return {
        "scout": scout,
        "posicao": pos,
        "ranking": ranking,
        "metricas": metrics,
        "rodadas_teste": sorted(set(rounds_used)),
        "eventos_reais": round(float(actual.sum()), 3),
        "prova_temporal_folds": fold_proofs,
    }


def main():
    df = pd.read_csv(DATA)
    results = []
    for scout in SCOUTS:
        for pos in POSITIONS:
            result = evaluate(df, scout, pos)
            if result:
                results.append(result)
                winner = result["ranking"][0]
                print(f"{scout}/{pos}: {winner} MAE={result['metricas'][winner]['mae']}")

    wins = {}
    for result in results:
        winner = result["ranking"][0]
        wins[winner] = wins.get(winner, 0) + 1

    all_temporal_ok = all(
        fold["anti_leakage_ok"]
        for result in results
        for fold in result["prova_temporal_folds"]
    )
    payload = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "protocolo": "walk-forward em blocos temporais; todo treino termina antes da primeira rodada do respectivo teste",
        "anti_leakage_aprovado": all_temporal_ok,
        "min_linhas_treino": MIN_ROWS,
        "modelos": ["media3", "ewma", "shrinkage_eb", "negative_binomial", *sklearn_models().keys()],
        "novos_challengers": {
            "shrinkage_eb": "média5 do atleta encolhida ao prior da posição calculado somente no treino",
            "negative_binomial": "GLM Negative Binomial para contagens, usando somente o bloco de treino anterior",
        },
        "scouts_testados": SCOUTS,
        "competicoes_validas": len(results),
        "vitorias_modelos": dict(sorted(wins.items(), key=lambda x: (-x[1], x[0]))),
        "resultados": results,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Campeonato concluído: {len(results)} scout×posição válidos; anti-leakage={all_temporal_ok}.")


if __name__ == "__main__":
    main()
