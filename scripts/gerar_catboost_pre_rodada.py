#!/usr/bin/env python3
"""Congela uma previsao CatBoost nested prospectiva em sidecar imutavel.

O snapshot principal do laboratorio ja e imutavel. Este sidecar existe para incluir o
challenger CatBoost nested nas validacoes prospectivas sem reescrever snapshots antigos.
Para uma rodada R, treino, selecao de modelo e validacao interna usam somente rodadas < R.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.backtest_v3s_catboost_nested import (
    POSITIONS,
    SCOUT_WEIGHTS,
    baseline_predict,
    choose_model,
    fit_predict,
)
from scripts.gerar_previsao_pre_rodada import detectar_rodada_aberta, montar_frame_atual

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "derived" / "dataset-walk-forward.csv"
ARCHIVE = ROOT / "predictions" / "pre_round" / "2026"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_csv(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False, lineterminator="\n", float_format="%.6f").encode("utf-8")


def validar_lock(csv_path: Path, manifest_path: Path) -> bool:
    if not csv_path.exists() and not manifest_path.exists():
        return False
    if not csv_path.exists() or not manifest_path.exists():
        raise SystemExit("LOCK CATBOOST INCONSISTENTE: CSV e manifest devem existir juntos")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    esperado = manifest.get("csv_sha256")
    atual = sha256(csv_path)
    if not esperado or esperado != atual:
        raise SystemExit("LOCK CATBOOST CORROMPIDO: hash do CSV diverge do manifest")
    print(f"LOCK CatBoost ja existe e foi validado ({atual[:12]}...); nenhuma recomputacao permitida.")
    return True


def numero(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def main() -> int:
    aberta = detectar_rodada_aberta()
    if not aberta:
        print("Nenhuma rodada aberta sem resultado; nada a congelar para CatBoost.")
        return 0

    rodada, folder, resumo = aberta
    csv_path = ARCHIVE / f"R{rodada:02d}.catboost.csv"
    manifest_path = ARCHIVE / f"R{rodada:02d}.catboost.manifest.json"
    if validar_lock(csv_path, manifest_path):
        return 0

    dataset = pd.read_csv(DATA)
    dataset = dataset[(dataset.rodada < rodada) & dataset.posicao.isin(POSITIONS)].copy()
    current, meta = montar_frame_atual(rodada, folder)
    if current.empty:
        raise SystemExit("Sem jogadores com historico suficiente para CatBoost prospectivo")

    score = np.zeros(len(current), dtype=float)
    selecoes = []
    contagem = Counter()

    for pos in POSITIONS:
        mask = current.posicao.eq(pos)
        test = current[mask]
        history = dataset[dataset.posicao.eq(pos)]
        if test.empty:
            continue
        if history.empty or int(history.rodada.max()) >= rodada:
            raise RuntimeError(f"Falha temporal CatBoost R{rodada}/{pos}")

        local = np.zeros(len(test), dtype=float)
        for scout, weight in SCOUT_WEIGHTS.items():
            if f"target_{scout}" not in history.columns:
                continue
            winner, inner_scores, proof = choose_model(history, scout, rodada)
            try:
                pred = fit_predict(winner, history, test, scout)
            except Exception:
                pred = baseline_predict(test, scout, "ewma")
                winner = "ewma_fallback"
            pred = np.asarray(pred, dtype=float)
            pred = np.nan_to_num(pred, nan=0.0, posinf=0.0, neginf=0.0)
            local += pred * float(weight)
            contagem[winner] += 1
            selecoes.append({
                "posicao": pos,
                "scout": scout,
                "modelo": winner,
                "mae_validacao_passada": numero(inner_scores.get(winner)),
                "prova_temporal": proof,
            })
        score[np.flatnonzero(mask.to_numpy())] = local

    pred = meta[["atleta_id", "apelido", "posicao", "clube_id", "sigla_clube", "status_id"]].copy()
    pred["rodada"] = rodada
    pred["v3s_catboost_nested"] = score
    pred = pred.sort_values(["posicao", "v3s_catboost_nested", "atleta_id"], ascending=[True, False, True])

    data = canonical_csv(pred)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.write_bytes(data)

    fontes = [DATA, folder / "jogadores.json", folder / "partidas.json"]
    manifest = {
        "temporada": 2026,
        "rodada": rodada,
        "gerado_em_utc": datetime.now(timezone.utc).isoformat(),
        "status_mercado": resumo.get("statusMercado"),
        "protocolo": (
            "sidecar prospectivo CatBoost nested; para prever R usa somente dados/resultados de rodadas < R; "
            "selecao interna e treino sao temporais; arquivo torna-se imutavel no primeiro lock"
        ),
        "jogadores_previstos": int(len(pred)),
        "csv": str(csv_path.relative_to(ROOT)),
        "csv_sha256": hashlib.sha256(data).hexdigest(),
        "fontes_sha256": {str(p.relative_to(ROOT)): sha256(p) for p in fontes if p.exists()},
        "modelos_selecionados": dict(sorted(contagem.items(), key=lambda kv: (-kv[1], kv[0]))),
        "selecoes_modelos": selecoes,
        "v2_producao_alterada": False,
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"CatBoost prospectivo R{rodada:02d}: {len(pred)} jogadores; "
        f"hash={manifest['csv_sha256'][:12]}...; LOCK CRIADO"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
