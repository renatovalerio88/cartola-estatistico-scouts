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
OUT = ROOT / "data" / "reports" / "seletor-posicional-temporal.json"
V2_RAW = "https://raw.githubusercontent.com/renatovalerio88/cartola-estatistico/main/data/historico/rodada-{rodada:02d}.json"
BOOTSTRAPS = 10000
SEED = 42
MIN_PRIOR_ROUNDS = 3

ARCHITECTURES_ALL = [
    "v2",
    "v3s_nested",
    "v3h_hibrido",
    "catboost_contexto_off_cal",
    "direta_rf_lab",
    "direta_ewma",
]
ARCHITECTURES_CORE = ["v2", "v3h_hibrido", "catboost_contexto_off_cal"]


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
            aid, pred, real = j.get("id"), j.get("projecao"), j.get("real")
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


def common_frame() -> tuple[pd.DataFrame, int]:
    bt = pd.DataFrame(load(BACKTEST).get("previsoes", []))
    cb = pd.DataFrame(load(CATBOOST).get("previsoes", []))
    if bt.empty or cb.empty:
        raise SystemExit("Backtests necessários estão vazios")

    bt_cols = ["rodada", "atleta_id", "posicao", "real", "v3s_nested", "v3h_hibrido", "direta_rf_lab", "direta_ewma"]
    cb_cols = ["rodada", "atleta_id", "real", "catboost_contexto_off_cal"]
    missing_bt = set(bt_cols) - set(bt.columns)
    missing_cb = set(cb_cols) - set(cb.columns)
    if missing_bt:
        raise SystemExit(f"Colunas ausentes V3: {sorted(missing_bt)}")
    if missing_cb:
        raise SystemExit(f"Colunas ausentes CatBoost: {sorted(missing_cb)}")

    bt = bt[bt_cols].rename(columns={"real": "real_v3"})
    cb = cb[cb_cols].rename(columns={"real": "real_cb"})
    rounds = sorted(set(bt.rodada.astype(int)) & set(cb.rodada.astype(int)))
    v2 = fetch_v2(rounds)
    if v2.empty:
        raise SystemExit("V2 histórica indisponível")

    merged = bt.merge(cb, on=["rodada", "atleta_id"], how="inner").merge(v2, on=["rodada", "atleta_id"], how="inner")
    clean = merged[
        (np.abs(merged.real_v2 - merged.real_v3) <= 1e-6)
        & (np.abs(merged.real_cb - merged.real_v3) <= 1e-6)
    ].copy()
    clean["real"] = clean.real_v3.astype(float)
    clean["rodada"] = clean.rodada.astype(int)
    clean["posicao"] = clean.posicao.astype(str)
    clean = clean.dropna(subset=ARCHITECTURES_ALL + ["real", "posicao"])
    return clean, int(len(merged) - len(clean))


def choose_architecture(history: pd.DataFrame, position: str, candidates: list[str]) -> tuple[str, dict]:
    h = history[history.posicao == position]
    rounds = sorted(h.rodada.unique().tolist())
    if len(rounds) < MIN_PRIOR_ROUNDS or h.empty:
        return "v2", {"motivo": "fallback_historico_insuficiente", "rodadas_treino": len(rounds)}

    scores = {}
    for name in candidates:
        scores[name] = metric(h.real, h[name])
    winner = min(candidates, key=lambda name: (scores[name]["mae"], scores[name]["rmse"], abs(scores[name]["bias"])))
    return winner, {
        "motivo": "menor_mae_historico_anterior",
        "rodadas_treino": len(rounds),
        "primeira_rodada_treino": int(min(rounds)),
        "ultima_rodada_treino": int(max(rounds)),
        "scores": scores,
    }


def walk_forward(clean: pd.DataFrame, candidates: list[str], label: str) -> tuple[pd.DataFrame, list[dict]]:
    rows = []
    decisions = []
    rounds = sorted(clean.rodada.unique().tolist())

    for target in rounds:
        history = clean[clean.rodada < target]
        target_df = clean[clean.rodada == target]
        for pos in sorted(target_df.posicao.unique().tolist()):
            winner, evidence = choose_architecture(history, pos, candidates)
            decisions.append({
                "seletor": label,
                "rodada_alvo": int(target),
                "posicao": pos,
                "arquitetura_escolhida": winner,
                **evidence,
            })
            g = target_df[target_df.posicao == pos]
            for _, r in g.iterrows():
                rows.append({
                    "rodada": int(target),
                    "atleta_id": int(r.atleta_id),
                    "posicao": pos,
                    "real": float(r.real),
                    "v2": float(r.v2),
                    "catboost_contexto_off_cal": float(r.catboost_contexto_off_cal),
                    "previsao_seletor": float(r[winner]),
                    "arquitetura_escolhida": winner,
                })
    return pd.DataFrame(rows), decisions


