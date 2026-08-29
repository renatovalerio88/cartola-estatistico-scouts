#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import PoissonRegressor, Ridge
from sklearn.metrics import mean_absolute_error
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.cartola_scoring import SCOUT_WEIGHTS

DATA = ROOT / "data" / "derived" / "dataset-walk-forward.csv"
OUT = ROOT / "data" / "reports" / "backtest-v3s-nested.json"
POSITIONS = ["GOL", "LAT", "ZAG", "MEI", "ATA"]
MIN_TRAIN = 80
START_ROUND = 10
HYBRID_GRID = [0.0, 0.25, 0.5, 0.75, 1.0]


def scout_feature_cols(scout: str) -> list[str]:
    return [
        "historico_jogos",
        "mando",
        "pontos_media3",
        "pontos_media5",
        "pontos_ewma",
        f"{scout}_media3",
        f"{scout}_media5",
        f"{scout}_ewma",
    ]


def direct_feature_cols() -> list[str]:
    # Contexto já congelado antes da rodada pelo construir_dataset.py.
    return [
        "historico_jogos",
        "pontos_media3",
        "pontos_media5",
        "pontos_ewma",
        "mando",
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


def factories():
    # Subconjunto forte/rápido para seleção nested. O campeonato amplo testa mais famílias.
    return {
        "ridge": lambda: make_pipeline(StandardScaler(), Ridge(alpha=2.0)),
        "poisson": lambda: make_pipeline(
            StandardScaler(), PoissonRegressor(alpha=0.2, max_iter=250)
        ),
        "extra_trees": lambda: ExtraTreesRegressor(
            n_estimators=40,
            min_samples_leaf=5,
            random_state=42,
            n_jobs=-1,
        ),
        "hist_gradient_boosting": lambda: HistGradientBoostingRegressor(
            max_iter=40,
            max_leaf_nodes=12,
            l2_regularization=1.0,
            random_state=42,
        ),
    }


def metric(y, pred):
    y = np.asarray(y, float)
    pred = np.asarray(pred, float)
    err = pred - y
    return {
        "n": int(len(y)),
        "mae": round(float(np.mean(np.abs(err))), 6),
        "rmse": round(float(np.sqrt(np.mean(err**2))), 6),
        "bias": round(float(np.mean(err)), 6),
    }


def baseline_predict(frame: pd.DataFrame, scout: str, name: str):
    col = f"{scout}_{'media3' if name == 'media3' else 'ewma'}"
    return np.clip(frame[col].fillna(0).to_numpy(float), 0, None)


def fit_predict(name: str, train: pd.DataFrame, test: pd.DataFrame, scout: str):
    if name in ("media3", "ewma"):
        return baseline_predict(test, scout, name)
    ycol = f"target_{scout}"
    feats = scout_feature_cols(scout)
    y_train = train[ycol].fillna(0).to_numpy(float)
    if len(y_train) == 0 or float(np.sum(y_train)) == 0:
        return np.zeros(len(test))
    model = factories()[name]()
    model.fit(train[feats].fillna(0).to_numpy(float), y_train)
    return np.clip(model.predict(test[feats].fillna(0).to_numpy(float)), 0, None)


def choose_model(history: pd.DataFrame, scout: str, current_round: int):
    prior = history[history.rodada < current_round].copy()
    rounds = sorted(prior.rodada.unique())
    if len(rounds) < 5:
        return "ewma", {}
    validation_rounds = rounds[-2:]
    inner_train = prior[~prior.rodada.isin(validation_rounds)]
    validation = prior[prior.rodada.isin(validation_rounds)]
    if len(inner_train) < MIN_TRAIN or validation.empty:
        return "ewma", {}
    y = validation[f"target_{scout}"].fillna(0).to_numpy(float)
    scores = {}
    for name in ["media3", "ewma", *factories().keys()]:
        try:
            scores[name] = float(
                mean_absolute_error(y, fit_predict(name, inner_train, validation, scout))
            )
        except Exception:
            scores[name] = 999999.0
    winner = min(scores, key=lambda n: (scores[n], n))
    return winner, {k: round(v, 6) for k, v in sorted(scores.items(), key=lambda kv: kv[1])}


def direct_rf_predict(train: pd.DataFrame, test: pd.DataFrame):
    if len(train) < MIN_TRAIN:
        return test["pontos_ewma"].fillna(0).to_numpy(float)
    feats = direct_feature_cols()
    model = RandomForestRegressor(
        n_estimators=120,
        max_depth=10,
        min_samples_leaf=5,
        max_features=0.75,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(
        train[feats].fillna(0).to_numpy(float),
        train["target_pontos"].fillna(0).to_numpy(float),
    )
    return model.predict(test[feats].fillna(0).to_numpy(float))


def choose_hybrid_alpha(previous_oos: pd.DataFrame):
    """Escolhe peso apenas com previsões OOS de rodadas anteriores.

    alpha=1 usa V3-S puro; alpha=0 usa RF direto do laboratório.
    Não existe ajuste usando o resultado da rodada corrente.
    """
    if previous_oos.empty or previous_oos["rodada"].nunique() < 2:
        return 0.5, {}
    scores = {}
    y = previous_oos["real"].to_numpy(float)
    v3s = previous_oos["v3s_nested"].to_numpy(float)
    direct = previous_oos["direta_rf_lab"].to_numpy(float)
    for alpha in HYBRID_GRID:
        pred = alpha * v3s + (1.0 - alpha) * direct
        scores[str(alpha)] = round(float(mean_absolute_error(y, pred)), 6)
    winner = min(HYBRID_GRID, key=lambda a: (scores[str(a)], -a))
    return float(winner), scores


def main():
    df = pd.read_csv(DATA)
    df = df[df.posicao.isin(POSITIONS)].copy()
    df = df.sort_values(["rodada", "atleta_id"]).reset_index(drop=True)
    scouts = [s for s in SCOUT_WEIGHTS if f"target_{s}" in df.columns]

    predictions = []
    champion_counts = {}
    selection_log = []
    hybrid_log = []

    for rodada in sorted(int(r) for r in df.rodada.unique() if int(r) >= START_ROUND):
        current = df[df.rodada.eq(rodada)].copy()
        previous = df[df.rodada.lt(rodada)].copy()
        if current.empty:
            continue

        v3s_score = np.zeros(len(current), float)
        direct_score = np.zeros(len(current), float)

        for pos in POSITIONS:
            mask = current.posicao.eq(pos)
            test = current[mask]
            history = previous[previous.posicao.eq(pos)]
            if test.empty:
                continue

            local_score = np.zeros(len(test), float)
            for scout, weight in SCOUT_WEIGHTS.items():
                if f"target_{scout}" not in df.columns:
                    continue
                winner, inner_scores = choose_model(history, scout, rodada)
                champion_counts[winner] = champion_counts.get(winner, 0) + 1
                if len(history) < MIN_TRAIN:
                    winner = "ewma"
                try:
                    pred = fit_predict(winner, history, test, scout)
                except Exception:
                    pred = baseline_predict(test, scout, "ewma")
                    winner = "ewma_fallback"
                local_score += pred * float(weight)
                selection_log.append(
                    {
                        "rodada": rodada,
                        "posicao": pos,
                        "scout": scout,
                        "modelo": winner,
                        "mae_validacao": inner_scores.get(winner),
                    }
                )

            v3s_score[np.flatnonzero(mask.to_numpy())] = local_score
            direct_score[np.flatnonzero(mask.to_numpy())] = direct_rf_predict(history, test)

        prior_oos = pd.DataFrame(predictions)
        alpha, alpha_scores = choose_hybrid_alpha(prior_oos)
        hybrid_score = alpha * v3s_score + (1.0 - alpha) * direct_score
        hybrid_log.append(
            {
                "rodada": rodada,
                "alpha_v3s": alpha,
                "alpha_rf_direto": 1.0 - alpha,
                "mae_historico_por_alpha": alpha_scores,
                "rodadas_oos_disponiveis": int(prior_oos.rodada.nunique()) if not prior_oos.empty else 0,
            }
        )

        for j, (_, row) in enumerate(current.iterrows()):
            predictions.append(
                {
                    "rodada": rodada,
                    "atleta_id": int(row.atleta_id),
                    "posicao": row.posicao,
                    "real": float(row.target_pontos),
                    "v3s_nested": float(v3s_score[j]),
                    "direta_rf_lab": float(direct_score[j]),
                    "v3h_hibrido": float(hybrid_score[j]),
                    "alpha_v3s": alpha,
                    "direta_ewma": float(row.pontos_ewma),
                }
            )
        print(f"R{rodada}: {len(current)} jogadores previstos; alpha híbrido V3-S={alpha:.2f}")

    pred = pd.DataFrame(predictions)
    if pred.empty:
        raise SystemExit("Sem previsões nested suficientes")

    architectures = ["v3s_nested", "direta_rf_lab", "v3h_hibrido", "direta_ewma"]
    geral = {name: metric(pred.real, pred[name]) for name in architectures}
    por_pos = {
        pos: {name: metric(group.real, group[name]) for name in architectures}
        for pos, group in pred.groupby("posicao")
    }
    por_rodada = {}
    for rodada, group in pred.groupby("rodada"):
        maes = {name: metric(group.real, group[name])["mae"] for name in architectures}
        vencedor = min(maes, key=lambda name: (maes[name], name))
        por_rodada[str(int(rodada))] = {
            "n": int(len(group)),
            "mae": maes,
            "vencedor": vencedor,
            "alpha_v3s": float(group.alpha_v3s.iloc[0]),
        }

    wins = {name: 0 for name in architectures}
    for row in por_rodada.values():
        wins[row["vencedor"]] += 1

    payload = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "protocolo": (
            "nested walk-forward: em cada R, modelos de scouts usam apenas passado; "
            "RF direto treina somente em histórico < R; híbrido escolhe alpha exclusivamente "
            "com previsões out-of-sample de rodadas anteriores, nunca com o resultado de R"
        ),
        "inicio_rodada": START_ROUND,
        "linhas": int(len(pred)),
        "rodadas": sorted(pred.rodada.astype(int).unique().tolist()),
        "scouts": scouts,
        "modelos_selecao": ["media3", "ewma", *factories().keys()],
        "nota_modelos": (
            "Nested usa subconjunto eficiente; campeonato amplo testa famílias adicionais. "
            "direta_rf_lab é um Random Forest direto reproduzível dentro do V3 e NÃO deve ser "
            "confundido com a implementação exata da V2 de produção; confronto fiel com a V2 será separado."
        ),
        "hibrido": {
            "formula": "alpha * V3-S + (1-alpha) * RF direto do laboratório",
            "grid_alpha": HYBRID_GRID,
            "selecao": "somente histórico OOS anterior à rodada corrente",
            "log": hybrid_log,
        },
        "geral": geral,
        "por_posicao": por_pos,
        "por_rodada": por_rodada,
        "vitorias_por_rodada": wins,
        "selecoes_modelos_scout": dict(
            sorted(champion_counts.items(), key=lambda kv: (-kv[1], kv[0]))
        ),
        "log_selecao": selection_log,
        "previsoes": pred.round(6).to_dict(orient="records"),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Arquiteturas:", geral)
    print("Vitórias por rodada:", wins)


if __name__ == "__main__":
    main()
