#!/usr/bin/env python3
"""Avalia previsoes pre-rodada imutaveis somente depois de a rodada estar resolvida.

O objetivo deste placar e separar completamente a evidencia prospectiva da pesquisa
retrospectiva. O script nunca recalibra modelos e nunca regrava snapshots. Ele apenas
cruza CSVs ja congelados em predictions/pre_round/<temporada>/Rxx.csv com o arquivo
pontuados.json posteriormente sincronizado da V2 em modo somente leitura.

Uma rodada so e considerada avaliavel quando pontuados.json possui uma colecao
plausivelmente completa de atletas (>= MIN_PONTUADOS). Ate la, ela permanece como
AGUARDANDO_RESULTADO e nao entra em nenhuma metrica.
"""
from __future__ import annotations

import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PRED_ROOT = ROOT / "predictions" / "pre_round"
RAW_ROOT = ROOT / "data" / "raw"
OUT = ROOT / "data" / "reports" / "avaliacao-prospectiva-imutavel.json"
MIN_PONTUADOS = 100
PREDICTION_COLUMNS = (
    "v3s_expected_scouts",
    "direta_rf_lab",
    "v3h_hibrido",
)


def numero(value):
    try:
        v = float(value)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def carregar_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def carregar_pontuados(rodada: int) -> dict[int, dict]:
    path = RAW_ROOT / f"rodada-{rodada:02d}" / "pontuados.json"
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    atletas = payload.get("atletas") if isinstance(payload, dict) else None
    if not isinstance(atletas, dict):
        return {}
    out = {}
    for atleta_id, item in atletas.items():
        if not isinstance(item, dict):
            continue
        real = numero(item.get("pontuacao"))
        if real is None:
            continue
        try:
            aid = int(atleta_id)
        except (TypeError, ValueError):
            continue
        out[aid] = {
            "real": real,
            "entrou_em_campo": bool(item.get("entrou_em_campo")),
            "posicao_id": item.get("posicao_id"),
        }
    return out


def metricas(y: list[float], p: list[float]) -> dict:
    if not y:
        return {"n": 0}
    ya = np.asarray(y, dtype=float)
    pa = np.asarray(p, dtype=float)
    erro = pa - ya
    if len(ya) >= 2 and np.std(ya) > 0 and np.std(pa) > 0:
        corr = float(np.corrcoef(ya, pa)[0, 1])
    else:
        corr = None
    return {
        "n": int(len(ya)),
        "mae": round(float(np.mean(np.abs(erro))), 6),
        "rmse": round(float(np.sqrt(np.mean(erro ** 2))), 6),
        "bias_previsto_menos_real": round(float(np.mean(erro)), 6),
        "correlacao_pearson": round(corr, 6) if corr is not None and math.isfinite(corr) else None,
        "media_prevista": round(float(np.mean(pa)), 6),
        "media_real": round(float(np.mean(ya)), 6),
    }


def avaliar_grupo(rows: list[dict], somente_entrou: bool) -> dict:
    resultado = {}
    for col in PREDICTION_COLUMNS:
        y, p = [], []
        for row in rows:
            if somente_entrou and not row["entrou_em_campo"]:
                continue
            pred = row.get(col)
            if pred is None:
                continue
            y.append(row["real"])
            p.append(pred)
        resultado[col] = metricas(y, p)
    return resultado


