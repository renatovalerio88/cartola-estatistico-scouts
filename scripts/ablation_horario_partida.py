#!/usr/bin/env python3
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from catboost import CatBoostRegressor
from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "derived" / "dataset-walk-forward.csv"
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "reports" / "ablation-horario-partida.json"
POSITIONS = ["GOL", "LAT", "ZAG", "MEI", "ATA"]
START_ROUND = 10
MIN_TRAIN = 80

BASE_FEATURES = [
    "historico_jogos", "historico_atuacoes", "entrou_media3", "entrou_media5",
    "entrou_ewma", "rodadas_desde_atuou", "pontos_media3", "pontos_media5",
    "pontos_ewma", "mando", "time_jogos", "time_gf_media5", "time_ga_media5",
    "time_gf_ewma", "time_ga_ewma", "adversario_jogos", "adversario_gf_media5",
    "adversario_ga_media5", "adversario_gf_ewma", "adversario_ga_ewma",
]
TIME_FEATURES = [
    "hora_sin", "hora_cos", "jogo_diurno", "jogo_noturno",
    "dia_semana_sin", "dia_semana_cos", "fim_de_semana",
]


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def partidas(path: Path):
    if not path.exists():
        return []
    raw = load(path)
    return raw.get("partidas", raw if isinstance(raw, list) else [])


def parse_dt(value):
    if not value:
        return None
    try:
        return pd.Timestamp(value).to_pydatetime()
    except Exception:
        return None


def construir_contexto_horario():
    features = {}
    provas = []
    for folder in sorted(RAW.glob("rodada-*"), key=lambda p: int(p.name.split("-")[-1])):
        rodada = int(folder.name.split("-")[-1])
        for p in partidas(folder / "partidas.json"):
            if not isinstance(p, dict):
                continue
            dt = parse_dt(p.get("partida_data"))
            if dt is None:
                continue
            hora = dt.hour + dt.minute / 60.0
            dow = dt.weekday()
            ang_h = 2.0 * math.pi * hora / 24.0
            ang_d = 2.0 * math.pi * dow / 7.0
            feat = {
                "hora_sin": math.sin(ang_h),
                "hora_cos": math.cos(ang_h),
                "jogo_diurno": int(11.0 <= hora < 18.0),
                "jogo_noturno": int(hora >= 18.0 or hora < 6.0),
                "dia_semana_sin": math.sin(ang_d),
                "dia_semana_cos": math.cos(ang_d),
                "fim_de_semana": int(dow >= 5),
            }
            for key in ("clube_casa_id", "clube_visitante_id"):
                try:
                    cid = int(p.get(key))
                except (TypeError, ValueError):
                    continue
                features[(rodada, cid)] = feat
                provas.append({
                    "rodada": rodada,
                    "clube_id": cid,
                    "partida_id": p.get("partida_id"),
                    "partida_data": str(p.get("partida_data")),
                    "fonte": f"data/raw/rodada-{rodada:02d}/partidas.json",
                    "somente_metadado_fixture": True,
                })
    if len(features) < 100:
        raise RuntimeError(f"Cobertura insuficiente de horários: {len(features)} pares rodada/clube")
    return features, provas


def factories():
    return {
        "ridge": lambda: make_pipeline(StandardScaler(), Ridge(alpha=8.0)),
        "extra_trees": lambda: ExtraTreesRegressor(
            n_estimators=180, min_samples_leaf=6, random_state=42, n_jobs=2,
        ),
        "hist_gb": lambda: HistGradientBoostingRegressor(
            max_iter=110, max_leaf_nodes=14, l2_regularization=2.0, random_state=42,
        ),
        "catboost": lambda: CatBoostRegressor(
            iterations=180, depth=4, learning_rate=.035, loss_function="MAE",
            l2_leaf_reg=5.0, random_seed=42, verbose=False, thread_count=2,
            allow_writing_files=False,
        ),
    }


def predict(model_name, train, test, features):
    model = factories()[model_name]()
    model.fit(train[features].fillna(0).to_numpy(float), train.target_pontos.to_numpy(float))
    return np.asarray(model.predict(test[features].fillna(0).to_numpy(float)), float)


def metrics(y, p):
    return {
        "mae": float(mean_absolute_error(y, p)),
        "rmse": float(np.sqrt(mean_squared_error(y, p))),
        "bias": float(np.mean(p - y)),
    }


def bootstrap_round_delta(round_deltas, draws=10000, seed=42):
    arr = np.asarray(round_deltas, float)
    rng = np.random.default_rng(seed)
    sims = np.asarray([
        float(np.mean(rng.choice(arr, size=len(arr), replace=True)))
        for _ in range(draws)
    ])
    return {
        "n_rodadas": int(len(arr)),
        "delta_mae_horario_menos_base": round(float(np.mean(arr)), 8),
        "ic95": [round(float(np.quantile(sims, .025)), 8), round(float(np.quantile(sims, .975)), 8)],
        "probabilidade_horario_melhor": round(float(np.mean(sims < 0)), 4),
        "rodadas_ganhas": int(np.sum(arr < 0)),
        "rodadas_perdidas": int(np.sum(arr > 0)),
    }


