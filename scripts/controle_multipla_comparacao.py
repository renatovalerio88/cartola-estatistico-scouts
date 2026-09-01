#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "reports" / "comparacao-v2-oficial-v3.json"
DOIS = ROOT / "data" / "reports" / "gate-dois-estagios.json"
OUT = ROOT / "data" / "reports" / "controle-multipla-comparacao.json"
ALPHA = 0.05


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def two_sided_p_from_bootstrap_probability(prob_better: float) -> float:
    """P-valor empírico bilateral conservador a partir da massa bootstrap de delta<0."""
    p = float(prob_better)
    return min(1.0, 2.0 * min(p, 1.0 - p))


def holm_adjust(pvalues: dict[str, float]) -> dict[str, dict]:
    ordered = sorted(pvalues.items(), key=lambda kv: kv[1])
    m = len(ordered)
    running = 0.0
    adjusted: dict[str, float] = {}
    for rank, (name, p) in enumerate(ordered, start=1):
        raw_adj = min(1.0, (m - rank + 1) * p)
        running = max(running, raw_adj)
        adjusted[name] = min(1.0, running)
    return {
        name: {
            "p_empirico_bilateral": round(float(pvalues[name]), 6),
            "p_holm": round(float(adjusted[name]), 6),
            "significativo_fwer_5pct": bool(adjusted[name] <= ALPHA),
        }
        for name in pvalues
    }


def main() -> None:
    if not SRC.exists():
        raise SystemExit("comparacao-v2-oficial-v3.json ausente")

    d = load(SRC)
    comps = d.get("comparacoes_bootstrap", {})
    if not comps:
        raise SystemExit("comparacoes_bootstrap ausentes")

    pvalues: dict[str, float] = {}
    detalhes: dict[str, dict] = {}
    amostras_opcionais = d.get("amostras_comparacoes_opcionais", {}) or {}

    for name, item in comps.items():
        prob = item.get("probabilidade_bootstrap_desafiante_melhor")
        if prob is None:
            continue
        pvalues[name] = two_sided_p_from_bootstrap_probability(float(prob))
        detalhe = {
            "probabilidade_bootstrap_desafiante_melhor": float(prob),
            "diferenca_mae_desafiante_menos_v2": item.get("diferenca_mae_desafiante_menos_base"),
            "ic95": item.get("ic95"),
            "rodadas_ganhas": item.get("rodadas_ganhas"),
            "rodadas_perdidas": item.get("rodadas_perdidas"),
        }
        if name in amostras_opcionais:
            detalhe["amostra_pareada"] = amostras_opcionais[name]
        detalhes[name] = detalhe

    if not pvalues:
        raise SystemExit("nenhuma comparacao com probabilidade bootstrap")

    adjusted = holm_adjust(pvalues)
    for name in detalhes:
        detalhes[name].update(adjusted[name])

    vencedores = [
        name
        for name, x in detalhes.items()
        if x["significativo_fwer_5pct"]
        and x.get("diferenca_mae_desafiante_menos_v2") is not None
        and float(x["diferenca_mae_desafiante_menos_v2"]) < 0
    ]

    dois = load(DOIS) if DOIS.exists() else None
    dois_status = None
    if dois:
        dois_status = {
            "status": dois.get("status"),
            "decisao": dois.get("decisao"),
            "incluido_no_holm_vs_v2": "dois_estagios_vs_v2" in detalhes,
            "resultado_holm": detalhes.get("dois_estagios_vs_v2"),
        }

    payload = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "objetivo": "Controlar inflacao de falso positivo apos testar multiplos challengers contra a V2.",
        "metodo": "p-valor empirico bilateral derivado do bootstrap em blocos por rodada + correcao Holm-Bonferroni (FWER 5%)",
        "alpha": ALPHA,
        "numero_comparacoes": len(detalhes),
        "amostra_base": {
            "linhas_consistentes": d.get("linhas_consistentes"),
            "rodadas_comuns": d.get("rodadas_comuns", []),
        },
        "nota_amostras": (
            "Comparacoes opcionais como CatBoost nested e dois estagios usam sua propria intersecao pareada "
            "V2/desafiante, registrada no relatorio de comparacao; entram no mesmo controle Holm apenas porque "
            "cada p-valor foi obtido contra a V2 historica salva sem olhar a rodada avaliada."
        ),
        "comparacoes": detalhes,
        "challengers_com_evidencia_apos_holm": vencedores,
        "dois_estagios": dois_status,
        "regra_decisao": (
            "Nao declarar vencedor final apenas por MAE ou probabilidade bootstrap nominal; "
            "exigir delta favoravel e significancia apos Holm em comparacao pareada contra a V2."
        ),
        "nota": (
            "Este controle e deliberadamente conservador. Ele nao promove modelo para V2 e nao altera producao."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
