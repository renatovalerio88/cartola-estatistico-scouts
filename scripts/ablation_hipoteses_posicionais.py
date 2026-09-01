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
OUT = ROOT / "data" / "reports" / "ablation-hipoteses-posicionais.json"
POSITIONS = ["GOL", "LAT", "ZAG", "MEI", "ATA"]
MIN_TRAIN = 80
BOOTSTRAP = 10000
SEED = 20260901

# Núcleo deliberadamente enxuto: forma de pontos + participação + contexto geral.
BASE = [
    "historico_jogos", "historico_atuacoes", "taxa_atuacao_historica",
    "entrou_media3", "entrou_media5", "entrou_ewma", "rodadas_desde_atuou",
    "pontos_media3", "pontos_media5", "pontos_ewma",
    "mando", "time_gf_ewma", "time_ga_ewma",
    "adversario_gf_ewma", "adversario_ga_ewma",
]

# Hipóteses extraídas das dicas posicionais. São apenas variáveis candidatas;
# nenhum peso manual é aplicado. O walk-forward decide se acrescentam sinal.
POSITIONAL = {
    # Defesas + SG: buscar goleiro exigido sem abandonar risco de sofrer gol.
    "GOL": [
        "DE_cond_media3", "DE_cond_media5", "DE_cond_ewma",
        "DP_cond_ewma", "SG_cond_media5", "SG_cond_ewma",
        "GC_cond_ewma",
    ],
    # Produção defensiva + SG + ameaça ofensiva/bola parada via gols/finalizações.
    "ZAG": [
        "DS_cond_media3", "DS_cond_media5", "DS_cond_ewma",
        "SG_cond_media5", "SG_cond_ewma",
        "G_cond_ewma", "FT_cond_ewma", "FD_cond_ewma", "FF_cond_ewma",
    ],
    # Lateral completo: desarme + criação/assistência + finalização + SG.
    "LAT": [
        "DS_cond_media3", "DS_cond_media5", "DS_cond_ewma",
        "A_cond_media3", "A_cond_media5", "A_cond_ewma",
        "FS_cond_ewma", "FT_cond_ewma", "FD_cond_ewma",
        "SG_cond_media5", "SG_cond_ewma",
    ],
    # Permite ao modelo distinguir perfis defensivos/ofensivos e regularidade.
    "MEI": [
        "DS_cond_media3", "DS_cond_media5", "DS_cond_ewma",
        "G_cond_media3", "G_cond_media5", "G_cond_ewma",
        "A_cond_media3", "A_cond_media5", "A_cond_ewma",
        "FT_cond_ewma", "FD_cond_ewma", "FF_cond_ewma", "FS_cond_ewma",
    ],
    # Fase ofensiva: gols, assistências e volume/qualidade de finalização.
    "ATA": [
        "G_cond_media3", "G_cond_media5", "G_cond_ewma",
        "A_cond_media3", "A_cond_media5", "A_cond_ewma",
        "FT_cond_media3", "FT_cond_media5", "FT_cond_ewma",
        "FD_cond_media3", "FD_cond_media5", "FD_cond_ewma",
        "FF_cond_media3", "FF_cond_media5", "FF_cond_ewma",
    ],
}


def model_factories():
    return {
        "ridge": lambda: make_pipeline(StandardScaler(), Ridge(alpha=2.0)),
        "extra_trees": lambda: ExtraTreesRegressor(
            n_estimators=160, min_samples_leaf=5, random_state=42, n_jobs=-1
        ),
        "hist_gradient_boosting": lambda: HistGradientBoostingRegressor(
            max_iter=140, max_leaf_nodes=15, l2_regularization=1.0, random_state=42
        ),
    }


def metrics(y, pred):
    y = np.asarray(y, dtype=float)
    pred = np.asarray(pred, dtype=float)
    err = pred - y
    return {
        "n": int(len(y)),
        "mae": round(float(np.mean(np.abs(err))), 6),
        "rmse": round(float(np.sqrt(np.mean(err ** 2))), 6),
        "bias": round(float(np.mean(err)), 6),
    }


def paired_bootstrap(round_deltas, seed):
    vals = np.asarray(round_deltas, dtype=float)
    if len(vals) < 3:
        return None
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(vals), size=(BOOTSTRAP, len(vals)))
    means = vals[idx].mean(axis=1)
    return {
        "n_rodadas": int(len(vals)),
        "delta_mae_medio_por_rodada": round(float(vals.mean()), 6),
        "ic95": [
            round(float(np.quantile(means, 0.025)), 6),
            round(float(np.quantile(means, 0.975)), 6),
        ],
        "probabilidade_aug_melhor": round(float(np.mean(means < 0)), 4),
        "rodadas_melhora": int(np.sum(vals < 0)),
        "rodadas_piora": int(np.sum(vals > 0)),
        "rodadas_empate": int(np.sum(vals == 0)),
    }


def predict_walk_forward(sub, model_name, features):
    rows = []
    factory = model_factories()[model_name]
    rounds = sorted(int(r) for r in sub.rodada.dropna().unique() if int(r) >= 7)
    for r in rounds:
        train = sub[sub.rodada < r]
        test = sub[sub.rodada == r]
        if len(train) < MIN_TRAIN or test.empty:
            continue
        max_train = int(train.rodada.max())
        if max_train >= r:
            raise RuntimeError(f"Vazamento temporal em {model_name}/R{r}: treino chega a R{max_train}")
        m = factory()
        m.fit(train[features].fillna(0).to_numpy(float), train.target_pontos.to_numpy(float))
        pred = m.predict(test[features].fillna(0).to_numpy(float))
        y = test.target_pontos.to_numpy(float)
        for yy, pp in zip(y, pred):
            rows.append((r, float(yy), float(pp)))
    return rows


