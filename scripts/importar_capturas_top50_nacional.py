#!/usr/bin/env python3
"""Importa capturas sanitizadas da classificação oficial Nacional.

O script nunca lê cookies/tokens e nunca promove uma coorte parcial. Ele aceita
somente snapshots previamente sanitizados em
``data/raw/top50-liga-nacional/capturas-browser/pagina-XX.json``.

Gate científico para promoção:
- exatamente 50 registros;
- 50 ``time_id`` únicos;
- rankings contínuos de 1 a 50;
- páginas com origem explícita na interface oficial;
- SHA-256 de cada snapshot de entrada preservado na proveniência.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CAPTURES = ROOT / "data" / "raw" / "top50-liga-nacional" / "capturas-browser"
OUT = ROOT / "data" / "raw" / "top50-liga-nacional" / "top50-atual.json"
REPORT = ROOT / "data" / "reports" / "top50-liga-nacional-importacao.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_capture(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if obj.get("sanitizado") is not True:
        raise ValueError(f"{path.name}: captura não marcada como sanitizada")
    origem = str(obj.get("origem") or "")
    if "Nacional" not in origem or "Cartola" not in origem:
        raise ValueError(f"{path.name}: origem oficial Nacional não identificada")
    rows = obj.get("times")
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"{path.name}: lista de times ausente")
    clean: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        tid = row.get("time_id")
        rank = row.get("ranking_campeonato")
        if not isinstance(tid, int) or not isinstance(rank, int):
            raise ValueError(f"{path.name}: time_id/ranking inválido")
        clean.append(
            {
                "time_id": tid,
                "nome": row.get("nome"),
                "ranking_campeonato": rank,
                "pontos_campeonato": row.get("pontos_campeonato"),
                "patrimonio": row.get("patrimonio"),
            }
        )
    return obj, clean


def main() -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    CAPTURES.mkdir(parents=True, exist_ok=True)
    files = sorted(CAPTURES.glob("pagina-*.json"))

    rows: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    errors: list[str] = []
    for path in files:
        try:
            obj, part = load_capture(path)
            rows.extend(part)
            sources.append(
                {
                    "arquivo": str(path.relative_to(ROOT)),
                    "pagina": obj.get("pagina"),
                    "request_observada": obj.get("request_observada"),
                    "capturado_em": obj.get("capturado_em"),
                    "sha256": sha256(path),
                    "n": len(part),
                }
            )
        except (ValueError, json.JSONDecodeError) as exc:
            errors.append(str(exc))

    rows.sort(key=lambda r: r["ranking_campeonato"])
    ids = [r["time_id"] for r in rows]
    ranks = [r["ranking_campeonato"] for r in rows]
    exact = (
        not errors
        and len(rows) == 50
        and len(set(ids)) == 50
        and ranks == list(range(1, 51))
    )

    if exact:
        payload = {
            "capturado_em": now_iso(),
            "liga": {
                "nome": "Nacional",
                "categoria_interface": "Ligas do Cartola",
                "tipo_interface": "Clássica",
            },
            "fonte": {
                "nome": "capturas_browser_oficiais_sanitizadas",
                "url": "interface Cartola / competições / clássica / nacional",
                "snapshots": sources,
            },
            "tipo_coorte": "ranking_atual_congelado",
            "alerta": "Coorte atual; uso retrospectivo sujeito a survivorship bias.",
            "top50": rows,
        }
        OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        status = "COORTE_50_PROMOVIDA"
    else:
        status = "COORTE_PARCIAL"
        # Nunca deixa uma coorte antiga parecer válida quando o conjunto atual
        # não passa pelo gate completo.
        if OUT.exists():
            try:
                old = json.loads(OUT.read_text(encoding="utf-8"))
                if old.get("fonte", {}).get("nome") == "capturas_browser_oficiais_sanitizadas":
                    OUT.unlink()
            except (json.JSONDecodeError, AttributeError):
                pass

    report = {
        "gerado_em": now_iso(),
        "status": status,
        "capturas_validas": len(sources),
        "registros": len(rows),
        "time_id_unicos": len(set(ids)),
        "ranking_min": min(ranks) if ranks else None,
        "ranking_max": max(ranks) if ranks else None,
        "ranking_continuo_1_50": ranks == list(range(1, 51)),
        "erros": errors,
        "snapshots": sources,
        "proximo_passo": (
            "Coorte pronta para validação/análise histórica."
            if exact
            else "Aguardar captura sanitizada complementar até completar rankings 1-50; não promover coorte parcial."
        ),
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
