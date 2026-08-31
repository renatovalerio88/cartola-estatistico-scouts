#!/usr/bin/env python3
"""Valida e congela snapshots auditáveis da coorte Top 50 da Liga Nacional.

O estudo Top 50 só pode avançar quando ``top50-atual.json`` vier de uma fonte
oficial/reproduzível já aprovada pela auditoria. Este módulo adiciona uma
segunda barreira independente antes da análise histórica:

- exige exatamente 50 ``time_id`` únicos;
- exige proveniência e instante de captura;
- rejeita URLs fora dos domínios oficiais usados pelo Cartola/Globo;
- valida ranking 1..50 quando o ranking é fornecido em massa;
- gera SHA-256 canônico da coorte;
- congela um snapshot imutável por captura/hash;
- nunca cria uma coorte sintética nem usa popularidade como proxy.

Se ainda não houver coorte, o script registra o bloqueio e termina com sucesso.
Isso mantém o workflow saudável sem transformar ausência legítima de fonte em
falha operacional.
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

ALLOWED_HOSTS = {
    "api.cartolafc.globo.com",
    "cartolafc.globo.com",
    "ge.globo.com",
    "globoesporte.globo.com",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_report(payload: dict[str, Any]) -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def fail(reason: str, details: dict[str, Any] | None = None) -> None:
    payload = {
        "gerado_em": now_iso(),
        "status": "COORTE_REPROVADA",
        "motivo": reason,
        "detalhes": details or {},
        "apta_para_analise": False,
    }
    write_report(payload)
    raise SystemExit(reason)


def canonical_team(team: dict[str, Any]) -> dict[str, Any]:
    return {
        "time_id": team.get("time_id"),
        "ranking_campeonato": team.get("ranking_campeonato"),
        "nome": team.get("nome"),
        "pontos_campeonato": team.get("pontos_campeonato"),
    }


def cohort_hash(teams: list[dict[str, Any]]) -> str:
    canonical = [canonical_team(t) for t in teams]
    raw = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
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
    name = str(source.get("nome") or "").strip()
    url = str(source.get("url") or "").strip()
    if not name or not url:
        fail("fonte precisa conter nome e URL")
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or host not in ALLOWED_HOSTS:
        fail("URL da fonte não pertence à allowlist oficial", {"host": host, "url": url})
    return name, url


def validate_ranks(teams: list[dict[str, Any]]) -> dict[str, Any]:
    ranks = [t.get("ranking_campeonato") for t in teams]
    numeric = [int(r) for r in ranks if isinstance(r, (int, float)) and float(r).is_integer()]
    if len(numeric) >= 40:
        if len(numeric) != 50 or set(numeric) != set(range(1, 51)):
            fail(
                "ranking oficial presente, mas não representa exatamente posições 1..50",
                {"quantidade_ranks": len(numeric), "ranks_unicos": len(set(numeric))},
            )
        return {"ranking_validado": True, "faixa": [1, 50]}
    return {
        "ranking_validado": False,
        "observacao": "ranking individual insuficiente; coorte depende da ordem oficial preservada pela fonte auditada",
    }


def main() -> None:
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

    if not COHORT.exists():
        report = {
            "gerado_em": now_iso(),
            "status": "AGUARDANDO_COORTE_AUDITAVEL",
            "apta_para_analise": False,
            "motivo": "top50-atual.json ainda não existe porque nenhuma fonte pública oficial foi confirmada",
            "regras": {
                "exatamente_50_times": True,
                "time_id_unico": True,
                "proveniencia_obrigatoria": True,
                "snapshot_sha256": True,
                "sem_proxy_popularidade": True,
            },
        }
        write_report(report)
        print(json.dumps({"status": report["status"], "report": str(REPORT.relative_to(ROOT))}, ensure_ascii=False))
        return

    try:
        obj = json.loads(COHORT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail("arquivo da coorte inválido", {"erro": str(exc)})

    captured = obj.get("capturado_em")
    if not isinstance(captured, str) or not captured.strip():
        fail("capturado_em ausente")
    stamp = safe_capture_stamp(captured)
    source_name, source_url = validate_source(obj.get("fonte"))

    teams = obj.get("top50")
    if not isinstance(teams, list) or len(teams) != 50:
        fail("coorte deve conter exatamente 50 times", {"quantidade": len(teams) if isinstance(teams, list) else None})

    ids = []
    for index, team in enumerate(teams, start=1):
        if not isinstance(team, dict) or team.get("time_id") is None:
            fail("time sem time_id", {"posicao_lista": index})
        ids.append(str(team["time_id"]))
    if len(set(ids)) != 50:
        fail("time_id duplicado na coorte", {"unicos": len(set(ids))})

    rank_validation = validate_ranks(teams)
    sha = cohort_hash(teams)
    frozen_name = f"top50-{stamp}-{sha[:12]}.json"
    frozen = SNAPSHOT_DIR / frozen_name

    frozen_payload = {
        "schema_version": 1,
        "congelado_em": now_iso(),
        "capturado_em": captured,
        "fonte": {"nome": source_name, "url": source_url},
        "coorte_sha256": sha,
        "n": 50,
        "top50": teams,
    }
    encoded = json.dumps(frozen_payload, ensure_ascii=False, indent=2)
    if frozen.exists():
        old = json.loads(frozen.read_text(encoding="utf-8"))
        if old.get("coorte_sha256") != sha:
            fail("colisão/inconsistência em snapshot já congelado", {"arquivo": str(frozen.relative_to(ROOT))})
    else:
        frozen.write_text(encoded, encoding="utf-8")

    report = {
        "gerado_em": now_iso(),
        "status": "COORTE_APROVADA_E_CONGELADA",
        "apta_para_analise": True,
        "capturado_em": captured,
        "fonte": {"nome": source_name, "url": source_url},
        "n": 50,
        "time_ids_unicos": 50,
        "coorte_sha256": sha,
        "snapshot_imutavel": str(frozen.relative_to(ROOT)),
        "validacao_ranking": rank_validation,
        "uso_permitido": "estudo comportamental descritivo; não usar como feature nem prova causal do V3",
    }
    write_report(report)
    print(json.dumps({"status": report["status"], "sha256": sha, "snapshot": str(frozen.relative_to(ROOT))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
