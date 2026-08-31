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
CONTEXT = ROOT / "data" / "context" / "mudancas-tecnicos-2026.json"
OUT = ROOT / "data" / "reports" / "ablation-mudanca-tecnico.json"
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
COACH_FEATURES = [
    "dias_desde_mudanca_tecnico",
    "tecnico_novo_7d",
    "tecnico_novo_14d",
    "tecnico_novo_30d",
    "mudancas_tecnico_90d",
    "tecnico_interino",
]


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def partidas(path: Path):
    if not path.exists():
        return []
    raw = load(path)
    return raw.get("partidas", raw if isinstance(raw, list) else [])


def parse_date(value):
    if not value:
        return None
    try:
        return pd.Timestamp(value).date()
    except Exception:
        return None


def siglas_por_clube_id():
    mapping = {}
    for folder in sorted(RAW.glob("rodada-*")):
        path = folder / "jogadores.json"
        if not path.exists():
            continue
        raw = load(path)
        atletas = raw if isinstance(raw, list) else raw.get("atletas", raw.get("jogadores", []))
        for a in atletas:
            try:
                cid = int(a.get("clubeId", a.get("clube_id")))
            except (TypeError, ValueError):
                continue
            sigla = str(a.get("siglaClube", a.get("clube", ""))).upper().strip()
            if cid and sigla:
                mapping[cid] = sigla
    return mapping


def datas_partidas_por_rodada_clube():
    dates = {}
    for folder in sorted(RAW.glob("rodada-*"), key=lambda p: int(p.name.split("-")[-1])):
        rodada = int(folder.name.split("-")[-1])
        for p in partidas(folder / "partidas.json"):
            if not isinstance(p, dict):
                continue
            data = parse_date(p.get("partida_data"))
            if data is None:
                continue
            for key in ("clube_casa_id", "clube_visitante_id"):
                try:
                    cid = int(p.get(key))
                except (TypeError, ValueError):
                    continue
                dates[(rodada, cid)] = data
    return dates


def contexto_tecnicos():
    payload = load(CONTEXT)
    if int(payload.get("temporada", 0)) != 2026:
        raise RuntimeError("Snapshot de técnicos não é da temporada 2026")
    eventos = []
    for e in payload.get("eventos", []):
        dt = parse_date(e.get("data_efetiva"))
        sigla = str(e.get("clube", "")).upper().strip()
        if dt is None or not sigla:
            continue
        eventos.append({**e, "_data": dt, "_sigla": sigla})
    if len(eventos) < 10:
        raise RuntimeError("Cobertura insuficiente do snapshot de mudanças de técnicos")
    return payload, eventos


def construir_features():
    payload, eventos = contexto_tecnicos()
    siglas = siglas_por_clube_id()
    target_dates = datas_partidas_por_rodada_clube()
    by_club = defaultdict(list)
    for e in eventos:
        by_club[e["_sigla"]].append(e)
    for sigla in by_club:
        by_club[sigla].sort(key=lambda x: x["_data"])

    features = {}
    provas = []
    for (rodada, cid), target_date in sorted(target_dates.items()):
        sigla = siglas.get(cid, "")
        # Conservador: evento no mesmo dia NÃO conta. Assim a feature nunca depende
        # de descobrir se o anúncio ocorreu antes ou depois do fechamento/partida.
        conhecidos = [e for e in by_club.get(sigla, []) if e["_data"] < target_date]
        if conhecidos:
            ultimo = conhecidos[-1]
            dias = (target_date - ultimo["_data"]).days
            ult90 = sum(1 for e in conhecidos if 0 < (target_date - e["_data"]).days <= 90)
            feat = {
                "dias_desde_mudanca_tecnico": float(min(max(dias, 0), 180)),
                "tecnico_novo_7d": int(dias <= 7),
                "tecnico_novo_14d": int(dias <= 14),
                "tecnico_novo_30d": int(dias <= 30),
                "mudancas_tecnico_90d": int(ult90),
                "tecnico_interino": int(bool(ultimo.get("interino", False))),
            }
            provas.append({
                "rodada": rodada, "clube_id": cid, "clube": sigla,
                "data_partida": str(target_date), "ultimo_evento": str(ultimo["_data"]),
                "anti_leakage": ultimo["_data"] < target_date,
            })
        else:
            feat = {
                "dias_desde_mudanca_tecnico": 180.0,
                "tecnico_novo_7d": 0,
                "tecnico_novo_14d": 0,
                "tecnico_novo_30d": 0,
                "mudancas_tecnico_90d": 0,
                "tecnico_interino": 0,
            }
        features[(rodada, cid)] = feat
    return payload, features, provas


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
        "delta_mae_tecnico_menos_base": round(float(np.mean(arr)), 8),
        "ic95": [round(float(np.quantile(sims, .025)), 8), round(float(np.quantile(sims, .975)), 8)],
        "probabilidade_tecnico_melhor": round(float(np.mean(sims < 0)), 4),
        "rodadas_ganhas": int(np.sum(arr < 0)),
        "rodadas_perdidas": int(np.sum(arr > 0)),
    }


