#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
INP = ROOT / "data" / "reports" / "backtest-v3s-guardrail-raros-nested.json"
OUT = ROOT / "data" / "reports" / "gate-guardrail-raros.json"

N_BOOT = 20000
SEED = 20260901
MIN_PROB_MELHORA = 0.90
MAX_REGRESSAO_POSICAO = 0.02


def metrics(y: np.ndarray, p: np.ndarray) -> dict:
    err = p - y
    return {
        "n": int(len(y)),
        "mae": round(float(np.mean(np.abs(err))), 6),
        "rmse": round(float(np.sqrt(np.mean(err ** 2))), 6),
        "bias": round(float(np.mean(err)), 6),
    }


def bootstrap_por_rodada(df: pd.DataFrame) -> dict:
    # Resampleia blocos de rodada completos para preservar dependencia entre jogadores
    # da mesma rodada. O estimando e delta = MAE_guardrail - MAE_base.
    rodadas = sorted(df.rodada.astype(int).unique().tolist())
    blocos = {r: df[df.rodada.eq(r)].copy() for r in rodadas}
    rng = np.random.default_rng(SEED)
    deltas = np.empty(N_BOOT, dtype=float)

    for i in range(N_BOOT):
        escolhidas = rng.choice(rodadas, size=len(rodadas), replace=True)
        abs_base = []
        abs_guard = []
        for r in escolhidas:
            g = blocos[int(r)]
            abs_base.append(np.abs(g.v3s_mae_nested.to_numpy(float) - g.real.to_numpy(float)))
            abs_guard.append(np.abs(g.v3s_guardrail_raros_nested.to_numpy(float) - g.real.to_numpy(float)))
        a = np.concatenate(abs_base)
        b = np.concatenate(abs_guard)
        deltas[i] = float(np.mean(b) - np.mean(a))

    lo, hi = np.quantile(deltas, [0.025, 0.975])
    return {
        "metodo": "bootstrap em blocos por rodada",
        "n_boot": N_BOOT,
        "seed": SEED,
        "delta_mae_guardrail_menos_base_media_boot": round(float(deltas.mean()), 6),
        "ic95": [round(float(lo), 6), round(float(hi), 6)],
        "prob_guardrail_melhor": round(float(np.mean(deltas < 0.0)), 6),
        "prob_guardrail_nao_pior": round(float(np.mean(deltas <= 0.0)), 6),
    }


def main() -> None:
    src = json.loads(INP.read_text(encoding="utf-8"))
    pred = pd.DataFrame(src.get("previsoes", []))
    required = {"rodada", "posicao", "real", "v3s_mae_nested", "v3s_guardrail_raros_nested"}
    missing = required - set(pred.columns)
    if missing:
        raise SystemExit(f"Campos ausentes no backtest nested: {sorted(missing)}")
    if pred.empty:
        raise SystemExit("Backtest nested sem previsoes")

    geral_base = metrics(pred.real.to_numpy(float), pred.v3s_mae_nested.to_numpy(float))
    geral_guard = metrics(pred.real.to_numpy(float), pred.v3s_guardrail_raros_nested.to_numpy(float))
    delta = round(geral_guard["mae"] - geral_base["mae"], 6)

    por_posicao = {}
    regressao_material = []
    for pos, g in pred.groupby("posicao"):
        mb = metrics(g.real.to_numpy(float), g.v3s_mae_nested.to_numpy(float))
        mg = metrics(g.real.to_numpy(float), g.v3s_guardrail_raros_nested.to_numpy(float))
        d = round(mg["mae"] - mb["mae"], 6)
        por_posicao[str(pos)] = {
            "base": mb,
            "guardrail": mg,
            "delta_mae_guardrail_menos_base": d,
        }
        if d > MAX_REGRESSAO_POSICAO:
            regressao_material.append({"posicao": str(pos), "delta_mae": d})

    por_rodada = []
    wins = {"base": 0, "guardrail": 0, "empate": 0}
    for rodada, g in pred.groupby("rodada"):
        a = float(np.mean(np.abs(g.v3s_mae_nested.to_numpy(float) - g.real.to_numpy(float))))
        b = float(np.mean(np.abs(g.v3s_guardrail_raros_nested.to_numpy(float) - g.real.to_numpy(float))))
        d = b - a
        if abs(d) < 1e-12:
            winner = "empate"
        elif d < 0:
            winner = "guardrail"
        else:
            winner = "base"
        wins[winner] += 1
        por_rodada.append({
            "rodada": int(rodada),
            "mae_base": round(a, 6),
            "mae_guardrail": round(b, 6),
            "delta": round(d, 6),
            "vencedor": winner,
        })

    boot = bootstrap_por_rodada(pred)
    criterios = {
        "mae_total_nao_degrada": delta <= 0.0,
        "probabilidade_melhoria_suficiente": boot["prob_guardrail_melhor"] >= MIN_PROB_MELHORA,
        "sem_regressao_posicional_material": len(regressao_material) == 0,
        "anti_leakage_origem_aprovado": bool(src.get("anti_leakage_aprovado", False)),
    }
    aprovado = all(criterios.values())

    payload = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "status": "APROVADO_PARA_CANDIDATO" if aprovado else "MANTER_COMO_DIAGNOSTICO",
        "objetivo": (
            "Gate estatistico para decidir se o guardrail de scouts raros melhora a pontuacao total "
            "fora da amostra. Nao promove V2 nem altera producao."
        ),
        "fonte": str(INP.relative_to(ROOT)),
        "anti_leakage_aprovado": bool(src.get("anti_leakage_aprovado", False)),
        "linhas": int(len(pred)),
        "rodadas": sorted(pred.rodada.astype(int).unique().tolist()),
        "checagens_raras_inner": int(src.get("checagens_raras_inner", 0)),
        "trocas_modelo_inner": int(src.get("trocas_modelo_inner", 0)),
        "geral": {
            "base": geral_base,
            "guardrail": geral_guard,
            "delta_mae_guardrail_menos_base": delta,
        },
        "bootstrap_rodadas": boot,
        "vitorias_por_rodada": wins,
        "por_rodada": por_rodada,
        "por_posicao": por_posicao,
        "regressoes_posicionais_materiais": regressao_material,
        "limiares": {
            "probabilidade_minima_melhoria": MIN_PROB_MELHORA,
            "regressao_mae_posicao_max": MAX_REGRESSAO_POSICAO,
        },
        "criterios": criterios,
        "decisao": (
            "CANDIDATO_A_INCORPORACAO_V3" if aprovado else
            "NAO_INCORPORAR_NO_MOTOR; manter guardrail como diagnostico/explicabilidade"
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Gate guardrail raros:", payload["status"])
    print("MAE base:", geral_base["mae"])
    print("MAE guardrail:", geral_guard["mae"])
    print("Delta MAE:", delta)
    print("Bootstrap P(guardrail melhor):", boot["prob_guardrail_melhor"])
    print("IC95 delta:", boot["ic95"])
    print("Vitorias por rodada:", wins)
    print("Decisao:", payload["decisao"])


if __name__ == "__main__":
    main()
