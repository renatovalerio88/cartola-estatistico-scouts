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
CALENDAR = ROOT / "data" / "context" / "calendario-externo-2026.json"
OUT = ROOT / "data" / "reports" / "ablation-calendario-externo.json"
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
EXTERNAL_FEATURES = [
    "dias_desde_ultimo_jogo_externo",
    "jogo_externo_ate3d",
    "jogos_externos_ultimos7d",
    "jogos_externos_ultimos14d",
    "jogos_totais_ultimos7d",
    "jogos_totais_ultimos14d",
    "dias_desde_ultimo_jogo_qualquer",
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
        ts = pd.Timestamp(value)
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        return ts
    except Exception:
        return None


def calendario_brasileirao():
    target_by_round_club = {}
    historical_by_club = defaultdict(list)
    folders = sorted(RAW.glob("rodada-*"), key=lambda p: int(p.name.split("-")[-1]))
    for folder in folders:
        rodada = int(folder.name.split("-")[-1])
        for p in partidas(folder / "partidas.json"):
            if not isinstance(p, dict):
                continue
            dt = parse_dt(p.get("partida_data"))
            if dt is None:
                continue
            for key in ("clube_casa_id", "clube_visitante_id"):
                try:
                    cid = int(p.get(key))
                except (TypeError, ValueError):
                    continue
                target_by_round_club[(rodada, cid)] = dt
                historical_by_club[cid].append((rodada, dt))
    return target_by_round_club, historical_by_club


def external_history():
    if not CALENDAR.exists():
        raise RuntimeError("Snapshot de calendário externo ausente; execute coletar_calendario_externo_2026.py")
    payload = load(CALENDAR)
    by_club = defaultdict(list)
    by_comp = defaultdict(int)
    for event in payload.get("eventos", []):
        dt = parse_dt(event.get("data"))
        if dt is None:
            continue
        comp = str(event.get("competicao") or "desconhecida")
        for cid in event.get("clubes_cartola_ids", []):
            try:
                cid = int(cid)
            except (TypeError, ValueError):
                continue
            by_club[cid].append((dt, comp, str(event.get("evento_id"))))
            by_comp[comp] += 1
    for cid in by_club:
        by_club[cid].sort(key=lambda x: x[0])
    return payload, by_club, dict(by_comp)


def build_features(df):
    target_dates, league_history = calendario_brasileirao()
    calendar_payload, ext_history, ext_counts = external_history()
    records = {}
    evidence = []

    for rodada, cid in sorted({(int(r), int(c)) for r, c in zip(df.rodada, df.clube_id)}):
        target = target_dates.get((rodada, cid))
        if target is None:
            continue
        prior_ext = [(d, comp, eid) for d, comp, eid in ext_history.get(cid, []) if d < target]
        prior_league = [d for r, d in league_history.get(cid, []) if r < rodada and d < target]
        ext_dates = [x[0] for x in prior_ext]
        all_dates = prior_league + ext_dates

        def count_window(values, days):
            return sum(1 for d in values if 0 < (target - d).total_seconds() / 86400.0 <= days)

        if ext_dates:
            days_ext = max(0.0, (target - max(ext_dates)).total_seconds() / 86400.0)
        else:
            days_ext = 30.0
        if all_dates:
            days_any = max(0.0, (target - max(all_dates)).total_seconds() / 86400.0)
        else:
            days_any = 14.0

        records[(rodada, cid)] = {
            "dias_desde_ultimo_jogo_externo": float(min(days_ext, 30.0)),
            "jogo_externo_ate3d": int(days_ext <= 3.0),
            "jogos_externos_ultimos7d": int(count_window(ext_dates, 7)),
            "jogos_externos_ultimos14d": int(count_window(ext_dates, 14)),
            "jogos_totais_ultimos7d": int(count_window(all_dates, 7)),
            "jogos_totais_ultimos14d": int(count_window(all_dates, 14)),
            "dias_desde_ultimo_jogo_qualquer": float(min(days_any, 30.0)),
        }
        evidence.append({
            "rodada": rodada,
            "clube_id": cid,
            "data_alvo": target.isoformat(),
            "eventos_externos_anteriores": len(prior_ext),
            "ultimo_externo": max(ext_dates).isoformat() if ext_dates else None,
            "anti_leakage": all(d < target for d in ext_dates),
        })

    return records, evidence, calendar_payload, ext_counts


def factories():
    return {
        "ridge": lambda: make_pipeline(StandardScaler(), Ridge(alpha=8.0)),
        "extra_trees": lambda: ExtraTreesRegressor(n_estimators=180, min_samples_leaf=6, random_state=42, n_jobs=2),
        "hist_gb": lambda: HistGradientBoostingRegressor(max_iter=110, max_leaf_nodes=14, l2_regularization=2.0, random_state=42),
        "catboost": lambda: CatBoostRegressor(iterations=180, depth=4, learning_rate=.035, loss_function="MAE", l2_leaf_reg=5.0, random_seed=42, verbose=False, thread_count=2, allow_writing_files=False),
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
    sims = np.asarray([float(np.mean(rng.choice(arr, size=len(arr), replace=True))) for _ in range(draws)])
    return {
        "n_rodadas": int(len(arr)),
        "delta_mae_externo_menos_base": round(float(np.mean(arr)), 8),
        "ic95": [round(float(np.quantile(sims, .025)), 8), round(float(np.quantile(sims, .975)), 8)],
        "probabilidade_externo_melhor": round(float(np.mean(sims < 0)), 4),
        "rodadas_ganhas": int(np.sum(arr < 0)),
        "rodadas_perdidas": int(np.sum(arr > 0)),
    }


def main():
    df = pd.read_csv(DATA)
    df = df[df.posicao.isin(POSITIONS)].sort_values(["rodada", "atleta_id"]).reset_index(drop=True)
    missing = [c for c in BASE_FEATURES if c not in df.columns]
    if missing:
        raise SystemExit(f"Dataset sem features base esperadas: {missing}")

    feature_map, date_evidence, calendar_payload, ext_counts = build_features(df)
    for feature in EXTERNAL_FEATURES:
        df[feature] = [feature_map.get((int(r), int(c)), {}).get(feature, 0.0) for r, c in zip(df.rodada, df.clube_id)]

    enriched_rows = int((df.jogos_externos_ultimos14d > 0).sum())
    enriched_clubs = int(df.loc[df.jogos_externos_ultimos14d > 0, "clube_id"].nunique())
    if enriched_rows == 0:
        raise RuntimeError("Calendário externo não gerou nenhuma linha enriquecida; bloquear teste para evitar falso negativo silencioso")

    rows = []
    temporal_proofs = []
    features_external = BASE_FEATURES + EXTERNAL_FEATURES
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
                    p_ext = predict(model_name, train, test, features_external)
                except Exception as exc:
                    temporal_proofs.append({"rodada": rodada, "posicao": pos, "modelo": model_name, "status": "erro", "erro": str(exc)[:250]})
                    continue
                for idx, (_, row) in enumerate(test.iterrows()):
                    rows.append({
                        "rodada": rodada, "atleta_id": int(row.atleta_id), "clube_id": int(row.clube_id),
                        "posicao": pos, "modelo": model_name, "real": float(row.target_pontos),
                        "p_base": float(p_base[idx]), "p_externo": float(p_ext[idx]),
                        "jogos_externos_14d": int(row.jogos_externos_ultimos14d),
                        "jogos_totais_14d": int(row.jogos_totais_ultimos14d),
                    })
                temporal_proofs.append({
                    "rodada": rodada, "posicao": pos, "modelo": model_name,
                    "max_train": int(train.rodada.max()), "rodada_prevista": rodada,
                    "status": "ok", "anti_leakage": int(train.rodada.max()) < rodada,
                })
        print(f"R{rodada}: ablation calendário externo concluído")

    pred = pd.DataFrame(rows)
    if pred.empty:
        raise SystemExit("Sem previsões para ablation de calendário externo")

    por_modelo = {}
    gates = []
    for model_name, g in pred.groupby("modelo"):
        y = g.real.to_numpy(float)
        mb = metrics(y, g.p_base.to_numpy(float))
        me = metrics(y, g.p_externo.to_numpy(float))
        round_deltas = []
        for _, rg in g.groupby("rodada"):
            round_deltas.append(mean_absolute_error(rg.real, rg.p_externo) - mean_absolute_error(rg.real, rg.p_base))
        boot = bootstrap_round_delta(round_deltas)
        mae_better = me["mae"] < mb["mae"]
        rmse_guard = me["rmse"] <= mb["rmse"] * 1.01
        strong = mae_better and rmse_guard and boot["probabilidade_externo_melhor"] >= .90
        gates.append(strong)
        por_modelo[model_name] = {
            "n": int(len(g)),
            "base": {k: round(v, 8) for k, v in mb.items()},
            "calendario_externo": {k: round(v, 8) for k, v in me.items()},
            "delta_mae": round(me["mae"] - mb["mae"], 8),
            "bootstrap_por_rodada": boot,
            "gate_individual": "APROVADO" if strong else "REPROVADO",
        }

    por_posicao = {}
    for pos, g in pred.groupby("posicao"):
        y = g.real.to_numpy(float)
        mb = metrics(y, g.p_base.to_numpy(float))
        me = metrics(y, g.p_externo.to_numpy(float))
        por_posicao[pos] = {
            "n": int(len(g)),
            "mae_base": round(mb["mae"], 8),
            "mae_calendario_externo": round(me["mae"], 8),
            "delta_mae": round(me["mae"] - mb["mae"], 8),
        }

    aprovados = int(sum(gates))
    decision = "PROMOVER_CALENDARIO_EXTERNO_PARA_TESTE_POR_SCOUT" if aprovados >= 3 else "NAO_PROMOVER_CALENDARIO_EXTERNO"
    payload = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "status": "APROVADA",
        "decisao": decision,
        "escopo": "Ablation isolada do congestionamento causado por Libertadores, Sul-Americana e Copa do Brasil, sem promover a ablation reprovada de descanso do Brasileirão.",
        "protocolo": "Walk-forward estrito por rodada e posição. Para uma partida-alvo, somente jogos externos concluídos com data estritamente anterior à partida são usados; nenhum placar externo é feature. BASE e EXTERNO usam as mesmas linhas/modelos.",
        "fonte_calendario": calendar_payload.get("fonte"),
        "janela_calendario": calendar_payload.get("janela_coletada"),
        "resumo_calendario": calendar_payload.get("resumo"),
        "contagens_clube_evento": ext_counts,
        "linhas_dataset_com_externo_14d": enriched_rows,
        "clubes_com_externo_14d": enriched_clubs,
        "features_adicionais": EXTERNAL_FEATURES,
        "modelos_com_gate_aprovado": aprovados,
        "modelos_testados": len(gates),
        "por_modelo": por_modelo,
        "por_posicao": por_posicao,
        "provas_temporais_modelos": temporal_proofs,
        "provas_temporais_calendario": date_evidence,
        "previsoes": pred.round(8).to_dict(orient="records"),
        "regra_gate": "Promover somente para teste por scout se >=3/4 modelos reduzirem MAE, mantiverem RMSE até +1% e bootstrap por rodada indicar >=90% de probabilidade favorável.",
        "observacao": "Resultado deste screening não autoriza integração no modelo final nem qualquer alteração na V2.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Calendário externo: {decision} | gates {aprovados}/{len(gates)} | linhas expostas 14d={enriched_rows}")


if __name__ == "__main__":
    main()
