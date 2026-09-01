#!/usr/bin/env python3
"""Importa capturas sanitizadas da classificação oficial Nacional.

O script nunca lê cookies/tokens e nunca promove uma coorte parcial. Ele aceita
somente snapshots previamente sanitizados em
``data/raw/top50-liga-nacional/capturas-browser/pagina-XX.json``.

Gate científico para promoção:
- exatamente 2 páginas oficiais (1 e 2);
- exatamente 25 registros por página;
- página 1 cobrindo rankings 1-25 e página 2 cobrindo 26-50;
- exatamente 50 registros totais;
- 50 ``time_id`` únicos;
- rankings contínuos de 1 a 50;
- request observada coerente com ``orderBy=campeonato`` e a página declarada;
- origem explícita na interface oficial do Cartola;
- ausência de campos de credencial/sessão na captura sanitizada;
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

FORBIDDEN_KEYS = {
    "authorization",
    "cookie",
    "cookies",
    "token",
    "access_token",
    "access-token",
    "refresh_token",
    "session",
    "sessionid",
    "jwt",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def find_forbidden_keys(value: Any, prefix: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_norm = str(key).strip().lower()
            path = f"{prefix}.{key}" if prefix else str(key)
            if key_norm in FORBIDDEN_KEYS:
                found.append(path)
            found.extend(find_forbidden_keys(child, path))
    elif isinstance(value, list):
        for idx, child in enumerate(value):
            path = f"{prefix}[{idx}]"
            found.extend(find_forbidden_keys(child, path))
    return found


def expected_ranks(page: int) -> list[int]:
    start = 1 + (page - 1) * 25
    return list(range(start, start + 25))


def validate_request(request: str, page: int) -> None:
    normalized = request.replace(" ", "")
    if "orderBy=campeonato" not in normalized:
        raise ValueError(f"pagina-{page:02d}: request sem orderBy=campeonato")
    if f"page={page}" not in normalized:
        raise ValueError(f"pagina-{page:02d}: request incompatível com página declarada")
    if "nacional" not in normalized.lower():
        raise ValueError(f"pagina-{page:02d}: request não identifica endpoint Nacional")


def load_capture(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    obj = json.loads(path.read_text(encoding="utf-8"))

    if obj.get("sanitizado") is not True:
        raise ValueError(f"{path.name}: captura não marcada como sanitizada")

    forbidden = find_forbidden_keys(obj)
    if forbidden:
        raise ValueError(
            f"{path.name}: captura contém campos de credencial/sessão proibidos: "
            + ", ".join(forbidden[:10])
        )

    origem = str(obj.get("origem") or "")
    if "Nacional" not in origem or "Cartola" not in origem:
        raise ValueError(f"{path.name}: origem oficial Nacional não identificada")

    page = obj.get("pagina")
    if page not in (1, 2):
        raise ValueError(f"{path.name}: página inválida; esperado 1 ou 2")

    request = str(obj.get("request_observada") or "")
    validate_request(request, int(page))

    rows = obj.get("times")
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"{path.name}: lista de times ausente")
    if len(rows) != 25:
        raise ValueError(f"{path.name}: esperado 25 times; recebido {len(rows)}")

    clean: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(f"{path.name}: registro de time inválido")
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

    ranks = sorted(r["ranking_campeonato"] for r in clean)
    if ranks != expected_ranks(int(page)):
        raise ValueError(
            f"{path.name}: cobertura de ranking inválida para página {page}; "
            f"esperado {expected_ranks(int(page))[0]}-{expected_ranks(int(page))[-1]}"
        )

    ids = [r["time_id"] for r in clean]
    if len(set(ids)) != 25:
        raise ValueError(f"{path.name}: time_id duplicado dentro da página")

    return obj, clean


def main() -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    CAPTURES.mkdir(parents=True, exist_ok=True)
    files = sorted(CAPTURES.glob("pagina-*.json"))

    rows: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    errors: list[str] = []
    seen_pages: set[int] = set()

    for path in files:
        try:
            obj, part = load_capture(path)
            page = int(obj["pagina"])
            if page in seen_pages:
                raise ValueError(f"{path.name}: página {page} duplicada")
            seen_pages.add(page)
            rows.extend(part)
            sources.append(
                {
                    "arquivo": str(path.relative_to(ROOT)),
                    "pagina": page,
                    "request_observada": obj.get("request_observada"),
                    "capturado_em": obj.get("capturado_em"),
                    "sha256": sha256(path),
                    "n": len(part),
                    "ranking_min": min(r["ranking_campeonato"] for r in part),
                    "ranking_max": max(r["ranking_campeonato"] for r in part),
                }
            )
        except (ValueError, json.JSONDecodeError) as exc:
            errors.append(str(exc))

    rows.sort(key=lambda r: r["ranking_campeonato"])
    sources.sort(key=lambda s: s["pagina"])
    ids = [r["time_id"] for r in rows]
    ranks = [r["ranking_campeonato"] for r in rows]

    pages_ok = seen_pages == {1, 2} and len(sources) == 2
    exact = (
        not errors
        and pages_ok
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
        "paginas_validas": sorted(seen_pages),
        "paginas_esperadas": [1, 2],
        "paginas_completas": pages_ok,
        "registros": len(rows),
        "time_id_unicos": len(set(ids)),
        "ranking_min": min(ranks) if ranks else None,
        "ranking_max": max(ranks) if ranks else None,
        "ranking_continuo_1_50": ranks == list(range(1, 51)),
        "credenciais_ausentes": not any("credencial/sessão" in e for e in errors),
        "erros": errors,
        "snapshots": sources,
        "proximo_passo": (
            "Coorte pronta para validação/análise histórica."
            if exact
            else "Aguardar captura sanitizada da página faltante até completar rankings 1-50; não promover coorte parcial."
        ),
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
