#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
BACKTEST = ROOT / "data" / "reports" / "backtest-v3s-nested.json"
CATBOOST = ROOT / "data" / "reports" / "backtest-v3s-catboost-nested.json"
DOIS_ESTAGIOS = ROOT / "data" / "reports" / "backtest-v3s-dois-estagios.json"
OUT = ROOT / "data" / "reports" / "comparacao-v2-oficial-v3.json"
V2_RAW = "https://raw.githubusercontent.com/renatovalerio88/cartola-estatistico/main/data/historico/rodada-{rodada:02d}.json"
BOOTSTRAPS = 5000
SEED = 42


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def fetch_v2_round(rodada: int):
    url = V2_RAW.format(rodada=rodada)
    response = requests.get(url, timeout=30)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    payload = response.json()
    jogadores = payload.get("jogadores") or []
    rows = []
    for j in jogadores:
        if not isinstance(j, dict):
            continue
        aid = j.get("id")
        pred = j.get("projecao")
        real = j.get("real")
        if aid is None or pred is None or real is None:
            continue
        try:
            rows.append(
                {
                    "rodada": rodada,
                    "atleta_id": int(aid),
                    "v2_projecao_salva": float(pred),
                    "v2_real_salvo": float(real),
                    "v2_posicao": str(j.get("posicao") or "").upper(),
                }
            )
        except (TypeError, ValueError):
            continue
    return rows


def mae(y, p):
    return float(np.mean(np.abs(np.asarray(p, float) - np.asarray(y, float))))


def bootstrap_rounds(df: pd.DataFrame, challenger: str, baseline: str):
    rounds = sorted(df.rodada.unique())
    per_round = {}
    for r in rounds:
        g = df[df.rodada.eq(r)]
        per_round[int(r)] = mae(g.real, g[challenger]) - mae(g.real, g[baseline])
    values = np.array([per_round[int(r)] for r in rounds], float)
    rng = np.random.default_rng(SEED)
    boots = []
    for _ in range(BOOTSTRAPS):
        sample = rng.choice(values, size=len(values), replace=True)
        boots.append(float(np.mean(sample)))
    boots = np.asarray(boots)
    point = float(np.mean(values))
    lo, hi = np.quantile(boots, [0.025, 0.975])
    prob_better = float(np.mean(boots < 0))
    wins = int(np.sum(values < 0))
    losses = int(np.sum(values > 0))
    ties = int(np.sum(np.isclose(values, 0)))
    if hi < 0:
        evidence = "evidencia_forte_a_melhor"
    elif lo > 0:
        evidence = "evidencia_forte_a_pior"
    else:
        evidence = "inconclusivo"
    return {
        "diferenca_mae_desafiante_menos_base": round(point, 6),
        "ic95": [round(float(lo), 6), round(float(hi), 6)],
        "probabilidade_bootstrap_desafiante_melhor": round(prob_better, 4),
        "rodadas_ganhas": wins,
        "rodadas_perdidas": losses,
        "empates": ties,
        "evidencia": evidence,
        "por_rodada": {str(k): round(v, 6) for k, v in per_round.items()},
    }


def merge_optional_predictions(base: pd.DataFrame, path: Path, prediction_col: str) -> tuple[pd.DataFrame, dict]:
    status = {
        "arquivo": str(path.relative_to(ROOT)),
        "coluna": prediction_col,
        "disponivel": False,
        "linhas_arquivo": 0,
        "linhas_casadas": 0,
    }
    if not path.exists():
        return base, status
    payload = load(path)
    extra = pd.DataFrame(payload.get("previsoes", []))
    if extra.empty or prediction_col not in extra.columns:
        return base, status
    needed = ["rodada", "atleta_id", prediction_col]
    extra = extra[needed].dropna(subset=needed).copy()
    extra["rodada"] = extra["rodada"].astype(int)
    extra["atleta_id"] = extra["atleta_id"].astype(int)
    extra = extra.drop_duplicates(["rodada", "atleta_id"], keep="last")
    status["disponivel"] = True
    status["linhas_arquivo"] = int(len(extra))
    merged = base.merge(extra, on=["rodada", "atleta_id"], how="left", validate="one_to_one")
    status["linhas_casadas"] = int(merged[prediction_col].notna().sum())
    return merged, status


