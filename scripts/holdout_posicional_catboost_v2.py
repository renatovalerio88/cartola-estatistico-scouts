#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
ABLATION = ROOT / "data" / "reports" / "ablation-catboost-contexto-nested.json"
OUT = ROOT / "data" / "reports" / "holdout-posicional-catboost-v2.json"
V2_RAW = "https://raw.githubusercontent.com/renatovalerio88/cartola-estatistico/main/data/historico/rodada-{rodada:02d}.json"
DISCOVERY_END = 17
HOLDOUT_START = 18
BOOTSTRAPS = 10000
SEED = 20260830


def metric(y, p) -> dict:
    y = np.asarray(y, dtype=float)
    p = np.asarray(p, dtype=float)
    e = p - y
    return {
        "n": int(len(y)),
        "mae": round(float(np.mean(np.abs(e))), 6),
        "rmse": round(float(np.sqrt(np.mean(e ** 2))), 6),
        "bias": round(float(np.mean(e)), 6),
    }


def fetch_v2_round(rodada: int) -> list[dict]:
    """Lê somente a saída histórica já publicada pela V2.

    A V3 pode ter uma rodada nova antes de a V2 fechar/publicar o histórico correspondente.
    Nesse caso (404), a rodada é simplesmente excluída da comparação pareada. Isso evita
    quebrar o laboratório e, principalmente, impede comparar universos temporais diferentes.
    """
    r = requests.get(V2_RAW.format(rodada=rodada), timeout=30)
    if r.status_code == 404:
        return []
    r.raise_for_status()
    rows = []
    for j in r.json().get("jogadores") or []:
        if not isinstance(j, dict):
            continue
        try:
            if j.get("id") is None or j.get("projecao") is None or j.get("real") is None:
                continue
            rows.append({
                "rodada": int(rodada),
                "atleta_id": int(j["id"]),
                "v2": float(j["projecao"]),
                "v2_real": float(j["real"]),
            })
        except (TypeError, ValueError):
            continue
    return rows


def bootstrap_rounds(df: pd.DataFrame, pred_col: str, base_col: str = "v2") -> dict:
    deltas = []
    por_rodada = {}
    for rodada, g in df.groupby("rodada"):
        delta = float(
            np.mean(np.abs(g[pred_col].to_numpy(float) - g.real.to_numpy(float)))
            - np.mean(np.abs(g[base_col].to_numpy(float) - g.real.to_numpy(float)))
        )
        deltas.append(delta)
        por_rodada[str(int(rodada))] = round(delta, 6)
    arr = np.asarray(deltas, dtype=float)
    if not len(arr):
        return {"n_rodadas": 0}
    rng = np.random.default_rng(SEED)
    sims = np.asarray([
        float(np.mean(rng.choice(arr, size=len(arr), replace=True)))
        for _ in range(BOOTSTRAPS)
    ])
    lo, hi = np.quantile(sims, [0.025, 0.975])
    return {
        "n_rodadas": int(len(arr)),
        "delta_mae_menos_v2": round(float(np.mean(arr)), 6),
        "ic95": [round(float(lo), 6), round(float(hi), 6)],
        "probabilidade_melhor_v2": round(float(np.mean(sims < 0)), 4),
        "rodadas_ganhas": int(np.sum(arr < 0)),
        "rodadas_perdidas": int(np.sum(arr > 0)),
        "empates": int(np.sum(np.isclose(arr, 0))),
        "por_rodada": por_rodada,
        "evidencia": "forte" if hi < 0 else "inconclusiva",
    }


