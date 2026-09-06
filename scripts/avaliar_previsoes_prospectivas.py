#!/usr/bin/env python3
"""Avalia snapshots pré-rodada sem recalibrar nem regravar previsões.

Mantém duas leituras separadas:
1) qualidade das projeções por jogador;
2) placar do Time Sugerido realmente congelado antes da rodada.

A segunda é a leitura principal do produto. Ela só entra no histórico quando o próprio
snapshot do time contém prova explícita de que nasceu com o mercado ainda aberto.
Arquivos antigos ou criados sem essa prova são preservados, mas nunca contam como
histórico prospectivo real.
"""
from __future__ import annotations

import csv
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PRED_ROOT = ROOT / "predictions" / "pre_round"
RAW_ROOT = ROOT / "data" / "raw"
OUT = ROOT / "data" / "reports" / "avaliacao-prospectiva-imutavel.json"
MIN_PONTUADOS = 100
MERCADO_ABERTO = 1
PREDICTION_COLUMNS = ("v3s_expected_scouts", "direta_rf_lab", "v3h_hibrido")
BASE_MANIFEST_RE = re.compile(r"R(\d{2})\.manifest\.json$")
TEAM_RE = re.compile(r"R(\d{2})\.time-sugerido\.json$")


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
    corr = None
    if len(ya) >= 2 and np.std(ya) > 0 and np.std(pa) > 0:
        c = float(np.corrcoef(ya, pa)[0, 1])
        if math.isfinite(c):
            corr = c
    return {
        "n": int(len(ya)),
        "mae": round(float(np.mean(np.abs(erro))), 6),
        "rmse": round(float(np.sqrt(np.mean(erro ** 2))), 6),
        "bias_previsto_menos_real": round(float(np.mean(erro)), 6),
        "correlacao_pearson": round(corr, 6) if corr is not None else None,
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


def avaliar_rodada_jogadores(csv_path: Path, temporada: int, rodada: int) -> dict:
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
    faltantes = 0
    for row in snapshot:
        try:
            aid = int(row.get("atleta_id", ""))
        except (TypeError, ValueError):
            continue
        item = pontuados.get(aid)
        if item is None:
            real, entrou = 0.0, False
            faltantes += 1
        else:
            real, entrou = item["real"], item["entrou_em_campo"]
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
        "snapshot_sem_registro_pontuados_tratado_como_zero": faltantes,
        "geral": {
            "todos_snapshot": avaliar_grupo(linhas, False),
            "somente_entrou_em_campo": avaliar_grupo(linhas, True),
        },
        "por_posicao": por_posicao,
    }


def prova_prospectiva_valida(snapshot: dict) -> tuple[bool, str]:
    prova = snapshot.get("prova_prospectiva")
    if not isinstance(prova, dict):
        return False, "snapshot do time não contém prova explícita de mercado aberto no congelamento"
    try:
        status = int(prova.get("status_mercado_no_congelamento") or 0)
    except (TypeError, ValueError):
        status = 0
    if status != MERCADO_ABERTO:
        return False, f"status do mercado no congelamento não era aberto: {status}"
    if not prova.get("coleta_oficial_em") or not prova.get("resumo_mercado_sha256"):
        return False, "prova prospectiva incompleta"
    return True, "mercado aberto comprovado no momento do congelamento"


