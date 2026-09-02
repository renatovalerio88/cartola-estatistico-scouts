#!/usr/bin/env python3
"""Audita snapshots pré-rodada imutáveis do laboratório Scouts V3.

Regras:
- cada Rxx.manifest.json deve ter CSV correspondente;
- hash SHA-256 do CSV deve coincidir com o manifesto;
- rodada/temporada e contagem de jogadores devem ser coerentes;
- nenhum atleta pode aparecer duplicado no snapshot;
- colunas essenciais de previsão e contexto pré-rodada devem existir;
- cada CSV e manifesto devem ter sido adicionados uma única vez no histórico Git,
  nunca modificados depois do primeiro commit.

O script não altera snapshots. Gera apenas um relatório de auditoria.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRED_ROOT = ROOT / "predictions" / "pre_round"
REPORT = ROOT / "data" / "reports" / "auditoria-previsoes-imutaveis.json"
ROUND_RE = re.compile(r"^R(\d+)\.manifest\.json$")
REQUIRED_COLUMNS = {
    "atleta_id",
    "apelido",
    "posicao",
    "clube_id",
    "status_id",
    "rodada",
    "v3s_expected_scouts",
    "direta_rf_lab",
    "v3h_hibrido",
}
NUMERIC_PREDICTIONS = ("v3s_expected_scouts", "direta_rf_lab", "v3h_hibrido")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def git_commits_touching(path: Path) -> list[str]:
    rel = path.relative_to(ROOT).as_posix()
    proc = subprocess.run(
        ["git", "log", "--follow", "--format=%H", "--", rel],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def audit_snapshot(manifest_path: Path) -> dict:
    match = ROUND_RE.match(manifest_path.name)
    assert match is not None
    rodada_nome = int(match.group(1))
    temporada = int(manifest_path.parent.name)
    csv_path = manifest_path.with_name(f"R{rodada_nome}.csv")

    erros: list[str] = []
    avisos: list[str] = []

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "temporada": temporada,
            "rodada": rodada_nome,
            "manifest": manifest_path.relative_to(ROOT).as_posix(),
            "status": "REPROVADA",
            "erros": [f"manifesto inválido: {exc}"],
        }

    if not csv_path.exists():
        erros.append("CSV correspondente ausente")
        rows = []
        fieldnames = []
    else:
        with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or []
            rows = list(reader)

    rodada_manifest = manifest.get("rodada")
    if rodada_manifest != rodada_nome:
        erros.append(f"rodada do manifesto={rodada_manifest!r} difere do nome R{rodada_nome}")

    csv_decl = manifest.get("csv")
    csv_rel = csv_path.relative_to(ROOT).as_posix()
    if csv_decl != csv_rel:
        erros.append(f"caminho CSV declarado={csv_decl!r} difere de {csv_rel!r}")

    if csv_path.exists():
        hash_real = sha256(csv_path)
        hash_manifest = manifest.get("csv_sha256")
        if hash_manifest != hash_real:
            erros.append("SHA-256 do CSV difere do manifesto")
    else:
        hash_real = None
        hash_manifest = manifest.get("csv_sha256")

    faltantes = sorted(REQUIRED_COLUMNS - set(fieldnames))
    if faltantes:
        erros.append(f"colunas obrigatórias ausentes: {faltantes}")

    if rows:
        rodadas_csv = {r.get("rodada", "").strip() for r in rows}
        if rodadas_csv != {str(rodada_nome)}:
            erros.append(f"CSV contém rodadas incompatíveis: {sorted(rodadas_csv)}")

        ids = [r.get("atleta_id", "").strip() for r in rows]
        ids_validos = [x for x in ids if x]
        if len(ids_validos) != len(set(ids_validos)):
            erros.append("há atleta_id duplicado no snapshot")

        for col in NUMERIC_PREDICTIONS:
            if col not in fieldnames:
                continue
            invalidos = 0
            for row in rows:
                try:
                    v = float(row[col])
                    if not math.isfinite(v):
                        invalidos += 1
                except Exception:
                    invalidos += 1
            if invalidos:
                erros.append(f"{col}: {invalidos} valores não numéricos/finitos")

    declarados = manifest.get("jogadores_previstos")
    if declarados is not None and declarados != len(rows):
        erros.append(f"jogadores_previstos={declarados} mas CSV possui {len(rows)} linhas")

    protocolo = str(manifest.get("protocolo", "")).lower()
    if "imut" not in protocolo:
        avisos.append("manifesto não explicita imutabilidade no protocolo")
    if "exclusivamente" not in protocolo and "< r" not in protocolo:
        avisos.append("manifesto não explicita claramente o corte temporal R-1")

    gerado = manifest.get("gerado_em_utc")
    if gerado:
        try:
            datetime.fromisoformat(str(gerado).replace("Z", "+00:00"))
        except Exception:
            erros.append("gerado_em_utc inválido")
    else:
        avisos.append("gerado_em_utc ausente")

    historico_git = {}
    for p in (csv_path, manifest_path):
        if not p.exists():
            continue
        try:
            commits = git_commits_touching(p)
            historico_git[p.relative_to(ROOT).as_posix()] = commits
            if not commits:
                erros.append(f"{p.name}: arquivo não aparece no histórico Git")
            elif len(commits) > 1:
                erros.append(
                    f"{p.name}: snapshot foi alterado após criação ({len(commits)} commits tocaram o arquivo)"
                )
        except Exception as exc:
            erros.append(f"falha ao auditar histórico Git de {p.name}: {exc}")

    return {
        "temporada": temporada,
        "rodada": rodada_nome,
        "manifest": manifest_path.relative_to(ROOT).as_posix(),
        "csv": csv_rel,
        "linhas": len(rows),
        "csv_sha256_manifest": hash_manifest,
        "csv_sha256_real": hash_real,
        "historico_git": historico_git,
        "avisos": avisos,
        "erros": erros,
        "status": "APROVADA" if not erros else "REPROVADA",
    }


def main() -> int:
    # O sidecar CatBoost usa Rxx.catboost.manifest.json e possui auditoria/hash próprios.
    # Este auditor deve validar somente o lock principal Rxx.manifest.json.
    manifests = sorted(
        path
        for path in PRED_ROOT.glob("*/R*.manifest.json")
        if ROUND_RE.match(path.name)
    )
    snapshots = [audit_snapshot(path) for path in manifests]
    reprovados = [s for s in snapshots if s.get("status") != "APROVADA"]

    relatorio = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "escopo": "integridade e imutabilidade das previsões pré-rodada do Scouts V3",
        "regra": "snapshot pré-rodada é append-only: CSV/manifesto podem ser criados uma vez e jamais regravados",
        "snapshots_encontrados": len(snapshots),
        "snapshots_aprovados": len(snapshots) - len(reprovados),
        "snapshots_reprovados": len(reprovados),
        "status": "APROVADA" if snapshots and not reprovados else "REPROVADA",
        "snapshots": snapshots,
        "observacao": "A auditoria não modifica previsões e não acessa a V2.",
    }

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        f"Auditoria previsões imutáveis: {relatorio['status']} | "
        f"snapshots={len(snapshots)} | reprovados={len(reprovados)}"
    )
    if not snapshots:
        print("Nenhum snapshot pré-rodada encontrado.")
        return 1
    if reprovados:
        for snap in reprovados:
            print(f"R{snap['rodada']}: " + "; ".join(snap.get("erros", [])))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
