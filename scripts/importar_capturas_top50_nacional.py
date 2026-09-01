#!/usr/bin/env python3
"""Importa a captura sanitizada dos Top 25 da classificação oficial Nacional.

Decisão metodológica final do laboratório: usar os 25 primeiros oficialmente
capturados como coorte descritiva suficiente, sem bloquear o fechamento do
laboratório pela ausência das posições 26-50.

Gate científico:
- exatamente a página 1 oficial;
- exatamente 25 registros;
- rankings contínuos 1..25;
- 25 ``time_id`` únicos;
- request observada com ``orderBy=campeonato`` e ``page=1``;
- origem explícita na interface oficial do Cartola;
- ausência de credenciais/sessão;
- SHA-256 da captura preservado na proveniência.
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
COHORT_SIZE = 25

FORBIDDEN_KEYS = {
    "authorization", "cookie", "cookies", "token", "access_token",
    "access-token", "refresh_token", "session", "sessionid", "jwt",
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
            found.extend(find_forbidden_keys(child, f"{prefix}[{idx}]"))
    return found


def load_page1(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if obj.get("sanitizado") is not True:
        raise ValueError("pagina-01: captura não marcada como sanitizada")
    forbidden = find_forbidden_keys(obj)
    if forbidden:
        raise ValueError("pagina-01: captura contém campos de credencial/sessão proibidos")
    origem = str(obj.get("origem") or "")
    if "Nacional" not in origem or "Cartola" not in origem:
        raise ValueError("pagina-01: origem oficial Nacional não identificada")
    if obj.get("pagina") != 1:
        raise ValueError("pagina-01: página declarada deve ser 1")
    request = str(obj.get("request_observada") or "").replace(" ", "")
    if "orderBy=campeonato" not in request or "page=1" not in request or "nacional" not in request.lower():
        raise ValueError("pagina-01: request oficial incompatível")
    rows = obj.get("times")
    if not isinstance(rows, list) or len(rows) != COHORT_SIZE:
        raise ValueError(f"pagina-01: esperado {COHORT_SIZE} times")
    clean: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("pagina-01: registro inválido")
        tid, rank = row.get("time_id"), row.get("ranking_campeonato")
        if not isinstance(tid, int) or not isinstance(rank, int):
            raise ValueError("pagina-01: time_id/ranking inválido")
        clean.append({
            "time_id": tid,
            "nome": row.get("nome"),
            "ranking_campeonato": rank,
            "pontos_campeonato": row.get("pontos_campeonato"),
            "patrimonio": row.get("patrimonio"),
        })
    clean.sort(key=lambda r: r["ranking_campeonato"])
    if [r["ranking_campeonato"] for r in clean] != list(range(1, COHORT_SIZE + 1)):
        raise ValueError("pagina-01: ranking deve cobrir continuamente 1..25")
    if len({r["time_id"] for r in clean}) != COHORT_SIZE:
        raise ValueError("pagina-01: time_id duplicado")
    return obj, clean


def main() -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    CAPTURES.mkdir(parents=True, exist_ok=True)
    path = CAPTURES / "pagina-01.json"
    errors: list[str] = []
    rows: list[dict[str, Any]] = []
    source: dict[str, Any] | None = None
    if not path.exists():
        errors.append("pagina-01.json ausente")
    else:
        try:
            obj, rows = load_page1(path)
            request = str(obj.get("request_observada") or "").lstrip("/")
            source = {
                "arquivo": str(path.relative_to(ROOT)),
                "pagina": 1,
                "request_observada": obj.get("request_observada"),
                "capturado_em": obj.get("capturado_em"),
                "sha256": sha256(path),
                "n": len(rows),
                "ranking_min": 1,
                "ranking_max": COHORT_SIZE,
            }
        except (ValueError, json.JSONDecodeError) as exc:
            errors.append(str(exc))

    exact = not errors and len(rows) == COHORT_SIZE and source is not None
    if exact:
        payload = {
            "capturado_em": source.get("capturado_em") or now_iso(),
            "liga": {"nome": "Nacional", "categoria_interface": "Ligas do Cartola", "tipo_interface": "Clássica"},
            "fonte": {
                "nome": "captura_browser_oficial_sanitizada",
                "url": f"https://api.cartolafc.globo.com/{str(source['request_observada']).lstrip('/')}",
                "snapshots": [source],
            },
            "tipo_coorte": "ranking_atual_congelado_top25",
            "n": COHORT_SIZE,
            "alerta": "Coorte atual Top 25; análise retrospectiva possui survivorship bias e é apenas descritiva.",
            "top50": rows,
        }
        OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        status = "COORTE_TOP25_PROMOVIDA"
    else:
        status = "COORTE_TOP25_REPROVADA"
        if OUT.exists():
            OUT.unlink()

    report = {
        "gerado_em": now_iso(), "status": status, "alvo_final": "Top 25 Nacional",
        "registros": len(rows), "time_id_unicos": len({r["time_id"] for r in rows}),
        "ranking_continuo_1_25": [r["ranking_campeonato"] for r in rows] == list(range(1, 26)),
        "erros": errors, "snapshot": source,
        "decisao_metodologica": "Top 25 oficial é suficiente para o estudo descritivo final; posições 26-50 não bloqueiam mais o laboratório.",
        "proximo_passo": "Validar/congelar coorte e reconstruir estratégias históricas." if exact else "Corrigir a captura oficial Top 25 antes da análise.",
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
