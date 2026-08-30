#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from catboost import CatBoostRegressor
from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingRegressor
from sklearn.linear_model import PoissonRegressor, Ridge
from sklearn.metrics import mean_absolute_error
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.cartola_scoring import SCOUT_WEIGHTS

DATA = ROOT / "data" / "derived" / "dataset-walk-forward.csv"
BASE = ROOT / "data" / "reports" / "backtest-v3s-nested.json"
OUT = ROOT / "data" / "reports" / "backtest-v3s-catboost-nested.json"
POSITIONS = ["GOL", "LAT", "ZAG", "MEI", "ATA"]
MIN_TRAIN = 80
START_ROUND = 10


def feature_cols(scout: str) -> list[str]:
    return [
        "historico_jogos",
        "mando",
        "pontos_media3",
        "pontos_media5",
        "pontos_ewma",
        f"{scout}_media3",
        f"{scout}_media5",
        f"{scout}_ewma",
        "time_jogos",
        "time_gf_media5",
        "time_ga_media5",
        "time_gf_ewma",
        "time_ga_ewma",
        "adversario_jogos",
        "adversario_gf_media5",
        "adversario_ga_media5",
        "adversario_gf_ewma",
        "adversario_ga_ewma",
    ]


def core_factories():
    return {
        "ridge": lambda: make_pipeline(StandardScaler(), Ridge(alpha=2.0)),
        "poisson": lambda: make_pipeline(StandardScaler(), PoissonRegressor(alpha=0.2, max_iter=250)),
        "extra_trees": lambda: ExtraTreesRegressor(
            n_estimators=40, min_samples_leaf=5, random_state=42, n_jobs=2
        ),
        "hist_gradient_boosting": lambda: HistGradientBoostingRegressor(
            max_iter=40, max_leaf_nodes=12, l2_regularization=1.0, random_state=42
        ),
        "catboost": lambda: CatBoostRegressor(
            iterations=120,
            depth=4,
            learning_rate=0.035,
            loss_function="MAE",
            l2_leaf_reg=4.0,
            random_seed=42,
            verbose=False,
            thread_count=2,
            allow_writing_files=False,
        ),
    }


def baseline_predict(frame: pd.DataFrame, scout: str, name: str):
    col = f"{scout}_{'media3' if name == 'media3' else 'ewma'}"
    return np.clip(frame[col].fillna(0).to_numpy(float), 0, None)


def fit_predict(name: str, train: pd.DataFrame, test: pd.DataFrame, scout: str):
    if name in ("media3", "ewma"):
        return baseline_predict(test, scout, name)
    ycol = f"target_{scout}"
    feats = feature_cols(scout)
    y = train[ycol].fillna(0).to_numpy(float)
    if not len(y) or float(np.sum(np.abs(y))) == 0:
        return np.zeros(len(test))
    model = core_factories()[name]()
    model.fit(train[feats].fillna(0).to_numpy(float), y)
    pred = np.asarray(model.predict(test[feats].fillna(0).to_numpy(float)), float)
    pred = np.nan_to_num(pred, nan=0.0, posinf=0.0, neginf=0.0)
    return np.clip(pred, 0, None)


def choose_model(history: pd.DataFrame, scout: str, current_round: int):
    prior = history[history.rodada < current_round].copy()
    rounds = sorted(int(r) for r in prior.rodada.unique())
    if len(rounds) < 5:
        return "ewma", {}, None
    validation_rounds = rounds[-2:]
    inner_train = prior[~prior.rodada.isin(validation_rounds)]
    validation = prior[prior.rodada.isin(validation_rounds)]
    if len(inner_train) < MIN_TRAIN or validation.empty:
        return "ewma", {}, None
    max_train = int(inner_train.rodada.max())
    min_valid = int(validation.rodada.min())
    if max_train >= min_valid or min_valid >= current_round:
        raise RuntimeError(
            f"vazamento temporal {scout}: treino={max_train}, validacao={min_valid}, atual={current_round}"
        )
    y = validation[f"target_{scout}"].fillna(0).to_numpy(float)
    scores = {}
    for name in ["media3", "ewma", *core_factories().keys()]:
        try:
            scores[name] = float(mean_absolute_error(y, fit_predict(name, inner_train, validation, scout)))
        except Exception:
            scores[name] = 999999.0
    winner = min(scores, key=lambda n: (scores[n], n))
    proof = {
        "max_rodada_inner_train": max_train,
        "min_rodada_validacao": min_valid,
        "rodada_prevista": current_round,
        "ok": True,
    }
    return winner, {k: round(v, 6) for k, v in sorted(scores.items(), key=lambda kv: kv[1])}, proof


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


def bootstrap_by_round(pred: pd.DataFrame, challenger: str, baseline: str, draws=5000, seed=42):
    rounds = sorted(pred.rodada.unique())
    per_round = []
    for r in rounds:
        g = pred[pred.rodada.eq(r)]
        per_round.append(
            float(np.mean(np.abs(g[challenger] - g.real)) - np.mean(np.abs(g[baseline] - g.real)))
        )
    arr = np.asarray(per_round, float)
    rng = np.random.default_rng(seed)
    sims = np.asarray([np.mean(rng.choice(arr, size=len(arr), replace=True)) for _ in range(draws)])
    return {
        "diferenca_mae_challenger_menos_baseline": round(float(np.mean(arr)), 6),
        "ic95": [round(float(np.quantile(sims, .025)), 6), round(float(np.quantile(sims, .975)), 6)],
        "probabilidade_challenger_melhor": round(float(np.mean(sims < 0)), 4),
        "rodadas_ganhas": int(np.sum(arr < 0)),
        "rodadas_perdidas": int(np.sum(arr > 0)),
    }


