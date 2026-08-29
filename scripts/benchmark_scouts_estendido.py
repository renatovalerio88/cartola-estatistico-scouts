#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "derived" / "dataset-walk-forward.csv"
CORE = ROOT / "data" / "reports" / "campeonato-modelos.json"
OUT = ROOT / "data" / "reports" / "campeonato-modelos-estendido.json"
SCOUTS = ["G","A","FT","FD","FF","FS","PS","I","DS","SG","DP","DE","GC","CV","CA","GS","FC","PC","PP"]
POSITIONS = ["GOL","LAT","ZAG","MEI","ATA"]
MIN_ROWS = 80


def feature_cols(s):
    return [
        "historico_jogos","mando","pontos_media3","pontos_media5","pontos_ewma",
        f"{s}_media3",f"{s}_media5",f"{s}_ewma",
        "time_jogos","time_gf_media5","time_ga_media5","time_gf_ewma","time_ga_ewma",
        "adversario_jogos","adversario_gf_media5","adversario_ga_media5","adversario_gf_ewma","adversario_ga_ewma",
    ]


def temporal_folds(rounds):
    rounds = sorted(int(r) for r in set(rounds))
    candidates = [r for r in rounds if r >= 7]
    if len(candidates) <= 4:
        return [(r, [r]) for r in candidates]
    idx = np.linspace(0, len(candidates) - 1, 4, dtype=int)
    starts = sorted(set(candidates[i] for i in idx))
    folds = []
    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else max(candidates) + 1
        folds.append((start, [r for r in candidates if start <= r < end]))
    return folds


def factories():
    available = {}
    errors = {}
    try:
        from xgboost import XGBRegressor
        available["xgboost"] = lambda: XGBRegressor(
            n_estimators=120,
            max_depth=3,
            learning_rate=0.035,
            subsample=0.85,
            colsample_bytree=0.85,
            reg_alpha=0.05,
            reg_lambda=1.5,
            objective="reg:squarederror",
            random_state=42,
            n_jobs=2,
        )
    except Exception as exc:
        errors["xgboost"] = repr(exc)
    try:
        from lightgbm import LGBMRegressor
        available["lightgbm"] = lambda: LGBMRegressor(
            n_estimators=120,
            max_depth=4,
            num_leaves=15,
            learning_rate=0.035,
            subsample=0.85,
            colsample_bytree=0.85,
            reg_alpha=0.05,
            reg_lambda=1.5,
            random_state=42,
            n_jobs=2,
            verbosity=-1,
        )
    except Exception as exc:
        errors["lightgbm"] = repr(exc)
    try:
        from catboost import CatBoostRegressor
        available["catboost"] = lambda: CatBoostRegressor(
            iterations=120,
            depth=4,
            learning_rate=0.035,
            loss_function="MAE",
            l2_leaf_reg=4.0,
            random_seed=42,
            verbose=False,
            thread_count=2,
        )
    except Exception as exc:
        errors["catboost"] = repr(exc)
    return available, errors


def metric(actual, pred):
    actual = np.asarray(actual, float)
    pred = np.asarray(pred, float)
    return {
        "mae": round(float(mean_absolute_error(actual, pred)), 6),
        "rmse": round(float(mean_squared_error(actual, pred) ** .5), 6),
        "bias": round(float(np.mean(pred - actual)), 6),
        "n": int(len(actual)),
    }


def evaluate(df, scout, pos, factory):
    sub = df[df.posicao.eq(pos)].copy()
    ycol = f"target_{scout}"
    feats = feature_cols(scout)
    if ycol not in sub.columns or len(sub) < MIN_ROWS:
        return None
    actuals, preds, rounds_used, proofs = [], [], [], []
    for start, test_rounds in temporal_folds(sub.rodada.unique()):
        train = sub[sub.rodada < start]
        test = sub[sub.rodada.isin(test_rounds)]
        if len(train) < MIN_ROWS or test.empty:
            continue
        max_train = int(train.rodada.max())
        min_test = int(test.rodada.min())
        if max_train >= min_test:
            raise RuntimeError(f"vazamento temporal em {scout}/{pos}: treino {max_train}, teste {min_test}")
        Xtr = train[feats].fillna(0).to_numpy(float)
        ytr = train[ycol].fillna(0).to_numpy(float)
        Xte = test[feats].fillna(0).to_numpy(float)
        yte = test[ycol].fillna(0).to_numpy(float)
        if float(np.sum(np.abs(ytr))) == 0:
            pred = np.zeros(len(test))
        else:
            model = factory()
            model.fit(Xtr, ytr)
            pred = np.asarray(model.predict(Xte), float)
            pred = np.nan_to_num(pred, nan=0.0, posinf=0.0, neginf=0.0)
            pred = np.clip(pred, 0, None)
        actuals.extend(yte)
        preds.extend(pred)
        rounds_used.extend(test.rodada.astype(int).tolist())
        proofs.append({"max_rodada_treino": max_train, "min_rodada_teste": min_test, "ok": True})
    if not actuals:
        return None
    return {
        "metricas": metric(actuals, preds),
        "rodadas_teste": sorted(set(rounds_used)),
        "prova_temporal": proofs,
    }


