#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from catboost import CatBoostRegressor

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.cartola_scoring import SCOUT_WEIGHTS

DATA = ROOT / "data" / "derived" / "dataset-walk-forward.csv"
GATE = ROOT / "data" / "reports" / "gate-contexto-catboost.json"
OUT = ROOT / "data" / "reports" / "ablation-catboost-contexto-nested.json"

POSITIONS = ["GOL", "LAT", "ZAG", "MEI", "ATA"]
START_ROUND = 10
MIN_TRAIN = 80
CAL_WINDOW = 5

BASE_FEATURES = [
    "historico_jogos",
    "pontos_media3",
    "pontos_media5",
    "pontos_ewma",
]

CONTEXT_FEATURES = [
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


def features(scout: str, contexto: bool) -> list[str]:
    cols = [
        *BASE_FEATURES,
        f"{scout}_media3",
        f"{scout}_media5",
        f"{scout}_ewma",
    ]
    if contexto:
        cols += CONTEXT_FEATURES
    return cols


def model() -> CatBoostRegressor:
    return CatBoostRegressor(
        iterations=120,
        depth=4,
        learning_rate=0.035,
        loss_function="MAE",
        l2_leaf_reg=4.0,
        random_seed=42,
        bootstrap_type="No",
        verbose=False,
        thread_count=2,
        allow_writing_files=False,
    )


def predict_scout(train: pd.DataFrame, test: pd.DataFrame, scout: str, contexto: bool) -> np.ndarray:
    ycol = f"target_{scout}"
    feats = features(scout, contexto)
    if len(train) < MIN_TRAIN:
        return np.clip(test[f"{scout}_ewma"].fillna(0).to_numpy(float), 0, None)

    y = train[ycol].fillna(0).to_numpy(float)
    if not len(y) or float(np.sum(np.abs(y))) == 0:
        return np.zeros(len(test), dtype=float)

    reg = model()
    reg.fit(train[feats].fillna(0).to_numpy(float), y)
    pred = np.asarray(reg.predict(test[feats].fillna(0).to_numpy(float)), dtype=float)
    pred = np.nan_to_num(pred, nan=0.0, posinf=0.0, neginf=0.0)
    return np.clip(pred, 0, None)


def metric(y, pred) -> dict:
    y = np.asarray(y, dtype=float)
    pred = np.asarray(pred, dtype=float)
    err = pred - y
    return {
        "n": int(len(y)),
        "mae": round(float(np.mean(np.abs(err))), 6),
        "rmse": round(float(np.sqrt(np.mean(err ** 2))), 6),
        "bias": round(float(np.mean(err)), 6),
    }


def bootstrap_by_round(df: pd.DataFrame, challenger: str, baseline: str, draws: int = 10000, seed: int = 42) -> dict:
    rounds = sorted(int(r) for r in df.rodada.unique())
    deltas = []
    for r in rounds:
        g = df[df.rodada.eq(r)]
        delta = float(
            np.mean(np.abs(g[challenger].to_numpy(float) - g.real.to_numpy(float)))
            - np.mean(np.abs(g[baseline].to_numpy(float) - g.real.to_numpy(float)))
        )
        deltas.append(delta)

    arr = np.asarray(deltas, dtype=float)
    rng = np.random.default_rng(seed)
    sims = np.asarray([
        float(np.mean(rng.choice(arr, size=len(arr), replace=True)))
        for _ in range(draws)
    ])
    return {
        "n_rodadas": int(len(arr)),
        "delta_mae_contexto_on_menos_off": round(float(np.mean(arr)), 6),
        "ic95": [
            round(float(np.quantile(sims, 0.025)), 6),
            round(float(np.quantile(sims, 0.975)), 6),
        ],
        "probabilidade_contexto_on_melhor": round(float(np.mean(sims < 0)), 4),
        "rodadas_contexto_on_melhor": int(np.sum(arr < 0)),
        "rodadas_contexto_off_melhor": int(np.sum(arr > 0)),
        "empates": int(np.sum(arr == 0)),
    }


def aplicar_calibracao_online(pred: pd.DataFrame, col: str) -> tuple[pd.Series, list[dict]]:
    saida = pd.Series(index=pred.index, dtype=float)
    provas = []

    for rodada in sorted(int(r) for r in pred.rodada.unique()):
        atual_idx = pred.index[pred.rodada.eq(rodada)]
        for pos in POSITIONS:
            idx = atual_idx[pred.loc[atual_idx, "posicao"].eq(pos)]
            if len(idx) == 0:
                continue

            hist = pred[(pred.rodada < rodada) & pred.posicao.eq(pos)].copy()
            hist_rounds = sorted(int(r) for r in hist.rodada.unique())[-CAL_WINDOW:]
            hist = hist[hist.rodada.isin(hist_rounds)]

            if hist.empty:
                ajuste = 0.0
                max_usada = None
            else:
                residuo = hist.real.to_numpy(float) - hist[col].to_numpy(float)
                ajuste = float(np.mean(residuo))
                max_usada = int(hist.rodada.max())
                if max_usada >= rodada:
                    raise RuntimeError(
                        f"vazamento calibracao {col}/{pos}: max_usada={max_usada}, prevista={rodada}"
                    )

            saida.loc[idx] = pred.loc[idx, col].to_numpy(float) + ajuste
            provas.append({
                "rodada_prevista": rodada,
                "posicao": pos,
                "max_rodada_calibracao": max_usada,
                "ajuste": round(ajuste, 6),
                "ok": max_usada is None or max_usada < rodada,
            })

    return saida.astype(float), provas


def main() -> None:
    if not GATE.exists():
        raise SystemExit("Gate de contexto ausente. Rode validar_gate_contexto_catboost.py antes.")
    gate = json.loads(GATE.read_text(encoding="utf-8"))
    if not gate.get("aprovado", False):
        raise SystemExit("Gate de contexto nao aprovado; ablation CatBoost ON/OFF bloqueada.")

    df = pd.read_csv(DATA)
    df = df[df.posicao.isin(POSITIONS)].sort_values(["rodada", "atleta_id"]).reset_index(drop=True)
    scouts = [s for s in SCOUT_WEIGHTS if f"target_{s}" in df.columns]

    missing = sorted({c for s in scouts for c in features(s, True) if c not in df.columns})
    if missing:
        raise SystemExit(f"Features ausentes: {missing}")

    rows = []
    temporal_proof = []

    for rodada in sorted(int(r) for r in df.rodada.unique() if int(r) >= START_ROUND):
        current = df[df.rodada.eq(rodada)].copy()
        previous = df[df.rodada.lt(rodada)].copy()
        if current.empty:
            continue

        score_off = np.zeros(len(current), dtype=float)
        score_on = np.zeros(len(current), dtype=float)

        for pos in POSITIONS:
            mask = current.posicao.eq(pos)
            test = current[mask]
            train = previous[previous.posicao.eq(pos)]
            if test.empty:
                continue
            if not train.empty and int(train.rodada.max()) >= rodada:
                raise RuntimeError(f"vazamento outer R{rodada}/{pos}")

            local_off = np.zeros(len(test), dtype=float)
            local_on = np.zeros(len(test), dtype=float)
            for scout, weight in SCOUT_WEIGHTS.items():
                if f"target_{scout}" not in df.columns:
                    continue
                p_off = predict_scout(train, test, scout, contexto=False)
                p_on = predict_scout(train, test, scout, contexto=True)
                local_off += p_off * float(weight)
                local_on += p_on * float(weight)

            indices = np.flatnonzero(mask.to_numpy())
            score_off[indices] = local_off
            score_on[indices] = local_on
            temporal_proof.append({
                "rodada_prevista": rodada,
                "posicao": pos,
                "max_rodada_treino": None if train.empty else int(train.rodada.max()),
                "ok": train.empty or int(train.rodada.max()) < rodada,
            })

        for j, (_, row) in enumerate(current.iterrows()):
            rows.append({
                "rodada": rodada,
                "atleta_id": int(row.atleta_id),
                "posicao": str(row.posicao),
                "real": float(row.target_pontos),
                "catboost_contexto_off": float(score_off[j]),
                "catboost_contexto_on": float(score_on[j]),
            })
        print(f"R{rodada}: {len(current)} jogadores, CatBoost contexto ON/OFF sem leakage")

    pred = pd.DataFrame(rows)
    if pred.empty:
        raise SystemExit("Sem previsoes para ablation CatBoost de contexto")

    pred["catboost_contexto_off_cal"] , proof_off = aplicar_calibracao_online(pred, "catboost_contexto_off")
    pred["catboost_contexto_on_cal"] , proof_on = aplicar_calibracao_online(pred, "catboost_contexto_on")

    geral = {
        "raw_contexto_off": metric(pred.real, pred.catboost_contexto_off),
        "raw_contexto_on": metric(pred.real, pred.catboost_contexto_on),
        "calibrado_contexto_off": metric(pred.real, pred.catboost_contexto_off_cal),
        "calibrado_contexto_on": metric(pred.real, pred.catboost_contexto_on_cal),
    }

    por_posicao = {}
    for pos, g in pred.groupby("posicao"):
        por_posicao[pos] = {
            "contexto_off_cal": metric(g.real, g.catboost_contexto_off_cal),
            "contexto_on_cal": metric(g.real, g.catboost_contexto_on_cal),
        }

    bootstrap = bootstrap_by_round(pred, "catboost_contexto_on_cal", "catboost_contexto_off_cal")
    off = geral["calibrado_contexto_off"]
    on = geral["calibrado_contexto_on"]
    rmse_rel = (on["rmse"] - off["rmse"]) / off["rmse"] if off["rmse"] else 0.0

    checks = {
        "todas_provas_temporais_ok": bool(all(x["ok"] for x in temporal_proof + proof_off + proof_on)),
        "mae_melhora": bool(on["mae"] < off["mae"]),
        "ic95_totalmente_favoravel": bool(bootstrap["ic95"][1] < 0),
        "probabilidade_melhora_ge_90pct": bool(bootstrap["probabilidade_contexto_on_melhor"] >= 0.90),
        "rmse_nao_deteriora_mais_2pct": bool(rmse_rel <= 0.02),
        "bias_absoluto_nao_piora_mais_010": bool(abs(on["bias"]) <= abs(off["bias"]) + 0.10),
    }
    aprovado = bool(all(checks.values()))

    payload = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "objetivo": "Isolar o ganho incremental de mando+forca no CatBoost sob folds temporais identicos.",
        "protocolo": (
            "Para prever R, ambos os bracos treinam apenas em rodadas < R, com hiperparametros identicos. "
            "A unica diferenca e incluir ou remover features de mando/time/adversario. "
            "CatBoost usa bootstrap_type=No nos dois bracos para manter o teste deterministico e evitar amostragem MVS invalida em folds scout-posicao esparsos. "
            "Depois, ambos recebem a mesma calibracao residual online por posicao usando no maximo 5 rodadas OOS anteriores."
        ),
        "gate_contexto_origem": gate.get("decisao"),
        "linhas": int(len(pred)),
        "rodadas": sorted(pred.rodada.astype(int).unique().tolist()),
        "scouts": scouts,
        "features_base": BASE_FEATURES,
        "features_contexto": CONTEXT_FEATURES,
        "geral": geral,
        "delta_calibrado": {
            "mae_on_menos_off": round(on["mae"] - off["mae"], 6),
            "rmse_on_menos_off": round(on["rmse"] - off["rmse"], 6),
            "rmse_variacao_relativa": round(rmse_rel, 6),
            "bias_on_menos_off": round(on["bias"] - off["bias"], 6),
        },
        "bootstrap_pareado_por_rodada": bootstrap,
        "por_posicao": por_posicao,
        "checks": checks,
        "aprovado": aprovado,
        "decisao": "CONTEXTO_VALIDADO_DENTRO_CATBOOST" if aprovado else "CONTEXTO_NAO_CONFIRMADO_DENTRO_CATBOOST",
        "provas_temporais_outer": temporal_proof,
        "provas_calibracao_off": proof_off,
        "provas_calibracao_on": proof_on,
        "previsoes": pred.round(6).to_dict(orient="records"),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Ablation CatBoost contexto:", geral)
    print("Bootstrap:", bootstrap)
    print("Decisao:", payload["decisao"])


if __name__ == "__main__":
    main()
