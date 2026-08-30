#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "derived" / "dataset-walk-forward.csv"
OUT = ROOT / "data" / "reports" / "ablation-contexto.json"
POSITIONS = ["GOL", "LAT", "ZAG", "MEI", "ATA"]
MIN_TRAIN = 80
BOOTSTRAP = 10000
SEED = 20260830

BASE = ["historico_jogos", "pontos_media3", "pontos_media5", "pontos_ewma"]
MANDO = ["mando"]
FORCA = [
    "time_jogos", "time_gf_media5", "time_ga_media5", "time_gf_ewma", "time_ga_ewma",
    "adversario_jogos", "adversario_gf_media5", "adversario_ga_media5",
    "adversario_gf_ewma", "adversario_ga_ewma",
]
FEATURE_SETS = {
    "base": BASE,
    "base_mando": BASE + MANDO,
    "base_forca": BASE + FORCA,
    "base_mando_forca": BASE + MANDO + FORCA,
}


def models():
    return {
        "ridge": lambda: make_pipeline(StandardScaler(), Ridge(alpha=2.0)),
        "extra_trees": lambda: ExtraTreesRegressor(
            n_estimators=100, min_samples_leaf=5, random_state=42, n_jobs=-1
        ),
        "hist_gradient_boosting": lambda: HistGradientBoostingRegressor(
            max_iter=100, max_leaf_nodes=15, l2_regularization=1.0, random_state=42
        ),
    }


def metric(y, p):
    y = np.asarray(y, float)
    p = np.asarray(p, float)
    e = p - y
    return {
        "n": int(len(y)),
        "mae": round(float(np.mean(np.abs(e))), 6),
        "rmse": round(float(np.sqrt(np.mean(e ** 2))), 6),
        "bias": round(float(np.mean(e)), 6),
    }


def bootstrap_round_deltas(deltas, n=BOOTSTRAP, seed=SEED):
    vals = np.asarray(deltas, float)
    if len(vals) < 3:
        return None
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(vals), size=(n, len(vals)))
    means = vals[idx].mean(axis=1)
    return {
        "n_rodadas": int(len(vals)),
        "delta_mae_medio": round(float(vals.mean()), 6),
        "ic95": [
            round(float(np.quantile(means, 0.025)), 6),
            round(float(np.quantile(means, 0.975)), 6),
        ],
        "probabilidade_contexto_melhor": round(float(np.mean(means < 0)), 4),
        "rodadas_melhora": int(np.sum(vals < 0)),
        "rodadas_piora": int(np.sum(vals > 0)),
        "rodadas_empate": int(np.sum(vals == 0)),
    }


def evaluate(df, pos, model_name, features):
    sub = df[df.posicao.eq(pos)].copy()
    rounds = sorted(int(r) for r in sub.rodada.dropna().unique() if int(r) >= 7)
    all_y, all_p = [], []
    by_round = {}
    max_train_by_round = {}

    for r in rounds:
        train = sub[sub.rodada < r]
        test = sub[sub.rodada == r]
        if len(train) < MIN_TRAIN or test.empty:
            continue

        # Prova estrutural do corte temporal: nenhuma linha de R ou futura entra no treino.
        max_train = int(train.rodada.max())
        if max_train >= r:
            raise RuntimeError(f"Vazamento detectado: {model_name}/{pos}/R{r}, max_train={max_train}")

        model = models()[model_name]()
        model.fit(
            train[features].fillna(0).to_numpy(float),
            train.target_pontos.to_numpy(float),
        )
        pred = model.predict(test[features].fillna(0).to_numpy(float))
        y = test.target_pontos.to_numpy(float)

        all_y.extend(y)
        all_p.extend(pred)
        by_round[str(r)] = metric(y, pred)
        max_train_by_round[str(r)] = max_train

    if not all_y:
        return None
    return {
        "geral": metric(all_y, all_p),
        "por_rodada": by_round,
        "max_train_por_rodada": max_train_by_round,
        "rodadas": [int(r) for r in by_round],
    }