def avaliar_time(path: Path, temporada: int, rodada: int) -> dict:
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    valida, motivo = prova_prospectiva_valida(snapshot)
    base = {
        "temporada": temporada,
        "rodada": rodada,
        "formacao": snapshot.get("formacao"),
        "custo": snapshot.get("custo"),
        "projecao": numero(snapshot.get("projecao_time_com_capitao")),
        "capitao_atleta_id": snapshot.get("capitao_atleta_id"),
        "titulares": snapshot.get("titulares") or [],
        "banco": snapshot.get("banco") or [],
        "snapshot_time": str(path.relative_to(ROOT)),
        "prova_prospectiva": snapshot.get("prova_prospectiva"),
    }
    if not valida:
        return {
            **base,
            "status": "NAO_PROSPECTIVO",
            "motivo": motivo,
            "entra_no_historico_publico": False,
        }

    pontuados = carregar_pontuados(rodada)
    if len(pontuados) < MIN_PONTUADOS:
        return {
            **base,
            "status": "AGUARDANDO_RESULTADO",
            "motivo": motivo,
            "entra_no_historico_publico": True,
        }
    detalhes = []
    real_base = 0.0
    captain_extra = 0.0
    captain_id = int(snapshot.get("capitao_atleta_id") or 0)
    for p in snapshot.get("titulares") or []:
        aid = int(p.get("atleta_id") or 0)
        item = pontuados.get(aid)
        real = float(item["real"]) if item else 0.0
        entrou = bool(item and item["entrou_em_campo"])
        real_base += real
        if aid == captain_id and entrou:
            captain_extra = real
        detalhes.append({
            "atleta_id": aid,
            "apelido": p.get("apelido"),
            "posicao": p.get("posicao"),
            "projecao": numero(p.get("projecao")),
            "real": real,
            "entrou_em_campo": entrou,
            "capitao": aid == captain_id,
        })
    real_total = real_base + captain_extra
    return {
        **base,
        "status": "AVALIADA",
        "motivo": motivo,
        "entra_no_historico_publico": True,
        "pontuacao_real": round(real_total, 4),
        "pontuacao_real_titulares_sem_bonus": round(real_base, 4),
        "bonus_real_capitao": round(captain_extra, 4),
        "erro_time_previsto_menos_real": round(float(base["projecao"] or 0) - real_total, 4),
        "detalhes_titulares": detalhes,
        "nota_pontuacao": "pontuação real dos titulares congelados + bônus do capitão quando ele entrou em campo; banco é exibido, mas substituições automáticas não são reconstruídas retroativamente",
    }


def consolidar_jogadores(avaliadas: list[dict]) -> dict:
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
    return resumo


def main() -> int:
    rodadas = []
    seen = set()
    for manifest_path in sorted(PRED_ROOT.glob("*/R*.manifest.json")):
        match = BASE_MANIFEST_RE.fullmatch(manifest_path.name)
        if not match:
            continue
        temporada = int(manifest_path.parent.name)
        rodada = int(match.group(1))
        key = (temporada, rodada)
        if key in seen:
            continue
        seen.add(key)
        csv_path = manifest_path.with_name(f"R{rodada}.csv")
        if csv_path.exists():
            rodadas.append(avaliar_rodada_jogadores(csv_path, temporada, rodada))

    times = []
    for team_path in sorted(PRED_ROOT.glob("*/R*.time-sugerido.json")):
        match = TEAM_RE.fullmatch(team_path.name)
        if not match:
            continue
        temporada = int(team_path.parent.name)
        rodada = int(match.group(1))
        times.append(avaliar_time(team_path, temporada, rodada))

    avaliadas = [r for r in rodadas if r.get("status") == "AVALIADA"]
    times_publicos = [r for r in times if r.get("entra_no_historico_publico")]
    times_avaliados = [r for r in times_publicos if r.get("status") == "AVALIADA"]
    payload = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "objetivo": "avaliação prospectiva de previsões e do Time Sugerido comprovadamente congelado com mercado aberto",
        "protocolo": "somente snapshots com prova explícita de mercado aberto no congelamento entram no histórico do Time Sugerido; nenhuma reconstrução retroativa de escalação; nenhum resultado da própria rodada entra na previsão",
        "rodadas": rodadas,
        "times_sugeridos": times,
        "consolidado": consolidar_jogadores(avaliadas),
        "consolidado_times": {
            "rodadas_avaliadas": len(times_avaliados),
            "rodadas": [r["rodada"] for r in times_avaliados],
            "rodadas_aguardando": [r["rodada"] for r in times_publicos if r.get("status") == "AGUARDANDO_RESULTADO"],
            "snapshots_nao_prospectivos_ignorados": [r["rodada"] for r in times if r.get("status") == "NAO_PROSPECTIVO"],
            "media_projetada": round(float(np.mean([r["projecao"] for r in times_avaliados])), 4) if times_avaliados else None,
            "media_real": round(float(np.mean([r["pontuacao_real"] for r in times_avaliados])), 4) if times_avaliados else None,
        },
        "v2_producao_alterada": False,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"Avaliação prospectiva | jogadores_avaliados={len(avaliadas)} | "
        f"times_avaliados={len(times_avaliados)} | "
        f"times_aguardando={sum(t.get('status') == 'AGUARDANDO_RESULTADO' for t in times_publicos)} | "
        f"times_nao_prospectivos={sum(t.get('status') == 'NAO_PROSPECTIVO' for t in times)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
