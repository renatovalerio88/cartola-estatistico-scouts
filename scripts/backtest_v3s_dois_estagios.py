#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from catboost import CatBoostClassifier, CatBoostRegressor
from sklearn.ensemble import ExtraTreesClassifier, ExtraTreesRegressor, HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import brier_score_loss, mean_absolute_error, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.cartola_scoring import SCOUT_WEIGHTS

DATA = ROOT / "data" / "derived" / "dataset-walk-forward.csv"
BASE = ROOT / "data" / "reports" / "backtest-v3s-catboost-nested.json"
OUT = ROOT / "data" / "reports" / "backtest-v3s-dois-estagios.json"
POSITIONS = ["GOL", "LAT", "ZAG", "MEI", "ATA"]
START_ROUND = 10
MIN_TRAIN = 80
MIN_COND = 45


def participation_features():
    return [
        "historico_jogos", "historico_atuacoes", "entrou_media3", "entrou_media5",
        "entrou_ewma", "rodadas_desde_atuou", "mando", "pontos_media3",
        "pontos_media5", "pontos_ewma", "time_jogos", "time_gf_media5",
        "time_ga_media5", "adversario_jogos", "adversario_gf_media5", "adversario_ga_media5",
    ]


def conditional_features(scout):
    return [
        "cond_atuacoes", "pontos_cond_media3", "pontos_cond_media5", "pontos_cond_ewma",
        f"{scout}_cond_media3", f"{scout}_cond_media5", f"{scout}_cond_ewma",
        "mando", "time_jogos", "time_gf_media5", "time_ga_media5",
        "adversario_jogos", "adversario_gf_media5", "adversario_ga_media5",
    ]


def participation_factories():
    return {
        "logistic": lambda: make_pipeline(StandardScaler(), LogisticRegression(C=.7, max_iter=400, random_state=42)),
        "extra_trees_cls": lambda: ExtraTreesClassifier(n_estimators=100, min_samples_leaf=6, random_state=42, n_jobs=2),
        "hist_gb_cls": lambda: HistGradientBoostingClassifier(max_iter=80, max_leaf_nodes=12, l2_regularization=1.0, random_state=42),
        "catboost_cls": lambda: CatBoostClassifier(iterations=150, depth=4, learning_rate=.035, loss_function="Logloss", l2_leaf_reg=5.0, random_seed=42, verbose=False, thread_count=2, allow_writing_files=False),
    }


def conditional_factories():
    return {
        "ridge_cond": lambda: make_pipeline(StandardScaler(), Ridge(alpha=2.0)),
        "extra_trees_cond": lambda: ExtraTreesRegressor(n_estimators=80, min_samples_leaf=5, random_state=42, n_jobs=2),
        "hist_gb_cond": lambda: HistGradientBoostingRegressor(max_iter=70, max_leaf_nodes=12, l2_regularization=1.0, random_state=42),
        "catboost_cond": lambda: CatBoostRegressor(iterations=140, depth=4, learning_rate=.035, loss_function="MAE", l2_leaf_reg=4.0, random_seed=42, verbose=False, thread_count=2, allow_writing_files=False),
    }


def pred_participacao(name, train, test):
    if name == "entrou_ewma":
        return np.clip(test.entrou_ewma.fillna(0).to_numpy(float), .01, .99)
    y = train.target_entrou.fillna(0).astype(int).to_numpy()
    if len(np.unique(y)) < 2:
        return np.full(len(test), float(np.mean(y)) if len(y) else .5)
    feats = participation_features()
    model = participation_factories()[name]()
    model.fit(train[feats].fillna(0).to_numpy(float), y)
    p = np.asarray(model.predict_proba(test[feats].fillna(0).to_numpy(float))[:, 1], float)
    return np.clip(np.nan_to_num(p, nan=.5), .01, .99)


def pred_condicional(name, train, test, scout):
    if name == "cond_ewma":
        return np.clip(test[f"{scout}_cond_ewma"].fillna(0).to_numpy(float), 0, None)
    ycol = f"target_{scout}"
    train = train[train.target_entrou.eq(1)].copy()
    if len(train) < MIN_COND or float(train[ycol].fillna(0).abs().sum()) == 0:
        return np.clip(test[f"{scout}_cond_ewma"].fillna(0).to_numpy(float), 0, None)
    feats = conditional_features(scout)
    model = conditional_factories()[name]()
    model.fit(train[feats].fillna(0).to_numpy(float), train[ycol].fillna(0).to_numpy(float))
    p = np.asarray(model.predict(test[feats].fillna(0).to_numpy(float)), float)
    return np.clip(np.nan_to_num(p, nan=0.0), 0, None)