def bootstrap_rounds(df: pd.DataFrame, challenger: str, baseline: str) -> dict:
    deltas = []
    per_round = {}
    for rodada, g in df.groupby("rodada"):
        if g.empty:
            continue
        d = float(
            np.mean(np.abs(g[challenger].to_numpy(float) - g.real.to_numpy(float)))
            - np.mean(np.abs(g[baseline].to_numpy(float) - g.real.to_numpy(float)))
        )
        deltas.append(d)
        per_round[str(int(rodada))] = round(d, 6)
    if not deltas:
        return {"n_rodadas": 0}
    arr = np.asarray(deltas, dtype=float)
    rng = np.random.default_rng(SEED)
    sims = np.asarray([float(np.mean(rng.choice(arr, size=len(arr), replace=True))) for _ in range(BOOTSTRAPS)])
    lo, hi = np.quantile(sims, [0.025, 0.975])
    return {
        "n_rodadas": int(len(arr)),
        "delta_mae": round(float(np.mean(arr)), 6),
        "ic95": [round(float(lo), 6), round(float(hi), 6)],
        "probabilidade_challenger_melhor": round(float(np.mean(sims < 0)), 4),
        "rodadas_ganhas": int(np.sum(arr < 0)),
        "rodadas_perdidas": int(np.sum(arr > 0)),
        "empates": int(np.sum(np.isclose(arr, 0))),
        "por_rodada": per_round,
        "evidencia": "forte_a_melhor" if hi < 0 else ("forte_a_pior" if lo > 0 else "inconclusiva"),
    }


def summarize(preds: pd.DataFrame) -> dict:
    eligible = preds.copy()
    # Exclui targets em que nenhuma posição tinha o mínimo de rodadas anteriores.
    eligibility = eligible.groupby("rodada")["arquitetura_escolhida"].apply(lambda s: bool((s != "v2").any()))
    valid_rounds = eligibility[eligibility].index.tolist()
    eligible = eligible[eligible.rodada.isin(valid_rounds)].copy()
    if eligible.empty:
        return {"status": "amostra_insuficiente", "rodadas_avaliadas": []}

    by_position = {}
    for pos, g in eligible.groupby("posicao"):
        by_position[str(pos)] = {
            "seletor": metric(g.real, g.previsao_seletor),
            "v2": metric(g.real, g.v2),
            "catboost": metric(g.real, g.catboost_contexto_off_cal),
        }

    return {
        "status": "avaliado",
        "rodadas_avaliadas": sorted(int(x) for x in eligible.rodada.unique().tolist()),
        "metricas": {
            "seletor": metric(eligible.real, eligible.previsao_seletor),
            "v2": metric(eligible.real, eligible.v2),
            "catboost_global": metric(eligible.real, eligible.catboost_contexto_off_cal),
        },
        "bootstrap_vs_v2": bootstrap_rounds(eligible, "previsao_seletor", "v2"),
        "bootstrap_vs_catboost_global": bootstrap_rounds(eligible, "previsao_seletor", "catboost_contexto_off_cal"),
        "por_posicao": by_position,
        "contagem_escolhas": {str(k): int(v) for k, v in eligible.arquitetura_escolhida.value_counts().to_dict().items()},
    }


def main() -> None:
    clean, divergences = common_frame()
    if clean.empty:
        raise SystemExit("Interseção limpa vazia")

    pred_core, dec_core = walk_forward(clean, ARCHITECTURES_CORE, "core")
    pred_all, dec_all = walk_forward(clean, ARCHITECTURES_ALL, "todos")

    payload = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "objetivo": "Testar se escolher a arquitetura por posição usando somente rodadas anteriores supera V2 e CatBoost global.",
        "protocolo": (
            "Para cada rodada-alvo R e posição, o seletor calcula MAE/RMSE/bias apenas em registros da mesma posição com rodada < R. "
            f"Exige pelo menos {MIN_PRIOR_ROUNDS} rodadas anteriores; caso contrário usa V2 como fallback. "
            "A escolha é congelada antes de avaliar R. Nenhuma pontuação ou scout da rodada-alvo participa da seleção."
        ),
        "anti_leakage": True,
        "min_rodadas_anteriores": MIN_PRIOR_ROUNDS,
        "linhas_intersecao_limpa": int(len(clean)),
        "divergencias_resultado_excluidas": divergences,
        "rodadas_disponiveis": sorted(int(x) for x in clean.rodada.unique().tolist()),
        "seletor_core_v2_v3h_catboost": summarize(pred_core),
        "seletor_todas_arquiteturas": summarize(pred_all),
        "decisoes_core": dec_core,
        "decisoes_todas": dec_all,
        "promover_v2": False,
        "nota": "Resultado é retrospectivo walk-forward e precisa de confirmação prospectiva imutável antes de qualquer promoção.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    core = payload["seletor_core_v2_v3h_catboost"]
    all_ = payload["seletor_todas_arquiteturas"]
    print("Seletor posicional core:", core.get("metricas", {}))
    print("Seletor posicional todos:", all_.get("metricas", {}))


if __name__ == "__main__":
    main()