def avaliar_rodada(csv_path: Path, temporada: int, rodada: int) -> dict:
    pontuados = carregar_pontuados(rodada)
    if len(pontuados) < MIN_PONTUADOS:
        return {
            "temporada": temporada,
            "rodada": rodada,
            "status": "AGUARDANDO_RESULTADO",
            "pontuados_disponiveis": len(pontuados),
            "minimo_para_avaliar": MIN_PONTUADOS,
        }

    snapshot = carregar_csv(csv_path)
    linhas = []
    faltantes_real = 0
    for row in snapshot:
        try:
            aid = int(row.get("atleta_id", ""))
        except (TypeError, ValueError):
            continue
        item = pontuados.get(aid)
        # Em rodada fechada, ausencia em /pontuados significa que o atleta nao pontuou.
        # Mantemos tambem uma metrica separada apenas para quem entrou em campo.
        if item is None:
            real = 0.0
            entrou = False
            faltantes_real += 1
        else:
            real = item["real"]
            entrou = item["entrou_em_campo"]
        linha = {
            "atleta_id": aid,
            "posicao": str(row.get("posicao") or "").upper(),
            "real": real,
            "entrou_em_campo": entrou,
        }
        for col in PREDICTION_COLUMNS:
            linha[col] = numero(row.get(col))
        linhas.append(linha)

    por_posicao = {}
    for posicao in sorted({r["posicao"] for r in linhas if r["posicao"]}):
        grupo = [r for r in linhas if r["posicao"] == posicao]
        por_posicao[posicao] = {
            "todos_snapshot": avaliar_grupo(grupo, False),
            "somente_entrou_em_campo": avaliar_grupo(grupo, True),
        }

    return {
        "temporada": temporada,
        "rodada": rodada,
        "status": "AVALIADA",
        "jogadores_snapshot": len(linhas),
        "jogadores_em_pontuados": len(pontuados),
        "snapshot_sem_registro_pontuados_tratado_como_zero": faltantes_real,
        "geral": {
            "todos_snapshot": avaliar_grupo(linhas, False),
            "somente_entrou_em_campo": avaliar_grupo(linhas, True),
        },
        "por_posicao": por_posicao,
    }


def consolidar(avaliadas: list[dict]) -> dict:
    if not avaliadas:
        return {"rodadas_avaliadas": 0, "status": "SEM_RESULTADO_PROSPECTIVO_FECHADO"}
    resumo = {"rodadas_avaliadas": len(avaliadas), "rodadas": [r["rodada"] for r in avaliadas]}
    for universo in ("todos_snapshot", "somente_entrou_em_campo"):
        por_modelo = {}
        for col in PREDICTION_COLUMNS:
            maes = []
            for rodada in avaliadas:
                m = rodada["geral"][universo].get(col, {})
                if m.get("n", 0) and m.get("mae") is not None:
                    maes.append(float(m["mae"]))
            por_modelo[col] = {
                "rodadas": len(maes),
                "mae_medio_por_rodada": round(float(np.mean(maes)), 6) if maes else None,
            }
        resumo[universo] = por_modelo
    resumo["nota"] = "Consolidado prospectivo usa apenas snapshots previamente congelados; nenhuma rodada e usada para recalibrar sua propria previsao."
    return resumo


def main() -> int:
    rodadas = []
    for manifest_path in sorted(PRED_ROOT.glob("*/R*.manifest.json")):
        try:
            temporada = int(manifest_path.parent.name)
            rodada = int(manifest_path.stem.split(".")[0][1:])
        except ValueError:
            continue
        csv_path = manifest_path.with_name(f"R{rodada}.csv")
        if not csv_path.exists():
            continue
        rodadas.append(avaliar_rodada(csv_path, temporada, rodada))

    avaliadas = [r for r in rodadas if r.get("status") == "AVALIADA"]
    payload = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "objetivo": "placar prospectivo puro das previsoes pre-rodada imutaveis do Scouts V3",
        "protocolo": (
            "somente snapshots criados antes da rodada; resultados lidos depois via data/raw sincronizado da V2 em modo somente leitura; "
            "nenhuma recalibracao, selecao de modelo ou alteracao retroativa do snapshot"
        ),
        "colunas_avaliadas": list(PREDICTION_COLUMNS),
        "rodadas": rodadas,
        "consolidado": consolidar(avaliadas),
        "v2_producao_alterada": False,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    aguardando = sum(r.get("status") == "AGUARDANDO_RESULTADO" for r in rodadas)
    print(f"Avaliacao prospectiva: avaliadas={len(avaliadas)} aguardando={aguardando}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
