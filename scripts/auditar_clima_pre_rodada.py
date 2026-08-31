#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAPDIR = ROOT / "predictions" / "clima"
OUT = ROOT / "data" / "reports" / "auditoria-clima-pre-rodada.json"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def parse_dt(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def canonical_hash(data):
    base = dict(data)
    base.pop("sha256_payload", None)
    raw = json.dumps(base, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def git_commits(path: Path):
    try:
        out = subprocess.check_output(
            ["git", "log", "--format=%H", "--", str(path.relative_to(ROOT))],
            cwd=ROOT, text=True, stderr=subprocess.DEVNULL,
        )
        return [x.strip() for x in out.splitlines() if x.strip()]
    except Exception:
        return []


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    files = sorted(SNAPDIR.glob("2026-r*.json")) if SNAPDIR.exists() else []
    details, violations = [], []
    eligible_rounds, eligible_matches = set(), 0
    legacy = []

    for path in files:
        data = load(path)
        captured = parse_dt(data.get("capturado_em"))
        deadline = parse_dt(data.get("limite_decisao"))
        eligible = data.get("elegivel_pre_rodada") is True
        rows = data.get("partidas", []) if isinstance(data.get("partidas"), list) else []
        expected_hash = data.get("sha256_payload")
        actual_hash = canonical_hash(data)
        commits = git_commits(path)
        row_errors = []

        if data.get("natureza") != "PREVISAO_METEOROLOGICA_PRE_RODADA":
            row_errors.append("natureza_invalida")
        if expected_hash != actual_hash:
            row_errors.append("hash_invalido")
        if captured is None:
            row_errors.append("captura_sem_timestamp")

        # Snapshots anteriores ao novo guardrail permanecem imutáveis e auditáveis,
        # mas não contam para o gate científico PRE-RODADA.
        if eligible:
            if deadline is None:
                row_errors.append("snapshot_elegivel_sem_limite_decisao")
            elif captured is not None and captured >= deadline:
                row_errors.append("captura_apos_fechamento_mercado")
        else:
            legacy.append(str(path.relative_to(ROOT)))

        for row in rows:
            kickoff = parse_dt(row.get("partida_data"))
            if kickoff is None:
                row_errors.append(f"partida_{row.get('partida_id')}_sem_data")
                continue
            if captured is not None and captured >= kickoff:
                row_errors.append(f"partida_{row.get('partida_id')}_capturada_apos_inicio")
            for key in (
                "temperature_2m", "apparent_temperature", "precipitation_probability",
                "relative_humidity_2m", "wind_speed_10m",
            ):
                if row.get(key) is None:
                    row_errors.append(f"partida_{row.get('partida_id')}_sem_{key}")

        if len(commits) > 1:
            row_errors.append("snapshot_regravado_no_git")

        if row_errors:
            violations.extend(
                {"arquivo": str(path.relative_to(ROOT)), "erro": e}
                for e in sorted(set(row_errors))
            )

        if eligible and not row_errors:
            try:
                eligible_rounds.add(int(data.get("rodada")))
            except Exception:
                row_errors.append("rodada_invalida")
            eligible_matches += len(rows)

        details.append({
            "arquivo": str(path.relative_to(ROOT)), "rodada": data.get("rodada"),
            "capturado_em": data.get("capturado_em"), "limite_decisao": data.get("limite_decisao"),
            "elegivel_pre_rodada": eligible, "partidas": len(rows),
            "hash_ok": expected_hash == actual_hash, "commits_git": len(commits),
            "imutavel": len(commits) <= 1, "erros": sorted(set(row_errors)),
        })

    if violations:
        status, decision = "REPROVADA", "BLOQUEAR_CLIMA"
    elif len(eligible_rounds) >= 5 and eligible_matches >= 40:
        status, decision = "APROVADA", "AMOSTRA_MINIMA_PARA_ABLATION_PROSPECTIVA"
    elif files:
        status, decision = "APROVADA", "ACUMULAR_AMOSTRA_PROSPECTIVA"
    else:
        status, decision = "SEM_SNAPSHOTS", "AGUARDAR_PREVISOES_PRE_RODADA"

    payload = {
        "gerado_em": datetime.now(timezone.utc).isoformat(), "status": status, "decisao": decision,
        "rodadas_elegiveis_pre_rodada": len(eligible_rounds), "rodadas": sorted(eligible_rounds),
        "partidas_elegiveis_com_forecast": eligible_matches,
        "snapshots_legado_pre_jogo_fora_do_gate": legacy,
        "violacoes": violations, "snapshots": details,
        "gate_amostra": {"min_rodadas": 5, "min_partidas": 40},
        "protocolo": (
            "Clima só entra no gate se a previsão foi congelada antes do fechamento oficial do mercado da rodada. "
            "Snapshots apenas pré-jogo, sem prova de captura pré-fechamento, são preservados mas excluídos do gate."
        ),
        "proximo_passo": (
            "Acumular 5 rodadas e 40 partidas elegíveis e então rodar BASE x CLIMA em avaliação prospectiva."
        ),
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"Clima: {status} | {decision} | rodadas_elegiveis={len(eligible_rounds)} "
        f"partidas_elegiveis={eligible_matches} legado={len(legacy)} violações={len(violations)}"
    )
    if violations:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
