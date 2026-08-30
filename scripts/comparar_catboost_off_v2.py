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
OUT = ROOT / "data" / "reports" / "comparacao-catboost-off-v2.json"
V2_RAW = "https://raw.githubusercontent.com/renatovalerio88/cartola-estatistico/main/data/historico/rodada-{rodada:02d}.json"
BOOTSTRAPS = 10000
SEED = 42
CONFIRMATORY_START = 18


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


def fetch_v2_round(rodada: int) -> list[dict] | None:
    response = requests.get(V2_RAW.format(rodada=rodada), timeout=30)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    rows = []
    for j in response.json().get("jogadores") or []:
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


def bootstrap_rounds(df: pd.DataFrame, challenger: str, baseline: str) -> dict:
    deltas = []
    per_round = {}
    for rodada, g in df.groupby("rodada"):
        d = float(
            np.mean(np.abs(g[challenger].to_numpy(float) - g.real.to_numpy(float)))
            - np.mean(np.abs(g[baseline].to_numpy(float) - g.real.to_numpy(float)))
        )
        deltas.append(d)
        per_round[str(int(rodada))] = round(d, 6)

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
        "delta_mae_challenger_menos_v2": round(float(np.mean(arr)), 6),
        "ic95": [round(float(lo), 6), round(float(hi), 6)],
        "probabilidade_challenger_melhor": round(float(np.mean(sims < 0)), 4),
        "rodadas_ganhas": int(np.sum(arr < 0)),
        "rodadas_perdidas": int(np.sum(arr > 0)),
        "empates": int(np.sum(np.isclose(arr, 0))),
        "por_rodada": per_round,
        "evidencia": (
            "forte_a_melhor" if hi < 0
            else "forte_a_pior" if lo > 0
            else "inconclusiva"
        ),
    }


def summarize(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"n": 0}
    return {
        "linhas": int(len(df)),
        "rodadas": sorted(df.rodada.astype(int).unique().tolist()),
        "v2": metric(df.real, df.v2),
        "catboost_off_cal": metric(df.real, df.catboost_off_cal),
        "bootstrap": bootstrap_rounds(df, "catboost_off_cal", "v2"),
        "por_posicao": {
            str(pos): {
                "v2": metric(g.real, g.v2),
                "catboost_off_cal": metric(g.real, g.catboost_off_cal),
            }
            for pos, g in df.groupby("posicao")
        },
    }


def main() -> None:
    if not ABLATION.exists():
        raise SystemExit("Relatorio ablation CatBoost ausente")
    payload = json.loads(ABLATION.read_text(encoding="utf-8"))
    pred = pd.DataFrame(payload.get("previsoes") or [])
    required = {"rodada", "atleta_id", "posicao", "real", "catboost_contexto_off_cal"}
    missing = required - set(pred.columns)
    if missing:
        raise SystemExit(f"Colunas ausentes: {sorted(missing)}")
    pred = pred.rename(columns={"catboost_contexto_off_cal": "catboost_off_cal"})

    rounds = sorted(pred.rodada.astype(int).unique().tolist())
    v2_rows = []
    missing_rounds = []
    for rodada in rounds:
        rows = fetch_v2_round(rodada)
        if rows is None:
            missing_rounds.append(rodada)
        else:
            v2_rows.extend(rows)
    if not v2_rows:
        raise SystemExit("Nenhuma previsao oficial V2 encontrada")

    merged = pred.merge(pd.DataFrame(v2_rows), on=["rodada", "atleta_id"], how="inner", validate="one_to_one")
    merged["real_diff"] = np.abs(merged.real.to_numpy(float) - merged.v2_real.to_numpy(float))
    inconsistent = merged[merged.real_diff > 1e-6]
    merged = merged[merged.real_diff <= 1e-6].copy()
    if merged.empty:
        raise SystemExit("Sem linhas V2/CatBoost com real consistente")

    all_period = summarize(merged)
    confirmatory = summarize(merged[merged.rodada >= CONFIRMATORY_START].copy())

    checks = {
        "resultados_reais_consistentes": bool(len(inconsistent) == 0),
        "periodo_confirmatorio_disponivel": bool(confirmatory.get("n", confirmatory.get("linhas", 0)) > 0),
        "mae_total_melhor_v2": bool(all_period["catboost_off_cal"]["mae"] < all_period["v2"]["mae"]),
        "rmse_total_nao_piora_2pct": bool(
            all_period["catboost_off_cal"]["rmse"] <= all_period["v2"]["rmse"] * 1.02
        ),
        "bias_total_abs_ate_050": bool(abs(all_period["catboost_off_cal"]["bias"]) <= 0.50),
        "confirmatorio_mae_melhor_v2": bool(
            confirmatory.get("linhas", 0) > 0
            and confirmatory["catboost_off_cal"]["mae"] < confirmatory["v2"]["mae"]
        ),
    }

    # O período total é exploratório porque a janela de calibração de 5 rodadas surgiu durante o laboratório.
    # O recorte R18+ é tratado como teste de robustez temporal, não como prova prospectiva definitiva.
    strong_total = all_period["bootstrap"]["ic95"][1] < 0
    strong_confirm = (
        confirmatory.get("linhas", 0) > 0
        and confirmatory["bootstrap"].get("ic95", [1, 1])[1] < 0
    )
    if all(checks.values()) and strong_total and strong_confirm:
        decision = "CHALLENGER_FORTE_MAS_AGUARDAR_VALIDACAO_PROSPECTIVA"
    elif checks["mae_total_melhor_v2"] and checks["rmse_total_nao_piora_2pct"]:
        decision = "CHALLENGER_PROMISSOR_SEM_EVIDENCIA_CONFIRMATORIA_SUFICIENTE"
    else:
        decision = "NAO_SUPERA_V2_COM_ROBUSTEZ"

    out = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "objetivo": "Comparar CatBoost contexto OFF com calibracao residual online fixa contra a V2 historicamente salva.",
        "protocolo": (
            "As previsoes CatBoost sao OOS por rodada e a calibracao de cada R usa somente residuos de ate 5 rodadas anteriores da mesma posicao. "
            "A V2 e lida diretamente dos snapshots historicos de producao. As linhas sao alinhadas por rodada+atleta_id e divergencias no real sao excluidas. "
            "Bootstrap e feito em blocos por rodada. R18+ e reportado separadamente como robustez temporal posterior, sem alegar independencia prospectiva completa."
        ),
        "nota_anti_cherry_pick": (
            "A janela CAL_WINDOW=5 ja havia sido explorada antes desta comparacao. Por isso o resultado total nao pode, sozinho, promover arquitetura. "
            "A decisao permanece bloqueada para V2 e exige validacao prospectiva em previsoes imutaveis futuras."
        ),
        "rodadas_v2_ausentes": missing_rounds,
        "linhas_comuns": int(len(merged) + len(inconsistent)),
        "linhas_consistentes": int(len(merged)),
        "linhas_real_divergente": int(len(inconsistent)),
        "periodo_total_exploratorio": all_period,
        "periodo_robustez_r18_mais": confirmatory,
        "checks": checks,
        "decisao": decision,
        "promover_v2": False,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "total": all_period,
        "robustez_r18_mais": confirmatory,
        "decisao": decision,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
