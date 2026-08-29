#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "derived" / "dataset-walk-forward.csv"
OUT = ROOT / "data" / "reports" / "auditoria-vazamento-temporal.json"
SCOUTS = ["G","A","FT","FD","FF","FS","PS","I","DS","SG","DP","DE","GC","CV","CA","GS","FC","PC","PP"]
TOL = 1e-8


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
    df = pd.read_csv(DATA).sort_values(["rodada", "atleta_id"]).reset_index(drop=True)
    violations = []
    checks = 0

    # Reconstrói as features individuais exclusivamente com targets de rodadas anteriores.
    # Se uma feature tiver incorporado a própria rodada R ou futuro, este teste diverge e o pipeline falha.
    histories = {}
    for _, row in df.iterrows():
        aid = int(row.atleta_id)
        rodada = int(row.rodada)
        h = histories.setdefault(aid, {"pontos": [], **{s: [] for s in SCOUTS}})

        expected = {
            "historico_jogos": len(h["pontos"]),
            "pontos_media3": float(np.mean(h["pontos"][-3:])) if h["pontos"] else 0.0,
            "pontos_media5": float(np.mean(h["pontos"][-5:])) if h["pontos"] else 0.0,
            "pontos_ewma": ewma(h["pontos"][-20:]),
        }
        for s in SCOUTS:
            vals = h[s][-20:]
            expected[f"{s}_media3"] = float(np.mean(vals[-3:])) if vals else 0.0
            expected[f"{s}_media5"] = float(np.mean(vals[-5:])) if vals else 0.0
            expected[f"{s}_ewma"] = ewma(vals)

        for col, exp in expected.items():
            if col not in df.columns:
                continue
            checks += 1
            got = row[col]
            if pd.isna(got) or not close(got, exp):
                violations.append({
                    "rodada": rodada,
                    "atleta_id": aid,
                    "coluna": col,
                    "esperado_so_passado": round(float(exp), 10),
                    "encontrado": None if pd.isna(got) else round(float(got), 10),
                })
                if len(violations) >= 100:
                    break
        if len(violations) >= 100:
            break

        # O target só entra no histórico APÓS auditar as features da linha atual.
        h["pontos"].append(float(row.target_pontos))
        for s in SCOUTS:
            col = f"target_{s}"
            h[s].append(float(row[col]) if col in df.columns and not pd.isna(row[col]) else 0.0)

    round_order_ok = bool((df["rodada"] >= 1).all())
    payload = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "status": "APROVADA" if not violations and round_order_ok else "REPROVADA",
        "regra": "Para projetar a rodada R, toda feature deve ser calculada somente com rodadas < R.",
        "linhas_auditadas": int(len(df)),
        "checks_features": int(checks),
        "violacoes": violations,
        "violacoes_total_amostradas": len(violations),
        "observacao": "Auditoria reconstrói médias/EWMA do jogador a partir dos targets já vistos; a linha R é testada antes de inserir o target de R no histórico.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Auditoria temporal: {payload['status']} | {checks} checks | {len(violations)} violações")
    if payload["status"] != "APROVADA":
        raise SystemExit("Vazamento temporal detectado; pipeline interrompido.")


if __name__ == "__main__":
    main()
