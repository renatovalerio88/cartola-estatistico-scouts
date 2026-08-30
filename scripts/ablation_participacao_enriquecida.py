#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from catboost import CatBoostClassifier
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "derived" / "dataset-walk-forward.csv"
OUT = ROOT / "data" / "reports" / "ablation-participacao-enriquecida.json"
POSITIONS = ["GOL", "LAT", "ZAG", "MEI", "ATA"]
START_ROUND = 10
MIN_TRAIN = 80

BASE_FEATURES = [
    "historico_jogos", "historico_atuacoes", "entrou_media3", "entrou_media5",
    "entrou_ewma", "rodadas_desde_atuou", "mando", "pontos_media3",
    "pontos_media5", "pontos_ewma", "time_jogos", "time_gf_media5",
    "time_ga_media5", "adversario_jogos", "adversario_gf_media5", "adversario_ga_media5",
]

ENHANCED_ONLY = [
    "taxa_atuacao_historica", "entrou_media2", "entrou_media10",
    "sequencia_atuacoes", "sequencia_ausencias",
]


def factories():
    return {
        "logistic": lambda: make_pipeline(
            StandardScaler(),
            LogisticRegression(C=.7, max_iter=500, random_state=42),
        ),
        "extra_trees": lambda: ExtraTreesClassifier(
            n_estimators=160, min_samples_leaf=6, random_state=42, n_jobs=2,
        ),
        "hist_gb": lambda: HistGradientBoostingClassifier(
            max_iter=100, max_leaf_nodes=12, l2_regularization=1.0, random_state=42,
        ),
        "catboost": lambda: CatBoostClassifier(
            iterations=180, depth=4, learning_rate=.035, loss_function="Logloss",
            l2_leaf_reg=5.0, random_seed=42, verbose=False, thread_count=2,
            allow_writing_files=False,
        ),
    }


def predict(model_name, train, test, features):
    y = train.target_entrou.fillna(0).astype(int).to_numpy()
    if len(np.unique(y)) < 2:
        return np.full(len(test), float(np.mean(y)) if len(y) else .5)
    model = factories()[model_name]()
    model.fit(train[features].fillna(0).to_numpy(float), y)
    p = np.asarray(model.predict_proba(test[features].fillna(0).to_numpy(float))[:, 1], float)
    return np.clip(np.nan_to_num(p, nan=.5), .01, .99)


def auc_safe(y, p):
    return float(roc_auc_score(y, p)) if len(np.unique(y)) > 1 else None


def bootstrap_round_delta(round_deltas, draws=10000, seed=42):
    arr = np.asarray(round_deltas, float)
    rng = np.random.default_rng(seed)
    sims = np.asarray([
        float(np.mean(rng.choice(arr, size=len(arr), replace=True)))
        for _ in range(draws)
    ])
    return {
        "delta_brier_enriquecido_menos_base": round(float(np.mean(arr)), 8),
        "ic95": [round(float(np.quantile(sims, .025)), 8), round(float(np.quantile(sims, .975)), 8)],
        "probabilidade_enriquecido_melhor": round(float(np.mean(sims < 0)), 4),
        "rodadas_ganhas": int(np.sum(arr < 0)),
        "rodadas_perdidas": int(np.sum(arr > 0)),
        "empates": int(np.sum(arr == 0)),
    }


