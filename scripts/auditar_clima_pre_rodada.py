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

    for path in files:
        data = load(path)
        captured = parse_dt(data.get("capturado_em"))
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

        for row in rows:
            kickoff = parse_dt(row.get("partida_data"))
            if kickoff is None:
                row_errors.append(f"partida_{row.get('partida_id')}_sem_data")
                continue
            if captured is not None and captured >= kickoff:
                row_errors.append(f"partida_{row.get('partida_id')}_capturada_apos_inicio")
            for key in ("temperature_2m", "apparent_temperature", "precipitation_probability", "relative_humidity_2m", "wind_speed_10m"):
                if row.get(key) is None:
                    row_errors.append(f"partida_{row.get('partida_id')}_sem_{key}")

        # Mais de um commit tocando o snapshot indica regravação e viola imutabilidade.
        # Zero commits é permitido durante a própria execução que acaba de criar o arquivo.
        if len(commits) > 1:
            row_errors.append("snapshot_regravado_no_git")

        if row_errors:
            violations.extend({"arquivo": str(path.relative_to(ROOT)), "erro": e} for e in sorted(set(row_errors)))

        details.append({
            "arquivo": str(path.relative_to(ROOT)),
            "rodada": data.get("rodada"),
            "capturado_em": data.get("capturado_em"),
            "partidas": len(rows),
            "hash_ok": expected_hash == actual_hash,
            "commits_git": len(commits),
            "imutavel": len(commits) <= 1,
            "erros": sorted(set(row_errors)),
        })

    rounds = sorted({int(x["rodada"]) for x in details if x.get("rodada") is not None})
    n_matches = sum(int(x["partidas"]) for x in details)
    if violations:
        status = "REPROVADA"
        decision = "BLOQUEAR_CLIMA"
    elif len(rounds) >= 5 and n_matches >= 40:
        status = "APROVADA"
        decision = "AMOSTRA_MINIMA_PARA_ABLATION_PROSPECTIVA"
    elif files:
        status = "APROVADA"
        decision = "ACUMULAR_AMOSTRA_PROSPECTIVA"
    else:
        status = "SEM_SNAPSHOTS"
        decision = "AGUARDAR_PREVISOES_PRE_RODADA"

    payload = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "decisao": decision,
        "rodadas_com_snapshot": len(rounds),
        "rodadas": rounds,
        "partidas_com_forecast": n_matches,
        "violacoes": violations,
        "snapshots": details,
        "gate_amostra": {"min_rodadas": 5, "min_partidas": 40},
        "protocolo": (
            "Clima só pode ser avaliado com previsões meteorológicas congeladas antes da partida. "
            "É proibido usar clima observado pós-jogo como substituto retrospectivo, pois isso não reproduz a informação disponível na decisão pré-rodada."
        ),
        "proximo_passo": (
            "Ao atingir 5 rodadas e 40 partidas prospectivas, rodar BASE x CLIMA em walk-forward/rolling holdout sem alterar snapshots anteriores."
        ),
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Clima: {status} | {decision} | rodadas={len(rounds)} partidas={n_matches} violações={len(violations)}")
    if violations:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
