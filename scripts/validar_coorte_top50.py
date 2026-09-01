#!/usr/bin/env python3
"""Valida e congela a coorte oficial Top 25 da Nacional.

O nome de arquivo legado ``top50-atual.json`` é preservado para compatibilidade
com o pipeline, mas o alvo científico final do laboratório passou a ser Top 25.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
BASE_DIR = ROOT / "data" / "raw" / "top50-liga-nacional"
COHORT = BASE_DIR / "top50-atual.json"
SNAPSHOT_DIR = BASE_DIR / "snapshots"
REPORT = ROOT / "data" / "reports" / "top50-liga-nacional-coorte.json"
COHORT_SIZE = 25
ALLOWED_HOSTS = {"api.cartolafc.globo.com", "api.cartola.globo.com", "cartolafc.globo.com", "ge.globo.com", "globoesporte.globo.com"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_report(payload: dict[str, Any]) -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def fail(reason: str, details: dict[str, Any] | None = None) -> None:
    write_report({"gerado_em": now_iso(), "status": "COORTE_REPROVADA", "motivo": reason, "detalhes": details or {}, "apta_para_analise": False})
    raise SystemExit(reason)


def canonical_team(team: dict[str, Any]) -> dict[str, Any]:
    return {"time_id": team.get("time_id"), "ranking_campeonato": team.get("ranking_campeonato"), "nome": team.get("nome"), "pontos_campeonato": team.get("pontos_campeonato")}


def cohort_hash(teams: list[dict[str, Any]]) -> str:
    raw = json.dumps([canonical_team(t) for t in teams], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def safe_capture_stamp(value: str) -> str:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        fail("capturado_em não está em ISO-8601", {"capturado_em": value})
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def validate_source(source: Any) -> tuple[str, str]:
    if not isinstance(source, dict):
        fail("fonte/proveniência ausente")
    name, url = str(source.get("nome") or "").strip(), str(source.get("url") or "").strip()
    if not name or not url:
        fail("fonte precisa conter nome e URL")
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or host not in ALLOWED_HOSTS:
        fail("URL da fonte não pertence à allowlist oficial", {"host": host, "url": url})
    return name, url


def validate_identity(obj: dict[str, Any]) -> dict[str, Any]:
    liga = obj.get("liga")
    if not isinstance(liga, dict):
        fail("identidade da liga oficial ausente")
    nome, categoria, tipo = str(liga.get("nome") or "").strip(), str(liga.get("categoria_interface") or "").strip(), str(liga.get("tipo_interface") or "").strip()
    if nome.casefold() != "nacional" or categoria.casefold() != "ligas do cartola":
        fail("identidade da Nacional oficial inválida", {"nome": nome, "categoria": categoria})
    if tipo and tipo.casefold() != "clássica":
        fail("tipo da liga oficial inesperado", {"tipo": tipo})
    return {"nome": nome, "categoria_interface": categoria, "tipo_interface": tipo or None}


def main() -> None:
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    if not COHORT.exists():
        write_report({
            "gerado_em": now_iso(), "status": "AGUARDANDO_COORTE_AUDITAVEL", "apta_para_analise": False,
            "alvo": "Top 25 Nacional", "motivo": "arquivo de coorte ainda não foi promovido pelo gate de importação",
            "regras": {"exatamente_25_times": True, "time_id_unico": True, "ranking_1_25": True, "proveniencia_obrigatoria": True, "snapshot_sha256": True},
        })
        return
    try:
        obj = json.loads(COHORT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail("arquivo da coorte inválido", {"erro": str(exc)})
    identity = validate_identity(obj)
    captured = obj.get("capturado_em")
    if not isinstance(captured, str) or not captured.strip():
        fail("capturado_em ausente")
    stamp = safe_capture_stamp(captured)
    source_name, source_url = validate_source(obj.get("fonte"))
    teams = obj.get("top50")
    if not isinstance(teams, list) or len(teams) != COHORT_SIZE:
        fail("coorte deve conter exatamente 25 times", {"quantidade": len(teams) if isinstance(teams, list) else None})
    ids, ranks = [], []
    for index, team in enumerate(teams, start=1):
        if not isinstance(team, dict) or team.get("time_id") is None:
            fail("time sem time_id", {"posicao_lista": index})
        ids.append(str(team["time_id"]))
        ranks.append(team.get("ranking_campeonato"))
    if len(set(ids)) != COHORT_SIZE:
        fail("time_id duplicado na coorte", {"unicos": len(set(ids))})
    if ranks != list(range(1, COHORT_SIZE + 1)):
        fail("ranking oficial deve ser exatamente 1..25", {"ranks": ranks})
    sha = cohort_hash(teams)
    frozen = SNAPSHOT_DIR / f"top25-{stamp}-{sha[:12]}.json"
    frozen_payload = {
        "schema_version": 3, "congelado_em": now_iso(), "capturado_em": captured,
        "liga": identity, "fonte": {"nome": source_name, "url": source_url},
        "coorte_sha256": sha, "n": COHORT_SIZE, "top25": teams,
    }
    encoded = json.dumps(frozen_payload, ensure_ascii=False, indent=2)
    if frozen.exists():
        old = json.loads(frozen.read_text(encoding="utf-8"))
        if old.get("coorte_sha256") != sha:
            fail("colisão/inconsistência em snapshot já congelado")
    else:
        frozen.write_text(encoded, encoding="utf-8")
    report = {
        "gerado_em": now_iso(), "status": "COORTE_TOP25_APROVADA_E_CONGELADA", "apta_para_analise": True,
        "liga": identity, "capturado_em": captured, "fonte": {"nome": source_name, "url": source_url},
        "n": COHORT_SIZE, "time_ids_unicos": COHORT_SIZE, "coorte_sha256": sha,
        "snapshot_imutavel": str(frozen.relative_to(ROOT)), "validacao_ranking": {"ranking_validado": True, "faixa": [1, 25]},
        "uso_permitido": "estudo comportamental descritivo; não usar como feature nem prova causal do V3",
        "decisao_metodologica": "Top 25 oficial encerra o gate da coorte; posições 26-50 não são mais requisito.",
    }
    write_report(report)
    print(json.dumps({"status": report["status"], "sha256": sha, "snapshot": str(frozen.relative_to(ROOT))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
