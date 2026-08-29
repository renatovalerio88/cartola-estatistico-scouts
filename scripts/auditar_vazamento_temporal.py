#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
DATA = ROOT / "data" / "derived" / "dataset-walk-forward.csv"
OUT = ROOT / "data" / "reports" / "auditoria-vazamento-temporal.json"
SCOUTS = ["G","A","FT","FD","FF","FS","PS","I","DS","SG","DP","DE","GC","CV","CA","GS","FC","PC","PP"]
TOL = 1e-7


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def mean(values):
    return float(np.mean(values)) if values else 0.0


def ewma(values, alpha=.45):
    values = list(values)
    if not values:
        return 0.0
    acc = float(values[0])
    for x in values[1:]:
        acc = alpha * float(x) + (1 - alpha) * acc
    return acc


def close(a, b):
    return abs(float(a) - float(b)) <= TOL


def main():
    df = pd.read_csv(DATA)
    indexed = {(int(r.rodada), int(r.atleta_id)): r for _, r in df.iterrows()}
    history = defaultdict(lambda: {
        "pontos": deque(maxlen=20),
        "scouts": defaultdict(lambda: deque(maxlen=20)),
    })
    violations = []
    checks = 0
    rows_checked = 0

    # Refaz a cronologia a partir dos arquivos brutos, inclusive a primeira atuação
    # que propositalmente não aparece no dataset por ainda não possuir passado.
    for folder in sorted(RAW.glob("rodada-*")):
        pontuados = folder / "pontuados.json"
        if not pontuados.exists():
            continue
        rodada = int(folder.name.split("-")[-1])
        raw = load(pontuados)
        atletas = raw.get("atletas", raw if isinstance(raw, dict) else {})

        for aid_raw, atleta in atletas.items():
            if not isinstance(atleta, dict) or not atleta.get("entrou_em_campo", False):
                continue
            aid = int(aid_raw)
            h = history[aid]
            key = (rodada, aid)

            if len(h["pontos"]) >= 1:
                row = indexed.get(key)
                if row is None:
                    violations.append({"rodada": rodada, "atleta_id": aid, "tipo": "linha_esperada_ausente"})
                else:
                    rows_checked += 1
                    expected = {
                        "historico_jogos": len(h["pontos"]),
                        "pontos_media3": mean(list(h["pontos"])[-3:]),
                        "pontos_media5": mean(list(h["pontos"])[-5:]),
                        "pontos_ewma": ewma(list(h["pontos"])),
                    }
                    for scout in SCOUTS:
                        vals = list(h["scouts"][scout])
                        expected[f"{scout}_media3"] = mean(vals[-3:])
                        expected[f"{scout}_media5"] = mean(vals[-5:])
                        expected[f"{scout}_ewma"] = ewma(vals)

                    for col, exp in expected.items():
                        checks += 1
                        got = row[col]
                        if pd.isna(got) or not close(got, exp):
                            violations.append({
                                "rodada": rodada,
                                "atleta_id": aid,
                                "tipo": "feature_divergente",
                                "coluna": col,
                                "esperado_so_passado": round(float(exp), 10),
                                "encontrado": None if pd.isna(got) else round(float(got), 10),
                            })

            # Só depois de conferir a linha R, incorpora o resultado de R ao histórico.
            h["pontos"].append(float(atleta.get("pontuacao") or 0))
            current_scouts = atleta.get("scout") or {}
            for scout in SCOUTS:
                h["scouts"][scout].append(float(current_scouts.get(scout, 0) or 0))

            if len(violations) >= 100:
                break
        if len(violations) >= 100:
            break

    expected_keys = set(indexed)
    payload = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "status": "APROVADA" if not violations and rows_checked == len(expected_keys) else "REPROVADA",
        "regra_inviolavel": "Para projetar a rodada R, toda feature, treino, seleção e calibração deve usar somente rodadas < R.",
        "linhas_dataset": int(len(df)),
        "linhas_auditadas": int(rows_checked),
        "checks_features": int(checks),
        "violacoes": violations,
        "violacoes_total_amostradas": len(violations),
        "metodo": "Reconstrução cronológica desde data/raw; cada linha R é validada antes de inserir target/scouts de R no histórico.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Auditoria temporal: {payload['status']} | {rows_checked}/{len(df)} linhas | {checks} checks | {len(violations)} violações")
    if payload["status"] != "APROVADA":
        raise SystemExit("Vazamento temporal ou inconsistência cronológica detectada; pipeline interrompido.")


if __name__ == "__main__":
    main()
