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


def main():
    bt = load(BACKTEST)
    v3 = pd.DataFrame(bt.get("previsoes", []))
    if v3.empty:
        raise SystemExit("Backtest V3 vazio")
    required = {"rodada", "atleta_id", "real", "v3s_nested", "v3h_hibrido", "direta_rf_lab", "direta_ewma"}
    missing = required - set(v3.columns)
    if missing:
        raise SystemExit(f"Colunas ausentes no backtest V3: {sorted(missing)}")
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
    global_metrics = {
        name: {
            "mae": round(mae(consistent.real, consistent[name]), 6),
            "n": int(len(consistent)),
        }
        for name in architectures
    }
    by_position = {}
    if "posicao" in consistent.columns:
        for pos, g in consistent.groupby("posicao"):
            by_position[str(pos)] = {
                name: {"mae": round(mae(g.real, g[name]), 6), "n": int(len(g))}
                for name in architectures
            }
    by_round = {}
    for rodada, g in consistent.groupby("rodada"):
        by_round[str(int(rodada))] = {
            "n": int(len(g)),
            "mae": {name: round(mae(g.real, g[name]), 6) for name in architectures},
        }

    comparisons = {
        "v3s_vs_v2": bootstrap_rounds(consistent, "v3s_nested", "v2_projecao_salva"),
        "v3h_vs_v2": bootstrap_rounds(consistent, "v3h_hibrido", "v2_projecao_salva"),
        "rf_lab_vs_v2": bootstrap_rounds(consistent, "direta_rf_lab", "v2_projecao_salva"),
    }

    payload = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "protocolo": (
            "comparação somente leitura: usa as projeções historicamente salvas pela V2 em data/historico/rodada-XX.json, "
            "alinha por rodada+atleta_id com previsões OOS nested da V3; remove linhas cujo resultado real difere entre as fontes; "
            "bootstrap em blocos por rodada, sem recalibrar a V2 olhando o futuro"
        ),
        "rotulo_v2": "V2 projeção histórica salva (produção)",
        "nota": (
            "Esta é a comparação mais fiel disponível porque usa o valor de projeção efetivamente arquivado pela V2 para cada rodada, "
            "em vez de substituir a V2 pelo RF direto do laboratório."
        ),
        "rodadas_v3": rounds,
        "rodadas_v2_ausentes": missing_rounds,
        "linhas_v3": int(len(v3)),
        "linhas_v2": int(len(v2)),
        "linhas_comuns": int(len(merged)),
        "linhas_consistentes": int(len(consistent)),
        "linhas_descartadas_real_divergente": int(len(inconsistent)),
        "rodadas_comuns": sorted(consistent.rodada.astype(int).unique().tolist()),
        "geral": global_metrics,
        "por_posicao": by_position,
        "por_rodada": by_round,
        "comparacoes_bootstrap": comparisons,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Comparação V2 oficial salva x V3:", global_metrics)
    print("Linhas comuns consistentes:", len(consistent), "descartadas:", len(inconsistent))
    print("Bootstrap:", comparisons)


if __name__ == "__main__":
    main()