def main() -> None:
    payload = json.loads(ABLATION.read_text(encoding="utf-8"))
    pred = pd.DataFrame(payload.get("previsoes") or [])
    required = {"rodada", "atleta_id", "posicao", "real", "catboost_contexto_off_cal"}
    missing = required - set(pred.columns)
    if missing:
        raise SystemExit(f"Colunas ausentes: {sorted(missing)}")
    pred = pred.rename(columns={"catboost_contexto_off_cal": "catboost"})

    rounds_v3 = sorted(pred.rodada.astype(int).unique().tolist())
    v2_rows = []
    rounds_v2_disponiveis = []
    rounds_v2_indisponiveis = []
    for rodada in rounds_v3:
        rows = fetch_v2_round(rodada)
        if rows:
            rounds_v2_disponiveis.append(int(rodada))
            v2_rows.extend(rows)
        else:
            rounds_v2_indisponiveis.append(int(rodada))

    if not v2_rows:
        raise SystemExit("Nenhuma rodada da V2 disponível para comparação pareada")

    merged = pred.merge(pd.DataFrame(v2_rows), on=["rodada", "atleta_id"], how="inner", validate="one_to_one")
    merged = merged[np.abs(merged.real.to_numpy(float) - merged.v2_real.to_numpy(float)) <= 1e-6].copy()
    if merged.empty:
        raise SystemExit("Sem linhas consistentes V2/CatBoost")

    discovery = merged[merged.rodada <= DISCOVERY_END].copy()
    holdout = merged[merged.rodada >= HOLDOUT_START].copy()
    if discovery.empty or holdout.empty:
        raise SystemExit("Split temporal discovery/holdout indisponivel")

    escolhas = {}
    for pos, g in discovery.groupby("posicao"):
        m_v2 = metric(g.real, g.v2)
        m_cb = metric(g.real, g.catboost)
        melhora_mae = m_cb["mae"] < m_v2["mae"]
        rmse_ok = m_cb["rmse"] <= m_v2["rmse"] * 1.02
        bias_ok = abs(m_cb["bias"]) <= 0.50
        usar_cb = bool(melhora_mae and rmse_ok and bias_ok)
        escolhas[str(pos)] = {
            "modelo_congelado": "CATBOOST_OFF_CAL" if usar_cb else "V2",
            "discovery_v2": m_v2,
            "discovery_catboost": m_cb,
            "checks": {
                "mae_melhor": melhora_mae,
                "rmse_nao_piora_2pct": rmse_ok,
                "bias_abs_ate_050": bias_ok,
            },
        }

    holdout["hibrido_congelado"] = holdout.apply(
        lambda r: r.catboost if escolhas.get(str(r.posicao), {}).get("modelo_congelado") == "CATBOOST_OFF_CAL" else r.v2,
        axis=1,
    )

    por_posicao_holdout = {}
    for pos, g in holdout.groupby("posicao"):
        por_posicao_holdout[str(pos)] = {
            "modelo_congelado": escolhas[str(pos)]["modelo_congelado"],
            "v2": metric(g.real, g.v2),
            "catboost": metric(g.real, g.catboost),
            "hibrido": metric(g.real, g.hibrido_congelado),
        }

    holdout_summary = {
        "linhas": int(len(holdout)),
        "rodadas": sorted(holdout.rodada.astype(int).unique().tolist()),
        "v2": metric(holdout.real, holdout.v2),
        "catboost": metric(holdout.real, holdout.catboost),
        "hibrido_congelado": metric(holdout.real, holdout.hibrido_congelado),
        "bootstrap_hibrido_vs_v2": bootstrap_rounds(holdout, "hibrido_congelado"),
        "por_posicao": por_posicao_holdout,
    }

    b = holdout_summary["bootstrap_hibrido_vs_v2"]
    strong = b.get("ic95", [1, 1])[1] < 0
    mae_better = holdout_summary["hibrido_congelado"]["mae"] < holdout_summary["v2"]["mae"]
    rmse_ok = holdout_summary["hibrido_congelado"]["rmse"] <= holdout_summary["v2"]["rmse"] * 1.02
    if strong and mae_better and rmse_ok:
        decision = "HOLDOUT_POSICIONAL_APROVADO_COM_EVIDENCIA_FORTE"
    elif mae_better and rmse_ok:
        decision = "HOLDOUT_POSICIONAL_PROMISSOR_MAS_INCONCLUSIVO"
    else:
        decision = "HOLDOUT_POSICIONAL_NAO_SUPERA_V2"

    discovery_rounds = sorted(discovery.rodada.astype(int).unique().tolist())
    holdout_rounds = sorted(holdout.rodada.astype(int).unique().tolist())
    out = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "objetivo": "Testar arquitetura posicional congelada sem escolher modelos usando o periodo de holdout.",
        "protocolo": (
            "R10-R17 e usado apenas como discovery. Para cada posicao, CatBoost OFF calibrado e escolhido somente se no discovery melhora MAE, "
            "nao piora RMSE em mais de 2% e mantem |bias| <= 0.50; caso contrario fica V2. A escolha por posicao e congelada antes do holdout. "
            "O holdout usa somente rodadas com resultado historico disponivel simultaneamente na V2 e na V3; rodadas ainda nao fechadas/publicadas pela V2 "
            "sao excluidas, nunca imputadas. Nenhum resultado do holdout participa da escolha. Bootstrap e feito em blocos de rodada."
        ),
        "anti_leakage": {
            "discovery_rodadas": discovery_rounds,
            "holdout_rodadas": holdout_rounds,
            "discovery_max": int(discovery.rodada.max()),
            "holdout_min": int(holdout.rodada.min()),
            "split_valido": bool(int(discovery.rodada.max()) < int(holdout.rodada.min())),
            "rodadas_v3_encontradas": rounds_v3,
            "rodadas_v2_disponiveis": rounds_v2_disponiveis,
            "rodadas_v2_indisponiveis_excluidas": rounds_v2_indisponiveis,
        },
        "escolhas_congeladas_por_posicao": escolhas,
        "holdout": holdout_summary,
        "decisao": decision,
        "promover_v2": False,
        "nota": "Mesmo se aprovado no holdout historico, a V2 permanece intocada; validacao prospectiva imutavel continua obrigatoria.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "decisao": decision,
        "holdout": holdout_summary,
        "escolhas": escolhas,
        "rodadas_v2_indisponiveis_excluidas": rounds_v2_indisponiveis,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
