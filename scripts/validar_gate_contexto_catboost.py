#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ABLATION = ROOT / "data" / "reports" / "ablation-contexto.json"
OUT = ROOT / "data" / "reports" / "gate-contexto-catboost.json"

# O CatBoost nested usa mando + métricas históricas de força do time/adversário.
# Este gate impede que o challenger pesado rode com essas features se o ablation
# walk-forward atual não sustentar evidência mínima previamente definida.
REQUIRED_SIGNAL = "PROMISSORIO_FORTE"
MIN_MODELS_IMPROVED = 3
MIN_MODELS_PROB_80 = 2
MIN_MODELS_CI_BELOW_ZERO = 1
MAX_RMSE_DETERIORATION_RIDGE = 0.02  # tolerância relativa de 2%


def main() -> None:
    if not ABLATION.exists():
        raise SystemExit("Gate bloqueado: ablation-contexto.json não existe")

    report = json.loads(ABLATION.read_text(encoding="utf-8"))
    factor = report.get("fatores", {}).get("mando_mais_forca", {})
    aggregate = report.get("agregado", {}).get("ridge", {})
    base = aggregate.get("base", {})
    context = aggregate.get("base_mando_forca", {})

    base_rmse = float(base.get("rmse", 0) or 0)
    context_rmse = float(context.get("rmse", 0) or 0)
    rmse_relative = (
        (context_rmse - base_rmse) / base_rmse if base_rmse > 0 else 999.0
    )

    checks = {
        "protocolo_walk_forward_estrito": "Walk-forward estrito" in str(report.get("protocolo", "")),
        "sinal_forte": factor.get("sinal") == REQUIRED_SIGNAL,
        "todos_modelos_melhoram_mae": int(factor.get("modelos_com_melhora", 0)) >= MIN_MODELS_IMPROVED,
        "evidencia_probabilistica_multimodelo": int(
            factor.get("modelos_probabilidade_melhora_ge_80pct", 0)
        ) >= MIN_MODELS_PROB_80,
        "ao_menos_um_ic95_totalmente_favoravel": int(
            factor.get("modelos_ic95_totalmente_abaixo_zero", 0)
        ) >= MIN_MODELS_CI_BELOW_ZERO,
        "rmse_ridge_dentro_guardrail": rmse_relative <= MAX_RMSE_DETERIORATION_RIDGE,
    }
    approved = all(checks.values())

    payload = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "objetivo": "Autorizar ou bloquear uso de mando+forca no CatBoost nested V3 sem tocar na V2.",
        "regra": {
            "sinal_exigido": REQUIRED_SIGNAL,
            "modelos_com_melhora_min": MIN_MODELS_IMPROVED,
            "modelos_probabilidade_ge_80pct_min": MIN_MODELS_PROB_80,
            "modelos_ic95_favoravel_min": MIN_MODELS_CI_BELOW_ZERO,
            "deterioracao_rmse_ridge_max_relativa": MAX_RMSE_DETERIORATION_RIDGE,
        },
        "evidencia": {
            "delta_mae_medio": factor.get("delta_mae_medio"),
            "modelos_com_melhora": factor.get("modelos_com_melhora"),
            "modelos_probabilidade_melhora_ge_80pct": factor.get(
                "modelos_probabilidade_melhora_ge_80pct"
            ),
            "modelos_ic95_totalmente_abaixo_zero": factor.get(
                "modelos_ic95_totalmente_abaixo_zero"
            ),
            "ridge_base_mae": base.get("mae"),
            "ridge_contexto_mae": context.get("mae"),
            "ridge_base_rmse": base.get("rmse"),
            "ridge_contexto_rmse": context.get("rmse"),
            "ridge_deterioracao_rmse_relativa": round(rmse_relative, 6),
            "bootstrap_ridge": factor.get("bootstrap_pareado_por_rodada", {}).get("ridge"),
        },
        "checks": checks,
        "aprovado": approved,
        "decisao": "CONTEXTO_AUTORIZADO_NO_CHALLENGER" if approved else "CONTEXTO_BLOQUEADO",
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if not approved:
        raise SystemExit(
            "Gate bloqueado: mando+forca não atingiu os guardrails científicos para o CatBoost nested"
        )


if __name__ == "__main__":
    main()
