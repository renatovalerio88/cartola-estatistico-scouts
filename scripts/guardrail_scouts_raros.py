#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAMPEONATO = ROOT / "data" / "reports" / "campeonato-modelos.json"
RAROS = ROOT / "data" / "reports" / "auditoria-eventos-raros.json"
OUT = ROOT / "data" / "reports" / "guardrail-scouts-raros.json"

MAX_BRIER_RELATIVO = 1.10
MIN_AP_RELATIVA_A_PREVALENCIA = 0.90
BIAS_ABS_MINIMO = 0.02
BIAS_RELATIVO_PREVALENCIA = 0.50
EPS = 1e-12


def carregar(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def indexar_campeonato(payload: dict) -> dict[tuple[str, str], dict]:
    out = {}
    for item in payload.get("resultados", []):
        key = (str(item.get("scout")), str(item.get("posicao")))
        out[key] = item
    return out


def quase_zero(prob_media: float, prevalencia: float) -> bool:
    if prevalencia <= 0:
        return False
    return prob_media <= max(0.001, prevalencia * 0.10)


def avaliar_modelo(
    nome: str,
    raridade: dict,
    campeonato: dict,
    brier_best: float,
) -> dict:
    met_raro = raridade["metricas"][nome]
    met_mae = campeonato["metricas"][nome]
    prevalencia = float(raridade["prevalencia"])
    ap = met_raro.get("average_precision")
    brier = float(met_raro["brier_evento"])
    bias = float(met_raro["calibration_bias"])
    prob_media = float(met_raro["prob_media"])
    limite_bias = max(BIAS_ABS_MINIMO, prevalencia * BIAS_RELATIVO_PREVALENCIA)

    falhas = []
    if brier > brier_best * MAX_BRIER_RELATIVO + EPS:
        falhas.append("brier_degradado")
    if abs(bias) > limite_bias + EPS:
        falhas.append("calibracao_degradada")
    if ap is not None and float(ap) + EPS < prevalencia * MIN_AP_RELATIVA_A_PREVALENCIA:
        falhas.append("discriminacao_abaixo_baseline")
    if quase_zero(prob_media, prevalencia):
        falhas.append("colapso_quase_zero")

    return {
        "modelo": nome,
        "mae": float(met_mae["mae"]),
        "brier": brier,
        "average_precision": float(ap) if ap is not None else None,
        "prob_media": prob_media,
        "prevalencia": prevalencia,
        "calibration_bias": bias,
        "limite_bias_abs": limite_bias,
        "aprovado_guardrail": not falhas,
        "falhas": falhas,
    }


def main() -> None:
    campeonato_payload = carregar(CAMPEONATO)
    raros_payload = carregar(RAROS)

    if not campeonato_payload.get("anti_leakage_aprovado"):
        raise RuntimeError("Campeonato sem aprovação anti-leakage")
    if not raros_payload.get("anti_leakage_aprovado"):
        raise RuntimeError("Auditoria de raros sem aprovação anti-leakage")

    campeonato_idx = indexar_campeonato(campeonato_payload)
    resultados = []
    total_guardrail_reprovado = 0
    total_colapso_zero = 0
    trocas_diagnosticas = 0

    for raro in raros_payload.get("resultados", []):
        key = (str(raro.get("scout")), str(raro.get("posicao")))
        camp = campeonato_idx.get(key)
        if not camp:
            continue

        ranking_mae = [m for m in camp.get("ranking", []) if m in raro.get("metricas", {})]
        if not ranking_mae:
            continue

        brier_best_model = raro["ranking_brier"][0]
        brier_best = float(raro["metricas"][brier_best_model]["brier_evento"])
        vencedor_mae = ranking_mae[0]
        aval_vencedor = avaliar_modelo(vencedor_mae, raro, camp, brier_best)

        candidatos = [avaliar_modelo(m, raro, camp, brier_best) for m in ranking_mae]
        aprovados = [c for c in candidatos if c["aprovado_guardrail"]]
        recomendado = min(aprovados, key=lambda c: c["mae"]) if aprovados else None

        if not aval_vencedor["aprovado_guardrail"]:
            total_guardrail_reprovado += 1
        if "colapso_quase_zero" in aval_vencedor["falhas"]:
            total_colapso_zero += 1
        if recomendado and recomendado["modelo"] != vencedor_mae:
            trocas_diagnosticas += 1

        resultados.append(
            {
                "scout": key[0],
                "posicao": key[1],
                "n": int(raro["n"]),
                "eventos": int(raro["eventos"]),
                "prevalencia": float(raro["prevalencia"]),
                "vencedor_mae": vencedor_mae,
                "avaliacao_vencedor_mae": aval_vencedor,
                "melhor_brier": brier_best_model,
                "melhor_average_precision": raro["ranking_average_precision"][0],
                "recomendado_diagnostico": recomendado["modelo"] if recomendado else None,
                "avaliacao_recomendado": recomendado,
                "acao": (
                    "MANTER_CAMPEAO_MAE"
                    if aval_vencedor["aprovado_guardrail"]
                    else "REVISAR_CAMPEAO_MAE"
                ),
            }
        )

    payload = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "status": "APROVADA" if resultados else "SEM_DADOS",
        "objetivo": (
            "Diagnosticar campeoes por MAE em scouts raros e impedir conclusoes espurias causadas por "
            "previsoes quase-zero. Este relatorio nao promove nem altera modelos de producao."
        ),
        "protocolo": (
            "Cruza apenas previsoes OOS dos mesmos folds walk-forward ja auditados. Para cada scout/posicao raro, "
            "o campeao por MAE precisa respeitar Brier, calibracao e discriminacao."
        ),
        "limites": {
            "brier_max_relativo_ao_melhor": MAX_BRIER_RELATIVO,
            "ap_min_relativa_prevalencia": MIN_AP_RELATIVA_A_PREVALENCIA,
            "bias_abs_minimo": BIAS_ABS_MINIMO,
            "bias_relativo_prevalencia": BIAS_RELATIVO_PREVALENCIA,
            "colapso_quase_zero": "prob_media <= max(0.001, 10% da prevalencia)",
        },
        "anti_leakage_aprovado": True,
        "competicoes_raras_avaliadas": len(resultados),
        "campeoes_mae_reprovados_guardrail": total_guardrail_reprovado,
        "campeoes_mae_com_colapso_quase_zero": total_colapso_zero,
        "trocas_diagnosticas_sugeridas": trocas_diagnosticas,
        "regra_de_uso": (
            "REVISAR_CAMPEAO_MAE significa apenas que o vencedor por MAE nao deve ser adotado automaticamente. "
            "Qualquer troca deve ser validada em nested walk-forward de pontuacao total antes de uso."
        ),
        "resultados": resultados,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        "Guardrail raros: "
        f"avaliados={len(resultados)}; "
        f"reprovados={total_guardrail_reprovado}; "
        f"colapso_zero={total_colapso_zero}; "
        f"trocas_diagnosticas={trocas_diagnosticas}"
    )


if __name__ == "__main__":
    main()
