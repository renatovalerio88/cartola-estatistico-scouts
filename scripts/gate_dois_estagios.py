#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "reports" / "backtest-v3s-dois-estagios.json"
OUT = ROOT / "data" / "reports" / "gate-dois-estagios.json"


def main():
    if not SRC.exists():
        raise SystemExit("backtest-v3s-dois-estagios.json ausente")
    d = json.loads(SRC.read_text(encoding="utf-8"))
    geral = d.get("geral", {})
    dois = geral.get("v3s_dois_estagios", {})
    cb = geral.get("v3s_catboost_nested", {})
    h = geral.get("v3h_hibrido", {})
    bcb = d.get("bootstrap_vs_catboost_direto", {})
    bh = d.get("bootstrap_vs_v3h", {})

    mae_dois = float(dois.get("mae", 999))
    mae_cb = float(cb.get("mae", 999))
    mae_h = float(h.get("mae", 999))
    prob_cb = float(bcb.get("probabilidade_dois_estagios_melhor", 0))
    prob_h = float(bh.get("probabilidade_dois_estagios_melhor", 0))

    por_pos = d.get("por_posicao", {})
    regressao_material = []
    for pos, x in por_pos.items():
        m = x.get("dois_estagios", {}).get("mae")
        if m is None:
            continue
        # Sem baseline posicional pareado no próprio relatório, não inventamos comparação.

    criterios = {
        "mae_valido": mae_dois < 999,
        "supera_catboost_nested_no_mae": mae_dois < mae_cb,
        "supera_v3h_no_mae": mae_dois < mae_h,
        "prob_melhora_vs_catboost_ge_90": prob_cb >= 0.90,
        "prob_melhora_vs_v3h_ge_90": prob_h >= 0.90,
        "participacao_calibrada": abs(float(d.get("participacao", {}).get("probabilidade_media_prevista", 0)) - float(d.get("participacao", {}).get("taxa_real_entrada", 0))) <= 0.05,
    }
    aprovado = all(criterios.values())
    payload = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "status": "CANDIDATO_APROVADO" if aprovado else "MANTER_EXPERIMENTAL",
        "objetivo": "Gate estrito do modelo V3-S em dois estágios; não promove V2 nem produção.",
        "fonte": str(SRC.relative_to(ROOT)),
        "linhas": d.get("linhas"),
        "rodadas": d.get("rodadas", []),
        "mae": {"dois_estagios": mae_dois, "catboost_nested": mae_cb, "v3h": mae_h},
        "participacao": d.get("participacao", {}),
        "bootstrap_vs_catboost": bcb,
        "bootstrap_vs_v3h": bh,
        "criterios": criterios,
        "decisao": "AVANCAR_PARA_COMPARACAO_FINAL" if aprovado else "NAO_INCORPORAR; manter como experimento ate nova evidencia",
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