def main():
    df = pd.read_csv(DATA)
    df = df[df.posicao.isin(POSITIONS)].sort_values(["rodada", "atleta_id"]).reset_index(drop=True)
    enhanced = BASE_FEATURES + ENHANCED_ONLY
    missing = [c for c in enhanced if c not in df.columns]
    if missing:
        raise SystemExit(f"Dataset sem features esperadas: {missing}")

    rows = []
    provas = []
    for rodada in sorted(int(r) for r in df.rodada.unique() if int(r) >= START_ROUND):
        train_round = df[df.rodada.lt(rodada)].copy()
        current = df[df.rodada.eq(rodada)].copy()
        if train_round.empty or current.empty:
            continue

        for pos in POSITIONS:
            train = train_round[train_round.posicao.eq(pos)].copy()
            test = current[current.posicao.eq(pos)].copy()
            if len(train) < MIN_TRAIN or test.empty:
                continue
            if int(train.rodada.max()) >= rodada:
                raise RuntimeError(f"Vazamento temporal em R{rodada}/{pos}")

            for model_name in factories():
                try:
                    p_base = predict(model_name, train, test, BASE_FEATURES)
                    p_enh = predict(model_name, train, test, enhanced)
                except Exception as exc:
                    provas.append({
                        "rodada": rodada, "posicao": pos, "modelo": model_name,
                        "status": "erro", "erro": str(exc)[:250],
                    })
                    continue

                for idx, (_, row) in enumerate(test.iterrows()):
                    rows.append({
                        "rodada": rodada,
                        "atleta_id": int(row.atleta_id),
                        "posicao": pos,
                        "modelo": model_name,
                        "real": int(row.target_entrou),
                        "p_base": float(p_base[idx]),
                        "p_enriquecido": float(p_enh[idx]),
                    })
                provas.append({
                    "rodada": rodada, "posicao": pos, "modelo": model_name,
                    "max_train": int(train.rodada.max()), "rodada_prevista": rodada,
                    "status": "ok", "anti_leakage": int(train.rodada.max()) < rodada,
                })
        print(f"R{rodada}: ablation participação concluído")

    pred = pd.DataFrame(rows)
    if pred.empty:
        raise SystemExit("Sem previsões para ablation de participação")

    por_modelo = {}
    gates = []
    for model_name, g in pred.groupby("modelo"):
        y = g.real.to_numpy(int)
        b_base = float(brier_score_loss(y, g.p_base))
        b_enh = float(brier_score_loss(y, g.p_enriquecido))
        auc_base = auc_safe(y, g.p_base.to_numpy(float))
        auc_enh = auc_safe(y, g.p_enriquecido.to_numpy(float))
        round_deltas = []
        for _, rg in g.groupby("rodada"):
            y_r = rg.real.to_numpy(int)
            round_deltas.append(
                float(brier_score_loss(y_r, rg.p_enriquecido) - brier_score_loss(y_r, rg.p_base))
            )
        boot = bootstrap_round_delta(round_deltas)
        improved_brier = b_enh < b_base
        auc_not_worse = auc_base is None or auc_enh is None or auc_enh >= auc_base - .005
        strong = improved_brier and auc_not_worse and boot["probabilidade_enriquecido_melhor"] >= .95
        gates.append(strong)
        por_modelo[model_name] = {
            "n": int(len(g)),
            "brier_base": round(b_base, 8),
            "brier_enriquecido": round(b_enh, 8),
            "delta_brier": round(b_enh - b_base, 8),
            "auc_base": None if auc_base is None else round(auc_base, 6),
            "auc_enriquecido": None if auc_enh is None else round(auc_enh, 6),
            "bootstrap_por_rodada": boot,
            "gate_individual": "APROVADO" if strong else "REPROVADO",
        }

    por_posicao = {}
    for pos, g in pred.groupby("posicao"):
        y = g.real.to_numpy(int)
        por_posicao[pos] = {
            "n": int(len(g)),
            "brier_base": round(float(brier_score_loss(y, g.p_base)), 8),
            "brier_enriquecido": round(float(brier_score_loss(y, g.p_enriquecido)), 8),
        }
        por_posicao[pos]["delta_brier"] = round(
            por_posicao[pos]["brier_enriquecido"] - por_posicao[pos]["brier_base"], 8
        )

    aprovados = int(sum(gates))
    decision = "APROVAR_FEATURES_PARTICIPACAO_ENRIQUECIDAS" if aprovados >= 3 else "NAO_APROVAR_FEATURES_PARTICIPACAO_ENRIQUECIDAS"
    payload = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "status": "APROVADA",
        "decisao": decision,
        "modelos_com_gate_aprovado": aprovados,
        "modelos_testados": len(gates),
        "protocolo": "Ablation walk-forward estrita. Para cada rodada R e posição, o mesmo classificador é treinado exclusivamente em rodadas < R. BASE e ENRIQUECIDO diferem apenas pelas cinco novas features históricas de participação. Nenhuma informação da rodada R entra nas features.",
        "features_base": BASE_FEATURES,
        "features_enriquecidas_adicionais": ENHANCED_ONLY,
        "por_modelo": por_modelo,
        "por_posicao": por_posicao,
        "provas_temporais": provas,
        "previsoes": pred.round(8).to_dict(orient="records"),
        "regra_gate": "Aprovar pacote somente se pelo menos 3/4 modelos tiverem Brier menor, AUC não pior que -0.005 e bootstrap por rodada >=95% de probabilidade favorável.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Participação enriquecida: {decision} | gates {aprovados}/{len(gates)}")


if __name__ == "__main__":
    main()
