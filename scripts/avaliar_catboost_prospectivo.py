#!/usr/bin/env python3
"""Avalia sidecars CatBoost prospectivos somente apos a rodada estar resolvida."""
from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from scripts.avaliar_previsoes_prospectivas import carregar_pontuados, metricas, numero

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "predictions" / "pre_round" / "2026"
OUT = ROOT / "data" / "reports" / "avaliacao-prospectiva-catboost-imutavel.json"
MIN_PONTUADOS = 100
COL = "v3s_catboost_nested"


def carregar_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def avaliar_metricas(rows: list[dict], somente_entrou: bool) -> dict:
    y, p = [], []
    for row in rows:
        if somente_entrou and not row["entrou_em_campo"]:
            continue
        pred = row.get("pred")
        if pred is None:
            continue
        y.append(row["real"])
        p.append(pred)
    return metricas(y, p)


def avaliar_rodada(manifest_path: Path) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rodada = int(manifest["rodada"])
    temporada = int(manifest.get("temporada", 2026))
    csv_path = manifest_path.with_name(f"R{rodada:02d}.catboost.csv")
    if not csv_path.exists():
        raise SystemExit(f"Sidecar CatBoost sem CSV em R{rodada:02d}")
    atual = sha256(csv_path)
    esperado = manifest.get("csv_sha256")
    if not esperado or atual != esperado:
        raise SystemExit(f"Hash invalido do sidecar CatBoost em R{rodada:02d}")

    pontuados = carregar_pontuados(rodada)
    if len(pontuados) < MIN_PONTUADOS:
        return {
            "temporada": temporada,
            "rodada": rodada,
            "status": "AGUARDANDO_RESULTADO",
            "pontuados_disponiveis": len(pontuados),
            "hash_validado": True,
        }

    linhas = []
    for row in carregar_csv(csv_path):
        try:
            aid = int(row.get("atleta_id", ""))
        except (TypeError, ValueError):
            continue
        pred = numero(row.get(COL))
        if pred is None:
            continue
        item = pontuados.get(aid)
        linhas.append({
            "atleta_id": aid,
            "posicao": str(row.get("posicao") or "").upper(),
            "pred": pred,
            "real": float(item["real"]) if item else 0.0,
            "entrou_em_campo": bool(item and item["entrou_em_campo"]),
        })

    por_posicao = {}
    for pos in sorted({r["posicao"] for r in linhas if r["posicao"]}):
        g = [r for r in linhas if r["posicao"] == pos]
        por_posicao[pos] = {
            "todos_snapshot": avaliar_metricas(g, False),
            "somente_entrou_em_campo": avaliar_metricas(g, True),
        }

    return {
        "temporada": temporada,
        "rodada": rodada,
        "status": "AVALIADA",
        "hash_validado": True,
        "jogadores_snapshot": len(linhas),
        "geral": {
            "todos_snapshot": avaliar_metricas(linhas, False),
            "somente_entrou_em_campo": avaliar_metricas(linhas, True),
        },
        "por_posicao": por_posicao,
    }


def consolidar(avaliadas: list[dict]) -> dict:
    if not avaliadas:
        return {
            "rodadas_avaliadas": 0,
            "status": "SEM_RESULTADO_PROSPECTIVO_FECHADO",
            "regra_promocao": "nenhuma decisao retrospectiva pode substituir evidencia prospectiva ausente",
        }
    out = {"rodadas_avaliadas": len(avaliadas), "rodadas": [r["rodada"] for r in avaliadas]}
    for universo in ("todos_snapshot", "somente_entrou_em_campo"):
        maes = []
        ns = []
        for rodada in avaliadas:
            m = rodada["geral"][universo]
            if m.get("n", 0) and m.get("mae") is not None:
                maes.append(float(m["mae"]))
                ns.append(int(m["n"]))
        out[universo] = {
            "mae_medio_por_rodada": round(float(np.mean(maes)), 6) if maes else None,
            "mae_ponderado_por_jogadores": round(float(np.average(maes, weights=ns)), 6) if maes else None,
            "rodadas": len(maes),
            "jogadores_avaliados_soma": int(sum(ns)),
        }
    out["status"] = "EVIDENCIA_PROSPECTIVA_EM_ACUMULO"
    return out


def main() -> int:
    rodadas = [avaliar_rodada(p) for p in sorted(ARCHIVE.glob("R??.catboost.manifest.json"))]
    avaliadas = [r for r in rodadas if r.get("status") == "AVALIADA"]
    payload = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "objetivo": "placar prospectivo puro do challenger CatBoost nested congelado antes da rodada",
        "protocolo": (
            "cada sidecar e imutavel por SHA-256; previsao usa apenas informacao disponivel antes da rodada; "
            "resultado so entra depois de pontuados.json plausivelmente completo; nenhuma recalibracao retroativa"
        ),
        "modelo": COL,
        "rodadas": rodadas,
        "consolidado": consolidar(avaliadas),
        "v2_producao_alterada": False,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    aguardando = sum(r.get("status") == "AGUARDANDO_RESULTADO" for r in rodadas)
    print(f"CatBoost prospectivo: avaliadas={len(avaliadas)} aguardando={aguardando}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
