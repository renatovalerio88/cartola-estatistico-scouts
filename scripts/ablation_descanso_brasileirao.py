#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import defaultdict
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
OUT = ROOT / "data" / "reports" / "ablation-descanso-brasileirao.json"
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
REST_FEATURES = [
    "dias_desde_ultimo_brasileirao",
    "descanso_curto_brasileirao",
    "descanso_longo_brasileirao",
    "jogos_brasileirao_ultimos14d",
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
        return pd.Timestamp(value)
    except Exception:
        return None


def calendario_brasileirao():
    """Monta contexto exclusivamente a partir das datas de partidas do Brasileirão.

    A feature da rodada R usa a data agendada da própria partida de R (informação
    disponível pré-rodada) e somente jogos de rodadas < R com data anterior à
    partida atual. Não usa placar, scouts ou resultado da rodada R.
    """
    jogos_por_rodada = defaultdict(dict)
    historico_por_clube = defaultdict(list)

    folders = sorted(RAW.glob("rodada-*"), key=lambda p: int(p.name.split("-")[-1]))
    for folder in folders:
        rodada = int(folder.name.split("-")[-1])
        for p in partidas(folder / "partidas.json"):
            if not isinstance(p, dict):
                continue
            data = parse_dt(p.get("partida_data"))
            if data is None:
                continue
            for key in ("clube_casa_id", "clube_visitante_id"):
                try:
                    clube = int(p.get(key))
                except (TypeError, ValueError):
                    continue
                jogos_por_rodada[rodada][clube] = data

    features = {}
    for rodada in sorted(jogos_por_rodada):
        for clube, data_atual in jogos_por_rodada[rodada].items():
            anteriores = [d for r, d in historico_por_clube[clube] if r < rodada and d < data_atual]
            if anteriores:
                ultimo = max(anteriores)
                dias = max(0.0, (data_atual - ultimo).total_seconds() / 86400.0)
                ultimos14 = sum(1 for d in anteriores if 0 < (data_atual - d).total_seconds() / 86400.0 <= 14)
            else:
                dias = 14.0
                ultimos14 = 0
            features[(rodada, clube)] = {
                "dias_desde_ultimo_brasileirao": float(min(dias, 30.0)),
                "descanso_curto_brasileirao": int(dias <= 4.0),
                "descanso_longo_brasileirao": int(dias >= 7.0),
                "jogos_brasileirao_ultimos14d": int(ultimos14),
            }
        for clube, data in jogos_por_rodada[rodada].items():
            historico_por_clube[clube].append((rodada, data))
    return features


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
        "delta_mae_descanso_menos_base": round(float(np.mean(arr)), 8),
        "ic95": [round(float(np.quantile(sims, .025)), 8), round(float(np.quantile(sims, .975)), 8)],
        "probabilidade_descanso_melhor": round(float(np.mean(sims < 0)), 4),
        "rodadas_ganhas": int(np.sum(arr < 0)),
        "rodadas_perdidas": int(np.sum(arr > 0)),
    }