def main():
    df = pd.read_csv(DATA)
    df = df[df.posicao.isin(POSITIONS)].sort_values(["rodada", "atleta_id"]).reset_index(drop=True)
    missing = [c for c in BASE_FEATURES if c not in df.columns]
    if missing:
        raise SystemExit(f"Dataset sem features base esperadas: {missing}")

    time_ctx, fixture_proofs = construir_contexto_horario()
    for feature in TIME_FEATURES:
        df[feature] = [
            time_ctx.get((int(r), int(c)), {}).get(feature, 0.0)
            for r, c in zip(df.rodada, df.clube_id)
        ]

    coverage = float(np.mean([
        (int(r), int(c)) in time_ctx for r, c in zip(df.rodada, df.clube_id)
    ]))
    if coverage < .95:
        raise RuntimeError(f"Cobertura de horário abaixo de 95%: {coverage:.2%}")

    rows = []
    provas = []
    features_time = BASE_FEATURES + TIME_FEATURES
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
                    p_time = predict(model_name, train, test, features_time)
                except Exception as exc:
                    provas.append({
                        "rodada": rodada, "posicao": pos, "modelo": model_name,
                        "status": "erro", "erro": str(exc)[:250],
                    })
                    continue
                for idx, (_, row) in enumerate(test.iterrows()):
                    rows.append({
                        "rodada": rodada, "atleta_id": int(row.atleta_id), "posicao": pos,
                        "modelo": model_name, "real": float(row.target_pontos),
                        "p_base": float(p_base[idx]), "p_horario": float(p_time[idx]),
                    })
                provas.append({
                    "rodada": rodada, "posicao": pos, "modelo": model_name,
                    "max_train": int(train.rodada.max()), "rodada_prevista": rodada,
                    "status": "ok", "anti_leakage": int(train.rodada.max()) < rodada,
                })
        print(f"R{rodada}: ablation horário concluída")

    pred = pd.DataFrame(rows)
    if pred.empty:
        raise SystemExit("Sem previsões para ablation de horário")

    por_modelo = {}
    gates = []
    for model_name, g in pred.groupby("modelo"):
        y = g.real.to_numpy(float)
        mb = metrics(y, g.p_base.to_numpy(float))
        mt = metrics(y, g.p_horario.to_numpy(float))
        round_deltas = []
        for _, rg in g.groupby("rodada"):
            round_deltas.append(
                mean_absolute_error(rg.real, rg.p_horario) - mean_absolute_error(rg.real, rg.p_base)
            )
        boot = bootstrap_round_delta(round_deltas)
        mae_better = mt["mae"] < mb["mae"]
        rmse_guard = mt["rmse"] <= mb["rmse"] * 1.01
        strong = mae_better and rmse_guard and boot["probabilidade_horario_melhor"] >= .90
        gates.append(strong)
        por_modelo[model_name] = {
            "n": int(len(g)),
            "base": {k: round(v, 8) for k, v in mb.items()},
            "horario": {k: round(v, 8) for k, v in mt.items()},
            "delta_mae": round(mt["mae"] - mb["mae"], 8),
            "bootstrap_por_rodada": boot,
            "gate_individual": "APROVADO" if strong else "REPROVADO",
        }

    por_posicao = {}
    for pos, g in pred.groupby("posicao"):
        mb = metrics(g.real.to_numpy(float), g.p_base.to_numpy(float))
        mt = metrics(g.real.to_numpy(float), g.p_horario.to_numpy(float))
        por_posicao[pos] = {
            "n": int(len(g)),
            "mae_base": round(mb["mae"], 8),
            "mae_horario": round(mt["mae"], 8),
            "delta_mae": round(mt["mae"] - mb["mae"], 8),
        }

    aprovados = int(sum(gates))
    decision = "PROMOVER_HORARIO_PARA_TESTE_POR_SCOUT" if aprovados >= 3 else "NAO_PROMOVER_HORARIO"
    payload = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "status": "APROVADA",
        "decisao": decision,
        "escopo": "Screening científico isolado do horário e dia da semana da partida no Brasileirão 2026.",
        "protocolo": "Ablation walk-forward estrita por rodada e posição. BASE e HORÁRIO usam exatamente as mesmas linhas, alvo e modelo; as features adicionais derivam apenas de partida_data do fixture, nunca de placar, scouts ou eventos ocorridos durante/depois da partida.",
        "nota_temporal": "Horário é metadado exógeno do fixture e não depende do resultado. Para previsões futuras, o horário deve ser congelado no snapshot pré-rodada; esta ablation histórica não usa qualquer variável de resultado para reconstruí-lo.",
        "cobertura_fixture": round(coverage, 6),
        "features_adicionais": TIME_FEATURES,
        "modelos_com_gate_aprovado": aprovados,
        "modelos_testados": len(gates),
        "por_modelo": por_modelo,
        "por_posicao": por_posicao,
        "provas_fixture": fixture_proofs,
        "provas_walk_forward": provas,
        "previsoes": pred.round(8).to_dict(orient="records"),
        "regra_gate": "Promover somente para teste por scout se >=3/4 modelos reduzirem MAE, mantiverem RMSE até +1% e bootstrap por rodada indicar >=90% de probabilidade favorável.",
        "proximo_passo_se_aprovado": "Testar horário por scout/posição e interação com clima pré-jogo antes de qualquer integração na arquitetura V3.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Horário: {decision} | gates {aprovados}/{len(gates)} | cobertura {coverage:.2%}")


if __name__ == "__main__":
    main()
