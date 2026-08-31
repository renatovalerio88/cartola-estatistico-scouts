#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import ablation_calendario_externo

ROOT = Path(__file__).resolve().parents[1]
CALENDAR = ROOT / "data" / "context" / "calendario-externo-2026.json"
OUT = ROOT / "data" / "reports" / "ablation-calendario-externo.json"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def blocked_report(calendar_payload: dict) -> dict:
    eventos = calendar_payload.get("eventos", [])
    resumo = calendar_payload.get("resumo", {})
    errors = calendar_payload.get("erros_coleta", [])
    return {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "status": "BLOQUEADA_FONTE",
        "decisao": "NAO_AVALIAR_CALENDARIO_EXTERNO_SEM_COBERTURA",
        "escopo": "Ablation isolada do congestionamento causado por Libertadores, Sul-Americana e Copa do Brasil.",
        "protocolo": "O teste só pode rodar com calendário histórico externo de cobertura suficiente e corte temporal estrito. Ausência da fonte nunca é convertida em zero jogos.",
        "fonte_calendario": calendar_payload.get("fonte"),
        "status_coleta": calendar_payload.get("status_coleta"),
        "janela_calendario": calendar_payload.get("janela_coletada"),
        "resumo_calendario": resumo,
        "fontes": calendar_payload.get("fontes", {}),
        "erros_coleta": errors,
        "eventos_disponiveis": len(eventos),
        "cobertura_suficiente_para_ablation": False,
        "modelos_com_gate_aprovado": 0,
        "modelos_testados": 0,
        "por_modelo": {},
        "por_posicao": {},
        "provas_temporais_modelos": [],
        "provas_temporais_calendario": [],
        "previsoes": [],
        "regra_gate": "Nenhum gate é calculado sem cobertura externa suficiente.",
        "observacao": "BLOQUEADA_FONTE não significa que calendário externo foi reprovado. Significa apenas que não há dados externos auditáveis suficientes nesta execução. Nenhuma promoção é autorizada e a V2 permanece fora deste experimento.",
    }


def main():
    if not CALENDAR.exists() or CALENDAR.stat().st_size <= 2:
        raise RuntimeError("Snapshot de calendário externo ausente ou vazio após a etapa de coleta")

    payload = load_json(CALENDAR)
    coverage = bool(payload.get("cobertura_suficiente_para_ablation"))
    eventos = payload.get("eventos", [])

    if coverage and eventos:
        print(f"Calendário externo com cobertura válida ({len(eventos)} eventos). Executando ablation científica.")
        ablation_calendario_externo.main()
        return

    OUT.parent.mkdir(parents=True, exist_ok=True)
    report = blocked_report(payload)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        "Calendário externo: BLOQUEADA_FONTE | "
        f"eventos={len(eventos)} | cobertura={coverage}. "
        "Campeonato seguirá sem transformar indisponibilidade de fonte em resultado científico."
    )


if __name__ == "__main__":
    main()
