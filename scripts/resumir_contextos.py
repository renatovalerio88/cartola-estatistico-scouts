#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "data" / "reports"
OUT = REPORTS / "resumo-contextos.json"

SPECS = {
    "participacao_enriquecida": "ablation-participacao-enriquecida.json",
    "descanso_brasileirao": "ablation-descanso-brasileirao.json",
    "calendario_externo": "ablation-calendario-externo.json",
    "mudanca_tecnico": "ablation-mudanca-tecnico.json",
    "horario_partida": "ablation-horario-partida.json",
}


def load(name):
    path = REPORTS / name
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def slim_model(v):
    if not isinstance(v, dict):
        return v
    out = {}
    for key in (
        "n", "base", "participacao_enriquecida", "descanso", "calendario_externo",
        "mudanca_tecnico", "horario", "delta_mae", "bootstrap_por_rodada",
        "gate_individual",
    ):
        if key in v:
            out[key] = v[key]
    return out


def slim_report(data):
    if not isinstance(data, dict):
        return {"status": "AUSENTE"}
    out = {}
    for key in (
        "gerado_em", "status", "decisao", "escopo", "protocolo",
        "modelos_com_gate_aprovado", "modelos_testados", "regra_gate",
        "cobertura_fixture", "cobertura", "snapshot", "features_adicionais",
    ):
        if key in data:
            out[key] = data[key]
    if isinstance(data.get("por_modelo"), dict):
        out["por_modelo"] = {k: slim_model(v) for k, v in data["por_modelo"].items()}
    if isinstance(data.get("por_posicao"), dict):
        out["por_posicao"] = data["por_posicao"]
    return out


def main():
    payload = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "objetivo": "Resumo compacto e auditável das ablations de contexto; previsões linha a linha permanecem nos relatórios científicos originais.",
        "contextos": {},
    }
    for key, filename in SPECS.items():
        payload["contextos"][key] = slim_report(load(filename))
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Resumo de contextos gerado:")
    for key, item in payload["contextos"].items():
        print(
            f"- {key}: status={item.get('status')} decisao={item.get('decisao')} "
            f"gates={item.get('modelos_com_gate_aprovado')}/{item.get('modelos_testados')}"
        )


if __name__ == "__main__":
    main()