def inner_split(history, current_round):
    prior = history[history.rodada < current_round].copy()
    rounds = sorted(int(r) for r in prior.rodada.unique())
    if len(rounds) < 5:
        return None, None
    valid_rounds = rounds[-2:]
    tr = prior[~prior.rodada.isin(valid_rounds)]
    va = prior[prior.rodada.isin(valid_rounds)]
    if tr.empty or va.empty or int(tr.rodada.max()) >= int(va.rodada.min()) or int(va.rodada.max()) >= current_round:
        return None, None
    return tr, va


def escolher_participacao(history, current_round):
    tr, va = inner_split(history, current_round)
    if tr is None or len(tr) < MIN_TRAIN:
        return "entrou_ewma", {}, None
    scores = {}
    for name in ["entrou_ewma", *participation_factories().keys()]:
        try:
            scores[name] = float(brier_score_loss(va.target_entrou.astype(int), pred_participacao(name, tr, va)))
        except Exception:
            scores[name] = 999999.0
    winner = min(scores, key=lambda k: (scores[k], k))
    return winner, {k: round(v, 6) for k, v in sorted(scores.items(), key=lambda kv: kv[1])}, {
        "max_inner_train": int(tr.rodada.max()), "min_validacao": int(va.rodada.min()), "rodada_prevista": current_round, "ok": True,
    }


def escolher_condicional(history, current_round, scout):
    tr, va = inner_split(history, current_round)
    if tr is None:
        return "cond_ewma", {}, None
    va_entrou = va[va.target_entrou.eq(1)].copy()
    if len(tr[tr.target_entrou.eq(1)]) < MIN_COND or va_entrou.empty:
        return "cond_ewma", {}, None
    scores = {}
    y = va_entrou[f"target_{scout}"].fillna(0).to_numpy(float)
    for name in ["cond_ewma", *conditional_factories().keys()]:
        try:
            scores[name] = float(mean_absolute_error(y, pred_condicional(name, tr, va_entrou, scout)))
        except Exception:
            scores[name] = 999999.0
    winner = min(scores, key=lambda k: (scores[k], k))
    return winner, {k: round(v, 6) for k, v in sorted(scores.items(), key=lambda kv: kv[1])}, {
        "max_inner_train": int(tr.rodada.max()), "min_validacao": int(va.rodada.min()), "rodada_prevista": current_round, "ok": True,
    }


def metric(y, pred):
    y, pred = np.asarray(y, float), np.asarray(pred, float)
    e = pred - y
    return {"n": int(len(y)), "mae": round(float(np.mean(np.abs(e))), 6), "rmse": round(float(np.sqrt(np.mean(e ** 2))), 6), "bias": round(float(np.mean(e)), 6)}


def bootstrap_by_round(pred, challenger, baseline, draws=5000, seed=42):
    deltas = []
    for _, g in pred.groupby("rodada"):
        deltas.append(float(np.mean(np.abs(g[challenger] - g.real)) - np.mean(np.abs(g[baseline] - g.real))))
    arr = np.asarray(deltas, float)
    rng = np.random.default_rng(seed)
    sims = np.asarray([np.mean(rng.choice(arr, size=len(arr), replace=True)) for _ in range(draws)])
    return {
        "delta_mae": round(float(np.mean(arr)), 6),
        "ic95": [round(float(np.quantile(sims, .025)), 6), round(float(np.quantile(sims, .975)), 6)],
        "probabilidade_dois_estagios_melhor": round(float(np.mean(sims < 0)), 4),
        "rodadas_ganhas": int(np.sum(arr < 0)), "rodadas_perdidas": int(np.sum(arr > 0)),
    }


