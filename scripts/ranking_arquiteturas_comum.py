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
CATBOOST = ROOT / "data" / "reports" / "ablation-catboost-contexto-nested.json"
OUT = ROOT / "data" / "reports" / "ranking-arquiteturas-comum.json"
V2_RAW = "https://raw.githubusercontent.com/renatovalerio88/cartola-estatistico/main/data/historico/rodada-{rodada:02d}.json"
BOOTSTRAPS = 10000
SEED = 42


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


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


def fetch_v2(rounds: list[int]) -> pd.DataFrame:
    rows = []
    for rodada in rounds:
        response = requests.get(V2_RAW.format(rodada=rodada), timeout=30)
        if response.status_code == 404:
            continue
        response.raise_for_status()
        for j in (response.json().get("jogadores") or []):
            if not isinstance(j, dict):
                continue
            aid = j.get("id")
            pred = j.get("projecao")
            real = j.get("real")
            if aid is None or pred is None or real is None:
                continue
            try:
                rows.append({
                    "rodada": int(rodada),
                    "atleta_id": int(aid),
                    "v2": float(pred),
                    "real_v2": float(real),
                })
            except (TypeError, ValueError):
                continue
    return pd.DataFrame(rows)


def bootstrap_rounds(df: pd.DataFrame, challenger: str, baseline: str = "v2") -> dict:
    deltas = []
    por_rodada = {}
    for rodada, g in df.groupby("rodada"):
        delta = float(
            np.mean(np.abs(g[challenger].to_numpy(float) - g.real.to_numpy(float)))
            - np.mean(np.abs(g[baseline].to_numpy(float) - g.real.to_numpy(float)))
        )
        por_rodada[str(int(rodada))] = round(delta, 6)
        deltas.append(delta)
    arr = np.asarray(deltas, dtype=float)
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
        "evidencia": "forte_a_melhor" if hi < 0 else ("forte_a_pior" if lo > 0 else "inconclusiva"),
    }


def main() -> None:
    bt = pd.DataFrame(load(BACKTEST).get("previsoes", []))
    cb = pd.DataFrame(load(CATBOOST).get("previsoes", []))
    if bt.empty or cb.empty:
        raise SystemExit("Backtests necessários estão vazios")

    bt_required = {"rodada", "atleta_id", "posicao", "real", "v3s_nested", "v3h_hibrido", "direta_rf_lab", "direta_ewma"}
    cb_required = {"rodada", "atleta_id", "real", "catboost_contexto_off_cal"}
    if missing := bt_required - set(bt.columns):
        raise SystemExit(f"Colunas ausentes no backtest V3: {sorted(missing)}")
    if missing := cb_required - set(cb.columns):
        raise SystemExit(f"Colunas ausentes no CatBoost: {sorted(missing)}")

    bt = bt[list(bt_required)].copy().rename(columns={"real": "real_v3"})
    cb = cb[["rodada", "atleta_id", "real", "catboost_contexto_off_cal"]].copy().rename(columns={"real": "real_catboost"})
    rounds = sorted(set(bt.rodada.astype(int)) & set(cb.rodada.astype(int)))
    v2 = fetch_v2(rounds)
    if v2.empty:
        raise SystemExit("Nenhuma projeção histórica da V2 encontrada")

    merged = bt.merge(cb, on=["rodada", "atleta_id"], how="inner").merge(v2, on=["rodada", "atleta_id"], how="inner")
    if merged.empty:
        raise SystemExit("Interseção comum V2/V3/CatBoost vazia")

    merged["diff_real_v2_v3"] = np.abs(merged.real_v2 - merged.real_v3)
    merged["diff_real_cb_v3"] = np.abs(merged.real_catboost - merged.real_v3)
    inconsistent = merged[(merged.diff_real_v2_v3 > 1e-6) | (merged.diff_real_cb_v3 > 1e-6)].copy()
    clean = merged[(merged.diff_real_v2_v3 <= 1e-6) & (merged.diff_real_cb_v3 <= 1e-6)].copy()
    clean["real"] = clean.real_v3

    architectures = [
        "v2",
        "v3s_nested",
        "v3h_hibrido",
        "catboost_contexto_off_cal",
        "direta_rf_lab",
        "direta_ewma",
    ]
    geral = {name: metric(clean.real, clean[name]) for name in architectures}
    ranking = sorted(
        [{"arquitetura": name, **geral[name]} for name in architectures],
        key=lambda x: (x["mae"], x["rmse"]),
    )
    for i, item in enumerate(ranking, 1):
        item["posicao_ranking"] = i

    por_posicao = {}
    for pos, g in clean.groupby("posicao"):
        local = sorted(
            [{"arquitetura": name, **metric(g.real, g[name])} for name in architectures],
            key=lambda x: (x["mae"], x["rmse"]),
        )
        for i, item in enumerate(local, 1):
            item["posicao_ranking"] = i
        por_posicao[str(pos)] = local

    bootstrap = {
        name: bootstrap_rounds(clean, name)
        for name in architectures
        if name != "v2"
    }

    divergencias = []
    for _, r in inconsistent.sort_values(["rodada", "atleta_id"]).iterrows():
        divergencias.append({
            "rodada": int(r.rodada),
            "atleta_id": int(r.atleta_id),
            "posicao": str(r.posicao),
            "real_v2": round(float(r.real_v2), 6),
            "real_v3": round(float(r.real_v3), 6),
            "real_catboost": round(float(r.real_catboost), 6),
            "delta_v2_v3": round(float(r.real_v2 - r.real_v3), 6),
        })

    payload = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "objetivo": "Ranking justo das arquiteturas na mesma interseção jogador×rodada e com o mesmo resultado real.",
        "protocolo": (
            "V2 é somente leitura. V3-S/V3-H/RF/EWMA vêm do backtest nested; CatBoost OFF calibrado vem do nested temporal próprio. "
            "Todas as arquiteturas são alinhadas por rodada+atleta_id. Linhas com divergência de resultado real entre fontes são auditadas e excluídas. "
            "A ordenação usa MAE primário e RMSE como desempate; bootstrap é em blocos por rodada contra a V2."
        ),
        "anti_cherry_pick": (
            "Este ranking equaliza a amostra e evita comparar MAEs calculados em universos diferentes. Não promove modelo para produção; "
            "evidência prospectiva imutável continua obrigatória."
        ),
        "linhas_intersecao_bruta": int(len(merged)),
        "linhas_intersecao_limpa": int(len(clean)),
        "linhas_divergentes_excluidas": int(len(inconsistent)),
        "rodadas_comuns": sorted(clean.rodada.astype(int).unique().tolist()),
        "ranking_geral": ranking,
        "por_posicao": por_posicao,
        "bootstrap_vs_v2": bootstrap,
        "divergencias_resultado": divergencias,
        "lider_exploratorio_amostra_comum": ranking[0]["arquitetura"] if ranking else None,
        "promover_v2": False,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Ranking comum:", [(x["arquitetura"], x["mae"]) for x in ranking])
    print("Interseção limpa:", len(clean), "divergências excluídas:", len(inconsistent))


if __name__ == "__main__":
    main()