def main():
    df = pd.read_csv(DATA)
    df = df[df.posicao.isin(POSITIONS)].sort_values(["rodada", "atleta_id"]).reset_index(drop=True)
    missing = [c for c in BASE_FEATURES if c not in df.columns]
    if missing:
        raise SystemExit(f"Dataset sem features base esperadas: {missing}")

    snapshot, coach_ctx, temporal_proofs = construir_features()
    for feature in COACH_FEATURES:
        df[feature] = [coach_ctx.get((int(r), int(c)), {}).get(feature, 0.0) for r, c in zip(df.rodada, df.clube_id)]

    rows = []
    provas = []
    features_coach = BASE_FEATURES + COACH_FEATURES
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
                    p_coach = predict(model_name, train, test, features_coach)
                except Exception as exc:
                    provas.append({"rodada": rodada, "posicao": pos, "modelo": model_name, "status": "erro", "erro": str(exc)[:250]})
                    continue
                for idx, (_, row) in enumerate(test.iterrows()):
                    rows.append({
                        "rodada": rodada, "atleta_id": int(row.atleta_id), "posicao": pos,
                        "modelo": model_name, "real": float(row.target_pontos),
                        "p_base": float(p_base[idx]), "p_tecnico": float(p_coach[idx]),
                    })
                provas.append({
                    "rodada": rodada, "posicao": pos, "modelo": model_name,
                    "max_train": int(train.rodada.max()), "rodada_prevista": rodada,
                    "status": "ok", "anti_leakage": int(train.rodada.max()) < rodada,
                })
        print(f"R{rodada}: ablation mudança de técnico concluída")

    pred = pd.DataFrame(rows)
    if pred.empty:
        raise SystemExit("Sem previsões para ablation de mudança de técnico")

    por_modelo = {}
    gates = []
    for model_name, g in pred.groupby("modelo"):
        y = g.real.to_numpy(float)
        mb = metrics(y, g.p_base.to_numpy(float))
        mt = metrics(y, g.p_tecnico.to_numpy(float))
        round_deltas = []
        for _, rg in g.groupby("rodada"):
            round_deltas.append(
                mean_absolute_error(rg.real, rg.p_tecnico) - mean_absolute_error(rg.real, rg.p_base)
            )
        boot = bootstrap_round_delta(round_deltas)
        mae_better = mt["mae"] < mb["mae"]
        rmse_guard = mt["rmse"] <= mb["rmse"] * 1.01
        strong = mae_better and rmse_guard and boot["probabilidade_tecnico_melhor"] >= .90
        gates.append(strong)
        por_modelo[model_name] = {
            "n": int(len(g)),
            "base": {k: round(v, 8) for k, v in mb.items()},
            "mudanca_tecnico": {k: round(v, 8) for k, v in mt.items()},
            "delta_mae": round(mt["mae"] - mb["mae"], 8),
            "bootstrap_por_rodada": boot,
            "gate_individual": "APROVADO" if strong else "REPROVADO",
        }

    por_posicao = {}
    for pos, g in pred.groupby("posicao"):
        mb = metrics(g.real.to_numpy(float), g.p_base.to_numpy(float))
        mt = metrics(g.real.to_numpy(float), g.p_tecnico.to_numpy(float))
        por_posicao[pos] = {
            "n": int(len(g)),
            "mae_base": round(mb["mae"], 8),
            "mae_mudanca_tecnico": round(mt["mae"], 8),
            "delta_mae": round(mt["mae"] - mb["mae"], 8),
        }

    aprovados = int(sum(gates))
    decision = "PROMOVER_MUDANCA_TECNICO_PARA_TESTE_POR_SCOUT" if aprovados >= 3 else "NAO_PROMOVER_MUDANCA_TECNICO"
    payload = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "status": "APROVADA",
        "decisao": decision,
        "escopo": "Screening científico isolado do efeito de mudança de técnico durante o Brasileirão 2026.",
        "protocolo": "Ablation walk-forward estrita por rodada e posição. Evento de técnico entra somente quando sua data efetiva é anterior à data da partida-alvo; mudanças no mesmo dia são ignoradas. BASE e TÉCNICO usam as mesmas linhas, o mesmo alvo e o mesmo modelo.",
        "snapshot": {
            "eventos": len(snapshot.get("eventos", [])),
            "fontes": snapshot.get("fontes", []),
            "criterio_temporal": snapshot.get("criterio_temporal"),
        },
        "features_adicionais": COACH_FEATURES,
        "modelos_com_gate_aprovado": aprovados,
        "modelos_testados": len(gates),
        "por_modelo": por_modelo,
        "por_posicao": por_posicao,
        "provas_contexto_temporal": temporal_proofs,
        "provas_walk_forward": provas,
        "previsoes": pred.round(8).to_dict(orient="records"),
        "regra_gate": "Promover somente para teste por scout se >=3/4 modelos reduzirem MAE, mantiverem RMSE até +1% e bootstrap por rodada indicar >=90% de probabilidade favorável.",
        "proximo_passo_se_aprovado": "Testar o sinal por scout/posição antes de qualquer integração na arquitetura V3.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Mudança de técnico: {decision} | gates {aprovados}/{len(gates)}")


if __name__ == "__main__":
    main()