def main():
    df = pd.read_csv(DATA)
    df = df[df.posicao.isin(POSITIONS)].sort_values(["rodada", "atleta_id"]).reset_index(drop=True)
    missing = [c for c in BASE_FEATURES if c not in df.columns]
    if missing:
        raise SystemExit(f"Dataset sem features base esperadas: {missing}")

    cal = calendario_brasileirao()
    for feature in REST_FEATURES:
        df[feature] = [cal.get((int(r), int(c)), {}).get(feature, 0.0) for r, c in zip(df.rodada, df.clube_id)]

    rows = []
    provas = []
    features_descanso = BASE_FEATURES + REST_FEATURES
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
                    p_rest = predict(model_name, train, test, features_descanso)
                except Exception as exc:
                    provas.append({"rodada": rodada, "posicao": pos, "modelo": model_name, "status": "erro", "erro": str(exc)[:250]})
                    continue
                for idx, (_, row) in enumerate(test.iterrows()):
                    rows.append({
                        "rodada": rodada, "atleta_id": int(row.atleta_id), "posicao": pos,
                        "modelo": model_name, "real": float(row.target_pontos),
                        "p_base": float(p_base[idx]), "p_descanso": float(p_rest[idx]),
                    })
                provas.append({
                    "rodada": rodada, "posicao": pos, "modelo": model_name,
                    "max_train": int(train.rodada.max()), "rodada_prevista": rodada,
                    "status": "ok", "anti_leakage": int(train.rodada.max()) < rodada,
                })
        print(f"R{rodada}: ablation descanso Brasileirão concluído")

    pred = pd.DataFrame(rows)
    if pred.empty:
        raise SystemExit("Sem previsões para ablation de descanso")

    por_modelo = {}
    gates = []
    for model_name, g in pred.groupby("modelo"):
        y = g.real.to_numpy(float)
        mb = metrics(y, g.p_base.to_numpy(float))
        mr = metrics(y, g.p_descanso.to_numpy(float))
        round_deltas = []
        for _, rg in g.groupby("rodada"):
            y_r = rg.real.to_numpy(float)
            round_deltas.append(
                mean_absolute_error(y_r, rg.p_descanso) - mean_absolute_error(y_r, rg.p_base)
            )
        boot = bootstrap_round_delta(round_deltas)
        mae_better = mr["mae"] < mb["mae"]
        rmse_guard = mr["rmse"] <= mb["rmse"] * 1.01
        strong = mae_better and rmse_guard and boot["probabilidade_descanso_melhor"] >= .90
        gates.append(strong)
        por_modelo[model_name] = {
            "n": int(len(g)),
            "base": {k: round(v, 8) for k, v in mb.items()},
            "descanso": {k: round(v, 8) for k, v in mr.items()},
            "delta_mae": round(mr["mae"] - mb["mae"], 8),
            "bootstrap_por_rodada": boot,
            "gate_individual": "APROVADO" if strong else "REPROVADO",
        }

    por_posicao = {}
    for pos, g in pred.groupby("posicao"):
        y = g.real.to_numpy(float)
        mb = metrics(y, g.p_base.to_numpy(float))
        mr = metrics(y, g.p_descanso.to_numpy(float))
        por_posicao[pos] = {
            "n": int(len(g)),
            "mae_base": round(mb["mae"], 8),
            "mae_descanso": round(mr["mae"], 8),
            "delta_mae": round(mr["mae"] - mb["mae"], 8),
        }

    aprovados = int(sum(gates))
    decision = "PROMOVER_DESCANSO_BRASILEIRAO_PARA_TESTE_POR_SCOUT" if aprovados >= 3 else "NAO_PROMOVER_DESCANSO_BRASILEIRAO"
    payload = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "status": "APROVADA",
        "decisao": decision,
        "escopo": "Screening científico de descanso entre jogos do próprio Brasileirão. NÃO representa ainda desgaste de Libertadores, Sul-Americana ou Copa do Brasil.",
        "protocolo": "Ablation walk-forward estrita por rodada e posição. A data da partida de R é tratada como informação pré-rodada; histórico de descanso considera apenas partidas de rodadas < R com data anterior à partida atual. BASE e DESCANSO usam as mesmas linhas e o mesmo modelo.",
        "features_adicionais": REST_FEATURES,
        "modelos_com_gate_aprovado": aprovados,
        "modelos_testados": len(gates),
        "por_modelo": por_modelo,
        "por_posicao": por_posicao,
        "provas_temporais": provas,
        "previsoes": pred.round(8).to_dict(orient="records"),
        "regra_gate": "Promover somente para teste por scout se >=3/4 modelos reduzirem MAE, mantiverem RMSE até +1% e bootstrap por rodada indicar >=90% de probabilidade favorável.",
        "proximo_passo_se_aprovado": "Adicionar calendário externo pré-rodada de Libertadores/Sul-Americana/Copa do Brasil e repetir ablation isolada antes de qualquer integração.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Descanso Brasileirão: {decision} | gates {aprovados}/{len(gates)}")


if __name__ == "__main__":
    main()