def main():
    df = pd.read_csv(DATA)
    df = df[df.posicao.isin(POSITIONS)].copy()
    missing = [c for c in set(sum(FEATURE_SETS.values(), [])) if c not in df.columns]
    if missing:
        raise SystemExit(f"Features ausentes para ablation: {missing}")

    detailed = {}
    aggregated = {}

    for model_name in models():
        detailed[model_name] = {}
        aggregated[model_name] = {}
        for variant, features in FEATURE_SETS.items():
            pos_results = {}
            pooled_y, pooled_p = [], []
            round_abs_errors = {}

            for pos in POSITIONS:
                result = evaluate(df, pos, model_name, features)
                if result is None:
                    continue
                pos_results[pos] = result

                # Para o agregado e bootstrap, refazemos apenas as previsões necessárias
                # para manter erros individuais e depois resumir por rodada.
                sub = df[df.posicao.eq(pos)].copy()
                for r in result["rodadas"]:
                    train = sub[sub.rodada < r]
                    test = sub[sub.rodada == r]
                    model = models()[model_name]()
                    model.fit(
                        train[features].fillna(0).to_numpy(float),
                        train.target_pontos.to_numpy(float),
                    )
                    pred = model.predict(test[features].fillna(0).to_numpy(float))
                    y = test.target_pontos.to_numpy(float)
                    pooled_y.extend(y)
                    pooled_p.extend(pred)
                    round_abs_errors.setdefault(r, []).extend(np.abs(pred - y).tolist())

            geral = metric(pooled_y, pooled_p) if pooled_y else None
            mae_por_rodada = {
                str(r): round(float(np.mean(v)), 6)
                for r, v in sorted(round_abs_errors.items())
            }
            detailed[model_name][variant] = {
                "geral": geral,
                "por_posicao": pos_results,
                "mae_por_rodada": mae_por_rodada,
                "features": features,
            }
            aggregated[model_name][variant] = geral
            if geral:
                print(f"{model_name}/{variant}: MAE={geral['mae']} N={geral['n']}")

    factors = {}
    comparisons = [
        ("base_mando", "mando"),
        ("base_forca", "forca_time_adversario"),
        ("base_mando_forca", "mando_mais_forca"),
    ]

    for variant, label in comparisons:
        deltas_global = {}
        bootstrap_by_model = {}
        wins = 0
        valid = 0

        for model_name in models():
            base = aggregated[model_name].get("base")
            cur = aggregated[model_name].get(variant)
            if not base or not cur:
                continue

            delta = round(cur["mae"] - base["mae"], 6)
            deltas_global[model_name] = delta
            valid += 1
            wins += int(delta < 0)

            base_round = detailed[model_name]["base"]["mae_por_rodada"]
            cur_round = detailed[model_name][variant]["mae_por_rodada"]
            common = sorted(set(base_round) & set(cur_round), key=int)
            round_deltas = [cur_round[r] - base_round[r] for r in common]
            bootstrap_by_model[model_name] = bootstrap_round_deltas(
                round_deltas, seed=SEED + sum(ord(c) for c in model_name + variant)
            )

        mean_delta = round(float(np.mean(list(deltas_global.values()))), 6) if deltas_global else None
        significant_models = sum(
            1
            for b in bootstrap_by_model.values()
            if b and b["ic95"][1] < 0
        )
        probable_models = sum(
            1
            for b in bootstrap_by_model.values()
            if b and b["probabilidade_contexto_melhor"] >= 0.80
        )

        if valid and wins >= 2 and significant_models >= 2 and mean_delta is not None and mean_delta < 0:
            signal = "VALIDADO"
        elif valid and wins >= 2 and probable_models >= 2 and mean_delta is not None and mean_delta < 0:
            signal = "PROMISSORIO_FORTE"
        elif valid and wins >= 2 and mean_delta is not None and mean_delta < 0:
            signal = "PROMISSORIO"
        else:
            signal = "NAO_COMPROVADO"

        factors[label] = {
            "delta_mae_vs_base_por_modelo": deltas_global,
            "delta_mae_medio": mean_delta,
            "modelos_com_melhora": wins,
            "modelos_validos": valid,
            "bootstrap_pareado_por_rodada": bootstrap_by_model,
            "modelos_ic95_totalmente_abaixo_zero": significant_models,
            "modelos_probabilidade_melhora_ge_80pct": probable_models,
            "sinal": signal,
        }

    payload = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "protocolo": (
            "Walk-forward estrito rodada a rodada. Para prever R, cada modelo e posição é "
            "reajustado usando exclusivamente rodadas < R. A comparação de contexto usa as "
            "mesmas linhas e bootstrap pareado sobre MAE por rodada."
        ),
        "modelos_fixos": list(models()),
        "feature_sets": FEATURE_SETS,
        "agregado": aggregated,
        "fatores": factors,
        "detalhado": detailed,
        "regra_decisao": {
            "VALIDADO": "delta médio < 0, melhora em >=2/3 modelos e IC95% inteiramente <0 em >=2 modelos",
            "PROMISSORIO_FORTE": "delta médio <0, melhora em >=2/3 e P(melhora)>=80% em >=2 modelos",
            "PROMISSORIO": "delta médio <0 e melhora em >=2/3, sem força estatística suficiente",
            "NAO_COMPROVADO": "demais casos",
            "observacao": "Nenhum status desta análise promove feature automaticamente para V2 ou produção.",
        },
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Ablation walk-forward estrito concluído:")
    for k, v in factors.items():
        print(k, v["sinal"], "delta médio", v["delta_mae_medio"])


if __name__ == "__main__":
    main()
