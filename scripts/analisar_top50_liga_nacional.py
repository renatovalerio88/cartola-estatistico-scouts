#!/usr/bin/env python3
"""Reconstrói e analisa o histórico da coorte Top 25 da Liga Nacional.

O caminho legado ``top50-atual.json`` é mantido por compatibilidade, mas o
laboratório final usa os 25 primeiros oficialmente capturados. A análise é
apenas descritiva: a coorte atual tem survivorship bias e não entra no treino.
"""
from __future__ import annotations

import json
import math
import statistics
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://api.cartolafc.globo.com"
COHORT = ROOT / "data" / "raw" / "top50-liga-nacional" / "top50-atual.json"
HISTORY_DIR = ROOT / "data" / "raw" / "top50-liga-nacional" / "historico"
REPORT = ROOT / "data" / "reports" / "top50-liga-nacional-estrategias.json"
COHORT_SIZE = 25
TIMEOUT = 20
HEADERS = {"User-Agent": "cartola-estatistico-scouts-v3/1.0 (scientific audit)", "Accept": "application/json,text/plain,*/*"}
POS = {1: "GOL", 2: "LAT", 3: "ZAG", 4: "MEI", 5: "ATA", 6: "TEC"}
SCHEME = {1: "3-4-3", 2: "3-5-2", 3: "4-3-3", 4: "4-4-2", 5: "4-5-1", 6: "5-3-2", 7: "5-4-1"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_float(v: Any) -> float | None:
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def mean(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def get_json(url: str) -> Any | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        return r.json() if r.status_code == 200 else None
    except (requests.RequestException, ValueError):
        return None


def load_cohort() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not COHORT.exists():
        raise FileNotFoundError("coorte Top 25 auditável ainda não existe")
    obj = json.loads(COHORT.read_text(encoding="utf-8"))
    teams = obj.get("top50")
    if not isinstance(teams, list) or len(teams) != COHORT_SIZE:
        raise ValueError("arquivo de coorte deve conter exatamente 25 times")
    ids = [str(t.get("time_id")) for t in teams if t.get("time_id") is not None]
    if len(ids) != COHORT_SIZE or len(set(ids)) != COHORT_SIZE:
        raise ValueError("a coorte deve conter 25 time_id únicos e não nulos")
    return obj, teams


def last_closed_round() -> int:
    status = get_json(f"{BASE}/mercado/status") or {}
    return max(0, int(status.get("rodada_atual") or 0) - 1)


def summarize_team(payload: dict[str, Any], fallback_id: Any) -> dict[str, Any]:
    atletas = payload.get("atletas") if isinstance(payload.get("atletas"), list) else []
    capitao = payload.get("capitao_id")
    titulares = []
    for a in atletas:
        if not isinstance(a, dict):
            continue
        aid, clube_id, pos_id = a.get("atleta_id", a.get("id")), a.get("clube_id"), a.get("posicao_id")
        titulares.append({
            "atleta_id": aid, "clube_id": clube_id, "posicao_id": pos_id,
            "posicao": POS.get(pos_id, str(pos_id) if pos_id is not None else None),
            "preco": safe_float(a.get("preco_num", a.get("preco"))),
            "pontos": safe_float(a.get("pontos_num", a.get("pontos"))),
            "capitao": str(aid) == str(capitao) if aid is not None and capitao is not None else False,
        })
    return {
        "time_id": payload.get("time", {}).get("time_id", fallback_id) if isinstance(payload.get("time"), dict) else fallback_id,
        "esquema_id": payload.get("esquema_id"),
        "formacao": SCHEME.get(payload.get("esquema_id"), str(payload.get("esquema_id")) if payload.get("esquema_id") is not None else None),
        "capitao_id": capitao, "patrimonio": safe_float(payload.get("patrimonio")), "pontos": safe_float(payload.get("pontos")), "atletas": titulares,
    }


def collect_round(rodada: int, teams: list[dict[str, Any]]) -> list[dict[str, Any]]:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    out_path = HISTORY_DIR / f"rodada-{rodada:02d}.json"
    if out_path.exists():
        obj = json.loads(out_path.read_text(encoding="utf-8"))
        cached = obj.get("times")
        if isinstance(cached, list) and len(cached) >= 22:
            cached_ids = {str(r.get("time_id")) for r in cached}
            target_ids = {str(t.get("time_id")) for t in teams}
            compatible = [r for r in cached if str(r.get("time_id")) in target_ids]
            if len(compatible) >= 22:
                return compatible
    rows = []
    for i, t in enumerate(teams, 1):
        payload = get_json(f"{BASE}/time/id/{t['time_id']}/{rodada}")
        if isinstance(payload, dict) and payload.get("atletas"):
            rows.append(summarize_team(payload, t["time_id"]))
        if i % 10 == 0:
            time.sleep(0.15)
    out_path.write_text(json.dumps({"rodada": rodada, "capturado_em": now_iso(), "coorte": "Top 25 Nacional", "times": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    return rows


def athlete_ids(row: dict[str, Any]) -> set[str]:
    return {str(a["atleta_id"]) for a in row.get("atletas", []) if a.get("atleta_id") is not None}


def analyze(history: dict[int, list[dict[str, Any]]], cohort: dict[str, Any]) -> dict[str, Any]:
    by_team_prev: dict[str, set[str]] = {}
    formation, captain_pos = Counter(), Counter()
    max_same_club: list[float] = []
    unique_club_share: list[float] = []
    lineup_costs: list[float] = []
    patrimonios: list[float] = []
    pontuacoes: list[float] = []
    rotations: list[float] = []
    rows_total = rounds_valid = 0
    per_round = []
    for rodada in sorted(history):
        rows = history[rodada]
        if not rows:
            continue
        rounds_valid += 1
        rows_total += len(rows)
        f = Counter(r.get("formacao") for r in rows if r.get("formacao"))
        formation.update(f)
        round_scores, round_rotation = [], []
        for row in rows:
            tid, ids = str(row.get("time_id")), athlete_ids(row)
            prev = by_team_prev.get(tid)
            if prev and ids:
                rot = len(ids - prev) / max(1, min(len(ids), 12))
                rotations.append(rot); round_rotation.append(rot)
            if ids: by_team_prev[tid] = ids
            prices = [a["preco"] for a in row.get("atletas", []) if a.get("preco") is not None]
            if prices: lineup_costs.append(sum(prices))
            if row.get("patrimonio") is not None: patrimonios.append(row["patrimonio"])
            if row.get("pontos") is not None: pontuacoes.append(row["pontos"]); round_scores.append(row["pontos"])
            clubs = [a.get("clube_id") for a in row.get("atletas", []) if a.get("clube_id") is not None]
            if clubs:
                counts = Counter(clubs); max_same_club.append(float(max(counts.values()))); unique_club_share.append(len(counts) / len(clubs))
            for a in row.get("atletas", []):
                if a.get("capitao") and a.get("posicao"): captain_pos[a["posicao"]] += 1
        per_round.append({"rodada": rodada, "times_recuperados": len(rows), "formacoes": dict(f.most_common()), "media_pontos": mean(round_scores), "media_rotacao": mean(round_rotation)})
    return {
        "gerado_em": now_iso(), "estudo": "Estratégias históricas da coorte atual Top 25 Liga Nacional",
        "status": "ANALISE_DESCRITIVA_CONCLUIDA" if rounds_valid else "SEM_HISTORICO_RECUPERADO",
        "proveniencia_coorte": cohort.get("fonte"), "coorte_capturada_em": cohort.get("capturado_em"),
        "alertas_metodologicos": [
            "A coorte definida pelo ranking atual possui survivorship bias ao ser analisada retrospectivamente.",
            "Resultados do Top 25 são descritivos e não entram automaticamente como features/pesos do V3.",
            "Qualquer regra inspirada nos melhores times deve vencer ablation/walk-forward antes de ser incorporada.",
        ],
        "cobertura": {"rodadas_com_dados": rounds_valid, "time_rodadas": rows_total, "media_times_por_rodada": rows_total / rounds_valid if rounds_valid else 0},
        "estrategias": {
            "formacoes": dict(formation.most_common()), "posicoes_capitao": dict(captain_pos.most_common()),
            "media_max_jogadores_mesmo_clube": mean(max_same_club), "media_fracao_clubes_unicos": mean(unique_club_share),
            "media_custo_escalacao": mean(lineup_costs), "media_patrimonio": mean(patrimonios), "media_pontos": mean(pontuacoes),
            "media_rotacao_entre_rodadas": mean(rotations),
        },
        "por_rodada": per_round,
        "proximo_passo": "Consolidar as evidências do laboratório e encerrar a fase científica antes do site V3.",
    }


def main() -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    try:
        cohort, teams = load_cohort()
    except (FileNotFoundError, ValueError) as exc:
        report = {"gerado_em": now_iso(), "estudo": "Estratégias históricas da coorte Top 25 Liga Nacional", "status": "AGUARDANDO_COORTE_AUDITAVEL", "motivo": str(exc)}
        REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return
    history = {rodada: collect_round(rodada, teams) for rodada in range(1, last_closed_round() + 1)}
    report = analyze(history, cohort)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": report["status"], "report": str(REPORT.relative_to(ROOT))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