def main():
    df = pd.read_csv(DATA)
    df = df[df.posicao.isin(POSITIONS)].sort_values(["rodada", "atleta_id"]).reset_index(drop=True)
    required = ["cond_atuacoes", "pontos_cond_ewma"]
    if any(c not in df.columns for c in required):
        raise SystemExit("Dataset ainda não possui features condicionais; rode construir_dataset.py")
    scouts = [s for s in SCOUT_WEIGHTS if f"target_{s}" in df.columns]
    predictions, selection_log = [], []
    participation_counts, conditional_counts = {}, {}

    for rodada in sorted(int(r) for r in df.rodada.unique() if int(r) >= START_ROUND):
        current = df[df.rodada.eq(rodada)].copy()
        previous = df[df.rodada.lt(rodada)].copy()
        for pos in POSITIONS:
            test = current[current.posicao.eq(pos)].copy()
            history = previous[previous.posicao.eq(pos)].copy()
            if test.empty:
                continue
            if not history.empty and int(history.rodada.max()) >= rodada:
                raise RuntimeError(f"vazamento outer em R{rodada}/{pos}")

            pmodel, pscores, pproof = escolher_participacao(history, rodada)
            try:
                p_enter = pred_participacao(pmodel, history, test)
            except Exception:
                pmodel, p_enter = "entrou_ewma_fallback", pred_participacao("entrou_ewma", history, test)
            participation_counts[pmodel] = participation_counts.get(pmodel, 0) + 1
            expected_points = np.zeros(len(test), float)

            for scout, weight in SCOUT_WEIGHTS.items():
                if scout not in scouts:
                    continue
                smodel, sscores, sproof = escolher_condicional(history, rodada, scout)
                try:
                    cond = pred_condicional(smodel, history, test, scout)
                except Exception:
                    smodel, cond = "cond_ewma_fallback", pred_condicional("cond_ewma", history, test, scout)
                conditional_counts[smodel] = conditional_counts.get(smodel, 0) + 1
                expected_points += p_enter * cond * float(weight)
                selection_log.append({"rodada": rodada, "posicao": pos, "scout": scout, "modelo_participacao": pmodel, "modelo_condicional": smodel, "brier_validacao": pscores.get(pmodel), "mae_cond_validacao": sscores.get(smodel), "prova_participacao": pproof, "prova_condicional": sproof})

            for i, (_, row) in enumerate(test.iterrows()):
                predictions.append({"rodada": rodada, "atleta_id": int(row.atleta_id), "posicao": pos, "real": float(row.target_pontos), "target_entrou": int(row.target_entrou), "p_entrou": float(p_enter[i]), "v3s_dois_estagios": float(expected_points[i])})
        print(f"R{rodada}: dois estágios concluído")

    pred = pd.DataFrame(predictions)
    if pred.empty:
        raise SystemExit("Sem previsões do modelo em dois estágios")

    if BASE.exists():
        base = pd.DataFrame(json.loads(BASE.read_text(encoding="utf-8")).get("previsoes", []))
        cols = [c for c in ["rodada", "atleta_id", "v3s_catboost_nested", "v3h_hibrido"] if c in base.columns]
        if len(cols) >= 3:
            pred = pred.merge(base[cols], on=["rodada", "atleta_id"], how="left", validate="one_to_one")

    geral = {"v3s_dois_estagios": metric(pred.real, pred.v3s_dois_estagios)}
    for col in ["v3s_catboost_nested", "v3h_hibrido"]:
        if col in pred.columns and pred[col].notna().any():
            g = pred.dropna(subset=[col])
            geral[col] = metric(g.real, g[col])

    part = {"brier": round(float(brier_score_loss(pred.target_entrou, pred.p_entrou)), 6)}
    if pred.target_entrou.nunique() > 1:
        part["auc"] = round(float(roc_auc_score(pred.target_entrou, pred.p_entrou)), 6)
    part["taxa_real_entrada"] = round(float(pred.target_entrou.mean()), 6)
    part["probabilidade_media_prevista"] = round(float(pred.p_entrou.mean()), 6)

    por_posicao = {pos: {"dois_estagios": metric(g.real, g.v3s_dois_estagios), "participacao_brier": round(float(brier_score_loss(g.target_entrou, g.p_entrou)), 6)} for pos, g in pred.groupby("posicao")}
    por_rodada = {str(int(r)): {"n": int(len(g)), "mae_dois_estagios": metric(g.real, g.v3s_dois_estagios)["mae"]} for r, g in pred.groupby("rodada")}

    payload = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "protocolo": "Nested walk-forward em dois estágios: P(entrar em campo) é selecionada por Brier usando apenas rodadas passadas; produção de scouts é treinada somente em atuações anteriores e selecionada por MAE em validação temporal anterior. A previsão final é P(entrada) x E[scout|entrada] x peso oficial do scout.",
        "linhas": int(len(pred)), "rodadas": sorted(pred.rodada.astype(int).unique().tolist()),
        "geral": geral, "participacao": part, "por_posicao": por_posicao, "por_rodada": por_rodada,
        "selecoes_participacao": dict(sorted(participation_counts.items(), key=lambda kv: (-kv[1], kv[0]))),
        "selecoes_condicionais": dict(sorted(conditional_counts.items(), key=lambda kv: (-kv[1], kv[0]))),
        "log_selecao": selection_log,
        "previsoes": pred.round(6).to_dict(orient="records"),
    }
    if "v3s_catboost_nested" in pred.columns:
        g = pred.dropna(subset=["v3s_catboost_nested"])
        if not g.empty:
            payload["bootstrap_vs_catboost_direto"] = bootstrap_by_round(g, "v3s_dois_estagios", "v3s_catboost_nested")
    if "v3h_hibrido" in pred.columns:
        g = pred.dropna(subset=["v3h_hibrido"])
        if not g.empty:
            payload["bootstrap_vs_v3h"] = bootstrap_by_round(g, "v3s_dois_estagios", "v3h_hibrido")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Dois estágios:", geral)
    print("Participação:", part)


if __name__ == "__main__":
    main()