def main():
    bt = load(BACKTEST)
    v3 = pd.DataFrame(bt.get("previsoes", []))
    if v3.empty:
        raise SystemExit("Backtest V3 vazio")
    required = {"rodada", "atleta_id", "real", "v3s_nested", "v3h_hibrido", "direta_rf_lab", "direta_ewma"}
    missing = required - set(v3.columns)
    if missing:
        raise SystemExit(f"Colunas ausentes no backtest V3: {sorted(missing)}")

    v3["rodada"] = v3["rodada"].astype(int)
    v3["atleta_id"] = v3["atleta_id"].astype(int)
    v3, status_cat = merge_optional_predictions(v3, CATBOOST, "v3s_catboost_nested")
    v3, status_dois = merge_optional_predictions(v3, DOIS_ESTAGIOS, "v3s_dois_estagios")

    rounds = sorted(int(r) for r in v3.rodada.unique())
    v2_rows = []
    missing_rounds = []
    for rodada in rounds:
        rows = fetch_v2_round(rodada)
        if rows is None:
            missing_rounds.append(rodada)
        else:
            v2_rows.extend(rows)
    v2 = pd.DataFrame(v2_rows)
    if v2.empty:
        raise SystemExit("Nenhuma projeção histórica da V2 encontrada")

    merged = v3.merge(v2, on=["rodada", "atleta_id"], how="inner")
    if merged.empty:
        raise SystemExit("Sem linhas comuns V2/V3")
    merged["real_diff_v2_v3"] = np.abs(merged.real - merged.v2_real_salvo)
    consistent = merged[merged.real_diff_v2_v3 <= 1e-6].copy()
    inconsistent = merged[merged.real_diff_v2_v3 > 1e-6].copy()
    if consistent.empty:
        raise SystemExit("Nenhuma linha comum com resultado real consistente entre V2 e V3")

    architectures = ["v2_projecao_salva", "v3s_nested", "v3h_hibrido", "direta_rf_lab", "direta_ewma"]
    for optional in ["v3s_catboost_nested", "v3s_dois_estagios"]:
        if optional in consistent.columns and consistent[optional].notna().any():
            architectures.append(optional)

    global_metrics = {}
    for name in architectures:
        g = consistent.dropna(subset=[name])
        if not g.empty:
            global_metrics[name] = {"mae": round(mae(g.real, g[name]), 6), "n": int(len(g))}

    by_position = {}
    if "posicao" in consistent.columns:
        for pos, pos_df in consistent.groupby("posicao"):
            metrics = {}
            for name in architectures:
                g = pos_df.dropna(subset=[name])
                if not g.empty:
                    metrics[name] = {"mae": round(mae(g.real, g[name]), 6), "n": int(len(g))}
            by_position[str(pos)] = metrics

    by_round = {}
    for rodada, round_df in consistent.groupby("rodada"):
        metrics = {}
        for name in architectures:
            g = round_df.dropna(subset=[name])
            if not g.empty:
                metrics[name] = round(mae(g.real, g[name]), 6)
        by_round[str(int(rodada))] = {"n": int(len(round_df)), "mae": metrics}

    comparisons = {
        "v3s_vs_v2": bootstrap_rounds(consistent, "v3s_nested", "v2_projecao_salva"),
        "v3h_vs_v2": bootstrap_rounds(consistent, "v3h_hibrido", "v2_projecao_salva"),
        "rf_lab_vs_v2": bootstrap_rounds(consistent, "direta_rf_lab", "v2_projecao_salva"),
    }

    optional_pairs = [
        ("catboost_nested_vs_v2", "v3s_catboost_nested"),
        ("dois_estagios_vs_v2", "v3s_dois_estagios"),
    ]
    comparison_samples = {}
    for label, col in optional_pairs:
        if col not in consistent.columns:
            continue
        pair = consistent.dropna(subset=[col, "v2_projecao_salva"]).copy()
        if pair.empty:
            continue
        common_rounds = sorted(int(r) for r in pair.rodada.unique())
        comparisons[label] = bootstrap_rounds(pair, col, "v2_projecao_salva")
        comparison_samples[label] = {
            "linhas": int(len(pair)),
            "rodadas": common_rounds,
            "mae_v2": round(mae(pair.real, pair.v2_projecao_salva), 6),
            "mae_desafiante": round(mae(pair.real, pair[col]), 6),
        }

    payload = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "protocolo": (
            "comparação somente leitura: usa as projeções historicamente salvas pela V2 em data/historico/rodada-XX.json, "
            "alinha por rodada+atleta_id com previsões OOS nested da V3; remove linhas cujo resultado real difere entre as fontes; "
            "CatBoost nested e dois estágios entram somente quando possuem previsão OOS para a mesma chave; bootstrap em blocos por rodada, "
            "sem recalibrar a V2 nem qualquer desafiante olhando a rodada avaliada"
        ),
        "rotulo_v2": "V2 projeção histórica salva (produção)",
        "nota": (
            "Esta é a comparação mais fiel disponível porque usa o valor de projeção efetivamente arquivado pela V2 para cada rodada. "
            "As comparações opcionais registram explicitamente sua própria interseção pareada para evitar falsa equivalência de amostras."
        ),
        "fontes_opcionais": {
            "catboost_nested": status_cat,
            "dois_estagios": status_dois,
        },
        "rodadas_v3": rounds,
        "rodadas_v2_ausentes": missing_rounds,
        "linhas_v3": int(len(v3)),
        "linhas_v2": int(len(v2)),
        "linhas_comuns": int(len(merged)),
        "linhas_consistentes": int(len(consistent)),
        "linhas_descartadas_real_divergente": int(len(inconsistent)),
        "rodadas_comuns": sorted(consistent.rodada.astype(int).unique().tolist()),
        "amostras_comparacoes_opcionais": comparison_samples,
        "geral": global_metrics,
        "por_posicao": by_position,
        "por_rodada": by_round,
        "comparacoes_bootstrap": comparisons,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Comparação V2 oficial salva x V3:", global_metrics)
    print("Linhas comuns consistentes:", len(consistent), "descartadas:", len(inconsistent))
    print("Amostras opcionais:", comparison_samples)
    print("Bootstrap:", comparisons)


if __name__ == "__main__":
    main()