def summarize_rows(rows):
    if not rows:
        return None
    y = [r[1] for r in rows]
    p = [r[2] for r in rows]
    per_round = {}
    for rodada in sorted(set(r[0] for r in rows)):
        cur = [r for r in rows if r[0] == rodada]
        per_round[str(rodada)] = metrics([x[1] for x in cur], [x[2] for x in cur])
    return {"geral": metrics(y, p), "por_rodada": per_round}


def decision(delta, bootstrap):
    if bootstrap is None:
        return "AMOSTRA_INSUFICIENTE"
    lo, hi = bootstrap["ic95"]
    prob = bootstrap["probabilidade_aug_melhor"]
    if delta < 0 and hi < 0:
        return "VALIDADO"
    if delta < 0 and prob >= 0.80:
        return "PROMISSORIO_FORTE"
    if delta < 0:
        return "PROMISSORIO"
    return "REJEITADO"


def main():
    df = pd.read_csv(DATA)
    df = df[df.posicao.isin(POSITIONS)].copy()

    needed = set(BASE)
    for cols in POSITIONAL.values():
        needed.update(cols)
    missing = sorted(c for c in needed if c not in df.columns)
    if missing:
        raise SystemExit(f"Features necessárias ausentes: {missing}")

    detailed = {}
    decisions = {}

    for pos in POSITIONS:
        sub = df[df.posicao.eq(pos)].copy()
        aug = BASE + [c for c in POSITIONAL[pos] if c not in BASE]
        detailed[pos] = {}
        model_deltas = []
        model_validations = 0
        model_improvements = 0

        for model_name in model_factories():
            base_rows = predict_walk_forward(sub, model_name, BASE)
            aug_rows = predict_walk_forward(sub, model_name, aug)
            base = summarize_rows(base_rows)
            cand = summarize_rows(aug_rows)
            if base is None or cand is None:
                continue

            if len(base_rows) != len(aug_rows):
                raise RuntimeError(f"Amostras diferentes em {pos}/{model_name}")
            for a, b in zip(base_rows, aug_rows):
                if a[0] != b[0] or a[1] != b[1]:
                    raise RuntimeError(f"Pareamento quebrado em {pos}/{model_name}")

            delta = round(cand["geral"]["mae"] - base["geral"]["mae"], 6)
            common = sorted(set(base["por_rodada"]) & set(cand["por_rodada"]), key=int)
            round_deltas = [
                cand["por_rodada"][r]["mae"] - base["por_rodada"][r]["mae"]
                for r in common
            ]
            boot = paired_bootstrap(round_deltas, SEED + sum(map(ord, pos + model_name)))
            status = decision(delta, boot)
            model_deltas.append(delta)
            model_improvements += int(delta < 0)
            model_validations += int(status == "VALIDADO")
            detailed[pos][model_name] = {
                "base": base,
                "hipotese_posicional": cand,
                "delta_mae": delta,
                "bootstrap_pareado_por_rodada": boot,
                "status": status,
            }
            print(f"{pos}/{model_name}: delta MAE={delta:+.6f} -> {status}")

        mean_delta = round(float(np.mean(model_deltas)), 6) if model_deltas else None
        if model_deltas and model_validations >= 2 and model_improvements >= 2 and mean_delta < 0:
            overall = "VALIDADO"
        elif model_deltas and model_improvements >= 2 and mean_delta < 0:
            overall = "PROMISSORIO_NAO_PROMOVER"
        else:
            overall = "REJEITADO"
        decisions[pos] = {
            "status": overall,
            "delta_mae_medio_modelos": mean_delta,
            "modelos_com_melhora": model_improvements,
            "modelos_validados": model_validations,
            "modelos_testados": len(model_deltas),
            "features_candidatas": POSITIONAL[pos],
        }

    payload = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "objetivo": "Teste final das hipóteses posicionais recebidas, sem pesos manuais e sem promoção automática.",
        "protocolo": (
            "Walk-forward estrito por rodada e posição. Para prever R, treino usa somente rodadas < R. "
            "Base e candidata usam as mesmas observações. O ganho é avaliado por MAE geral e bootstrap "
            "pareado do delta de MAE por rodada em Ridge, Extra Trees e HistGradientBoosting."
        ),
        "base_features": BASE,
        "hipoteses_por_posicao": POSITIONAL,
        "decisoes": decisions,
        "detalhado": detailed,
        "guardrails": {
            "pesos_manuais": False,
            "usa_target_da_rodada_como_feature": False,
            "promove_v2": False,
            "top25_usado_no_treino": False,
            "tecnico": "fora deste dataset de atletas; não é inferido artificialmente neste teste",
            "formacao": "não recebe preferência fixa; deve ser otimizada posteriormente pelo total projetado sob restrições do Cartola",
            "preco_patrimonio": "restrição de otimização, não bônus de score",
        },
        "regra_decisao_posicao": (
            "VALIDADO exige ganho médio, melhora em >=2/3 modelos e validação com IC95% do delta abaixo de zero em >=2 modelos. "
            "PROMISSORIO_NAO_PROMOVER não altera arquitetura final; REJEITADO é descartado."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\nDecisão final por posição:")
    for pos, d in decisions.items():
        print(pos, d["status"], "delta médio", d["delta_mae_medio_modelos"])


if __name__ == "__main__":
    main()