def core_index():
    if not CORE.exists():
        return {}
    raw = json.loads(CORE.read_text(encoding="utf-8"))
    idx = {}
    for r in raw.get("resultados", []):
        ranking = r.get("ranking") or []
        metrics = r.get("metricas") or {}
        if not ranking:
            continue
        winner = ranking[0]
        idx[(r.get("scout"), r.get("posicao"))] = {
            "modelo": winner,
            "mae": metrics.get(winner, {}).get("mae"),
        }
    return idx


def main():
    df = pd.read_csv(DATA)
    df = df[df.posicao.isin(POSITIONS)].copy()
    factories_map, import_errors = factories()
    if not factories_map:
        raise SystemExit(f"Nenhum challenger pesado disponível: {import_errors}")
    core = core_index()
    results = []
    wins_heavy = {name: 0 for name in factories_map}
    heavy_beats_core = {name: 0 for name in factories_map}
    failures = {name: 0 for name in factories_map}

    for scout in SCOUTS:
        for pos in POSITIONS:
            key = (scout, pos)
            per_model = {}
            for name, factory in factories_map.items():
                try:
                    r = evaluate(df, scout, pos, factory)
                    if r:
                        per_model[name] = r
                except Exception as exc:
                    failures[name] += 1
                    per_model[name] = {"erro": repr(exc)}
            valid = {n: r for n, r in per_model.items() if "metricas" in r}
            if not valid:
                continue
            heavy_winner = min(valid, key=lambda n: (valid[n]["metricas"]["mae"], n))
            wins_heavy[heavy_winner] += 1
            core_best = core.get(key)
            if core_best and core_best.get("mae") is not None:
                for name, r in valid.items():
                    if r["metricas"]["mae"] < float(core_best["mae"]):
                        heavy_beats_core[name] += 1
            all_candidates = []
            if core_best and core_best.get("mae") is not None:
                all_candidates.append((core_best["modelo"], float(core_best["mae"]), "core"))
            all_candidates.extend((name, r["metricas"]["mae"], "heavy") for name, r in valid.items())
            champion = min(all_candidates, key=lambda x: (x[1], x[0])) if all_candidates else None
            results.append({
                "scout": scout,
                "posicao": pos,
                "core_melhor": core_best,
                "pesados": per_model,
                "vencedor_pesado": heavy_winner,
                "campeao_geral": {"modelo": champion[0], "mae": champion[1], "familia": champion[2]} if champion else None,
            })
            print(f"{scout}/{pos}: pesado={heavy_winner} MAE={valid[heavy_winner]['metricas']['mae']} | geral={champion}")

    geral_heavy = {}
    for name in factories_map:
        vals = [
            r["pesados"][name]["metricas"]["mae"]
            for r in results
            if name in r["pesados"] and "metricas" in r["pesados"][name]
        ]
        geral_heavy[name] = {
            "competicoes": len(vals),
            "mae_medio_competicoes": round(float(np.mean(vals)), 6) if vals else None,
            "vitorias_entre_pesados": wins_heavy[name],
            "vezes_superou_campeao_core": heavy_beats_core[name],
            "falhas": failures[name],
        }

    payload = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "protocolo": "campeonato estendido walk-forward; cada fold treina exclusivamente em rodadas anteriores; challengers pesados ficam fora do pipeline diário para preservar estabilidade",
        "modelos_disponiveis": list(factories_map),
        "erros_importacao": import_errors,
        "resumo_modelos": geral_heavy,
        "competicoes_validas": len(results),
        "resultados": results,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Campeonato estendido concluído:", geral_heavy)


if __name__ == "__main__":
    main()