def main():
    df = pd.read_csv(DATA)
    df = df[df.posicao.isin(POSITIONS)].sort_values(["rodada", "atleta_id"]).reset_index(drop=True)
    scouts = [s for s in SCOUT_WEIGHTS if f"target_{s}" in df.columns]
    predictions = []
    selections = []
    counts = {}

    for rodada in sorted(int(r) for r in df.rodada.unique() if int(r) >= START_ROUND):
        current = df[df.rodada.eq(rodada)].copy()
        previous = df[df.rodada.lt(rodada)].copy()
        if current.empty:
            continue
        score = np.zeros(len(current), float)
        for pos in POSITIONS:
            mask = current.posicao.eq(pos)
            test = current[mask]
            history = previous[previous.posicao.eq(pos)]
            if test.empty:
                continue
            if not history.empty and int(history.rodada.max()) >= rodada:
                raise RuntimeError(f"vazamento outer em R{rodada}/{pos}")
            local = np.zeros(len(test), float)
            for scout, weight in SCOUT_WEIGHTS.items():
                if f"target_{scout}" not in df.columns:
                    continue
                winner, scores, proof = choose_model(history, scout, rodada)
                if len(history) < MIN_TRAIN:
                    winner = "ewma"
                try:
                    pred = fit_predict(winner, history, test, scout)
                except Exception:
                    pred = baseline_predict(test, scout, "ewma")
                    winner = "ewma_fallback"
                counts[winner] = counts.get(winner, 0) + 1
                local += pred * float(weight)
                selections.append({
                    "rodada": rodada,
                    "posicao": pos,
                    "scout": scout,
                    "modelo": winner,
                    "mae_validacao": scores.get(winner),
                    "prova_temporal": proof,
                })
            score[np.flatnonzero(mask.to_numpy())] = local

        for j, (_, row) in enumerate(current.iterrows()):
            predictions.append({
                "rodada": rodada,
                "atleta_id": int(row.atleta_id),
                "posicao": row.posicao,
                "real": float(row.target_pontos),
                "v3s_catboost_nested": float(score[j]),
            })
        print(f"R{rodada}: {len(current)} jogadores previstos sem leakage")

    pred = pd.DataFrame(predictions)
    if pred.empty:
        raise SystemExit("Sem previsões CatBoost nested")

    base = json.loads(BASE.read_text(encoding="utf-8"))
    base_pred = pd.DataFrame(base.get("previsoes", []))[
        ["rodada", "atleta_id", "v3s_nested", "v3h_hibrido", "direta_rf_lab"]
    ]
    pred = pred.merge(base_pred, on=["rodada", "atleta_id"], how="inner", validate="one_to_one")
    geral = {
        "v3s_catboost_nested": metric(pred.real, pred.v3s_catboost_nested),
        "v3s_nested_core": metric(pred.real, pred.v3s_nested),
        "v3h_atual": metric(pred.real, pred.v3h_hibrido),
        "rf_lab": metric(pred.real, pred.direta_rf_lab),
    }
    por_posicao = {
        pos: {
            "v3s_catboost_nested": metric(g.real, g.v3s_catboost_nested),
            "v3s_nested_core": metric(g.real, g.v3s_nested),
            "v3h_atual": metric(g.real, g.v3h_hibrido),
        }
        for pos, g in pred.groupby("posicao")
    }
    por_rodada = {}
    for r, g in pred.groupby("rodada"):
        maes = {
            "v3s_catboost_nested": metric(g.real, g.v3s_catboost_nested)["mae"],
            "v3s_nested_core": metric(g.real, g.v3s_nested)["mae"],
            "v3h_atual": metric(g.real, g.v3h_hibrido)["mae"],
        }
        por_rodada[str(int(r))] = {"n": int(len(g)), "mae": maes, "vencedor": min(maes, key=maes.get)}

    payload = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "protocolo": (
            "nested walk-forward estrito: para prever R, outer train usa somente rodadas < R; "
            "a escolha CatBoost vs baselines/modelos core usa apenas inner validation em rodadas < R; "
            "nenhum resultado de R entra na seleção, treino ou hiperparametros"
        ),
        "linhas": int(len(pred)),
        "rodadas": sorted(pred.rodada.astype(int).unique().tolist()),
        "modelos_candidatos": ["media3", "ewma", *core_factories().keys()],
        "geral": geral,
        "por_posicao": por_posicao,
        "por_rodada": por_rodada,
        "bootstrap_catboost_vs_core": bootstrap_by_round(pred, "v3s_catboost_nested", "v3s_nested"),
        "bootstrap_catboost_vs_v3h_atual": bootstrap_by_round(pred, "v3s_catboost_nested", "v3h_hibrido"),
        "selecoes_modelos": dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))),
        "log_selecao": selections,
        "previsoes": pred.round(6).to_dict(orient="records"),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Resultado CatBoost nested:", geral)
    print("Selecoes:", payload["selecoes_modelos"])


if __name__ == "__main__":
    main()
