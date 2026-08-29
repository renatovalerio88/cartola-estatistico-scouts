#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
ARCHIVE = ROOT / "predictions" / "pre_round" / "2026"
GENERATOR = ROOT / "scripts" / "gerar_previsao_pre_rodada.py"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def detectar_rodada_aberta():
    candidatas = []
    for folder in RAW.glob("rodada-*"):
        try:
            rodada = int(folder.name.split("-")[-1])
        except ValueError:
            continue
        resumo = folder / "resumo.json"
        pontuados = folder / "pontuados.json"
        jogadores = folder / "jogadores.json"
        if not resumo.exists() or not jogadores.exists():
            continue
        try:
            r = load(resumo)
        except Exception:
            continue
        if int(r.get("statusMercado") or 0) != 1:
            continue
        tem_resultado = False
        if pontuados.exists():
            try:
                p = load(pontuados)
                if isinstance(p, dict):
                    tem_resultado = bool(p.get("atletas", p))
                elif isinstance(p, list):
                    tem_resultado = bool(p)
            except Exception:
                pass
        if not tem_resultado:
            candidatas.append(rodada)
    return max(candidatas) if candidatas else None


def main():
    rodada = detectar_rodada_aberta()
    if rodada is None:
        print("Nenhuma rodada aberta sem resultado; nada a congelar.")
        return

    csv_path = ARCHIVE / f"R{rodada:02d}.csv"
    manifest_path = ARCHIVE / f"R{rodada:02d}.manifest.json"

    if csv_path.exists() or manifest_path.exists():
        if not csv_path.exists() or not manifest_path.exists():
            raise SystemExit(
                f"LOCK INCONSISTENTE R{rodada:02d}: CSV e manifest devem existir juntos"
            )
        manifest = load(manifest_path)
        expected = manifest.get("csv_sha256")
        actual = sha256(csv_path)
        if not expected or actual != expected:
            raise SystemExit(
                f"LOCK CORROMPIDO R{rodada:02d}: hash armazenado não confere com CSV"
            )
        print(
            f"LOCK R{rodada:02d} já existe e foi validado ({actual[:12]}...). "
            "Snapshot original preservado; nenhuma recomputação permitida."
        )
        return

    subprocess.run([sys.executable, str(GENERATOR)], check=True, cwd=ROOT)


if __name__ == "__main__":
    main()
