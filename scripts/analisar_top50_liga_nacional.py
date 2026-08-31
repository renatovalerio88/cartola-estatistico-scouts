#!/usr/bin/env python3
"""Reconstrói e analisa o histórico da coorte Top 50 da Liga Nacional.

Este módulo só executa a análise quando existe uma coorte auditável em
``data/raw/top50-liga-nacional/top50-atual.json``. Ele nunca tenta inferir o
Top 50 por popularidade, pontuação de atletas ou ligas homônimas criadas por
usuários.

Importante: uma coorte definida pelo ranking *atual* possui viés de seleção
(retrospectivo/survivorship bias). Portanto, os resultados históricos são
tratados como estudo descritivo de estratégias dos atuais Top 50 e nunca como
prova causal ou feature de treino. Para testes prospectivos, snapshots futuros
da coorte devem ser congelados antes de cada rodada.
"""

from __future__ import annotations

import json
import math
import statistics
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://api.cartolafc.globo.com"
COHORT = ROOT / "data" / "raw" / "top50-liga-nacional" / "top50-atual.json"
HISTORY_DIR = ROOT / "data" / "raw" / "top50-liga-nacional" / "historico"
REPORT = ROOT / "data" / "reports" / "top50-liga-nacional-estrategias.json"
TIMEOUT = 20
HEADERS = {
    "User-Agent": "cartola-estatistico-scouts-v3/1.0 (scientific audit)",
    "Accept": "application/json,text/plain,*/*",
}

POS = {1: "GOL", 2: "LAT", 3: "ZAG", 4: "MEI", 5: "ATA", 6: "TEC"}
SCHEME = {
    1: "3-4-3",
    2: "3-5-2",
    3: "4-3-3",
    4: "4-4-2",
    5: "4-5-1",
    6: "5-3-2",
    7: "5-4-1",
}


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
        if r.status_code != 200:
            return None
        return r.json()
    except (requests.RequestException, ValueError):
        return None


def load_cohort() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not COHORT.exists():
        raise FileNotFoundError("coorte Top 50 auditável ainda não existe")
    obj = json.loads(COHORT.read_text(encoding="utf-8"))
    teams = obj.get("top50")
    if not isinstance(teams, list) or len(teams) != 50:
        raise ValueError("top50-atual.json deve conter exatamente 50 times")
    ids = [str(t.get("time_id")) for t in teams if t.get("time_id") is not None]
    if len(ids) != 50 or len(set(ids)) != 50:
        raise ValueError("a coorte deve conter 50 time_id únicos e não nulos")
    fonte = obj.get("fonte")
    if not isinstance(fonte, dict) or not fonte.get("url"):
        raise ValueError("a coorte precisa registrar fonte/proveniência")
    return obj, teams


def last_closed_round() -> int:
    status = get_json(f"{BASE}/mercado/status") or {}
    rodada = int(status.get("rodada_atual") or 0)
    mercado_status = status.get("status_mercado")
    # status_mercado=1 costuma indicar mercado aberto para a próxima rodada.
    # Por segurança, nunca tratamos a rodada_atual como fechada quando não há
    # evidência inequívoca; a coleta histórica para r<rodada_atual é estável.
    return max(0, rodada - 1)


def summarize_team(payload: dict[str, Any], fallback_id: Any) -> dict[str, Any]:
    atletas = payload.get("atletas") if isinstance(payload.get("atletas"), list) else []
    capitao = payload.get("capitao_id")
    titulares = []
    for a in atletas:
        if not isinstance(a, dict):
            continue
        aid = a.get("atleta_id", a.get("id"))
        clube_id = a.get("clube_id")
        pos_id = a.get("posicao_id")
        titulares.append(
            {
                "atleta_id": aid,
                "clube_id": clube_id,
                "posicao_id": pos_id,
                "posicao": POS.get(pos_id, str(pos_id) if pos_id is not None else None),
                "preco": safe_float(a.get("preco_num", a.get("preco"))),
                "pontos": safe_float(a.get("pontos_num", a.get("pontos"))),
                "capitao": str(aid) == str(capitao) if aid is not None and capitao is not None else False,
            }
        )
    return {
        "time_id": payload.get("time", {}).get("time_id", fallback_id) if isinstance(payload.get("time"), dict) else fallback_id,
        "esquema_id": payload.get("esquema_id"),
        "formacao": SCHEME.get(payload.get("esquema_id"), str(payload.get("esquema_id")) if payload.get("esquema_id") is not None else None),
        "capitao_id": capitao,
        "patrimonio": safe_float(payload.get("patrimonio")),
        "pontos": safe_float(payload.get("pontos")),
        "atletas": titulares,
    }


def collect_round(rodada: int, teams: list[dict[str, Any]]) -> list[dict[str, Any]]:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    out_path = HISTORY_DIR / f"rodada-{rodada:02d}.json"
    if out_path.exists():
        obj = json.loads(out_path.read_text(encoding="utf-8"))
        cached = obj.get("times")
        if isinstance(cached, list) and len(cached) >= 45:
            return cached

    rows: list[dict[str, Any]] = []
    for i, t in enumerate(teams, 1):
        team_id = t["time_id"]
        payload = get_json(f"{BASE}/time/id/{team_id}/{rodada}")
        if isinstance(payload, dict) and payload.get("atletas"):
            rows.append(summarize_team(payload, team_id))
        # leve espaçamento para não agredir a API pública
        if i % 10 == 0:
            time.sleep(0.15)

    out_path.write_text(
        json.dumps({"rodada": rodada, "capturado_em": now_iso(), "times": rows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return rows


def formation_counts(rows: list[dict[str, Any]]) -> Counter[str]:
    return Counter(r["formacao"] for r in rows if r.get("formacao"))


def club_concentration(row: dict[str, Any]) -> tuple[int, float | None]:
    clubs = [a.get("clube_id") for a in row.get("atletas", []) if a.get("clube_id") is not None]
    if not clubs:
        return 0, None
    counts = Counter(clubs)
    return max(counts.values()), len(counts) / len(clubs)


def athlete_ids(row: dict[str, Any]) -> set[str]:
    return {str(a["atleta_id"]) for a in row.get("atletas", []) if a.get("atleta_id") is not None}


def analyze(history: dict[int, list[dict[str, Any]]], cohort: dict[str, Any]) -> dict[str, Any]:
    by_team_prev: dict[str, set[str]] = {}
    formation = Counter()
    captain = Counter()
    captain_pos = Counter()
    position_exposure = Counter()
    max_same_club: list[float] = []
    unique_club_share: list[float] = []
    lineup_costs: list[float] = []
    patrimonios: list[float] = []
    pontuacoes: list[float] = []
    rotations: list[float] = []
    rows_total = 0
    rounds_valid = 0

    per_round = []
    for rodada in sorted(history):
        rows = history[rodada]
        if not rows:
            continue
        rounds_valid += 1
        rows_total += len(rows)
        f = formation_counts(rows)
        formation.update(f)
        round_scores: list[float] = []
        round_rotation: list[float] = []

        for row in rows:
            tid = str(row.get("time_id"))
            ids = athlete_ids(row)
            prev = by_team_prev.get(tid)
            if prev and ids:
                # proporção de nomes novos em relação à escalação anterior observada
                changes = len(ids - prev)
                denom = max(1, min(len(ids), 12))
                rot = changes / denom
                rotations.append(rot)
                round_rotation.append(rot)
            if ids:
                by_team_prev[tid] = ids

            prices = [a["preco"] for a in row.get("atletas", []) if a.get("preco") is not None]
            if prices:
                lineup_costs.append(sum(prices))
            if row.get("patrimonio") is not None:
                patrimonios.append(row["patrimonio"])
            if row.get("pontos") is not None:
                pontuacoes.append(row["pontos"])
                round_scores.append(row["pontos"])

            mx, share = club_concentration(row)
            if mx:
                max_same_club.append(float(mx))
            if share is not None:
                unique_club_share.append(share)

            for a in row.get("atletas", []):
                if a.get("posicao"):
                    position_exposure[a["posicao"]] += 1
                if a.get("capitao"):
                    if a.get("atleta_id") is not None:
                        captain[str(a["atleta_id"])] += 1
                    if a.get("posicao"):
                        captain_pos[a["posicao"]] += 1

        per_round.append(
            {
                "rodada": rodada,
                "times_recuperados": len(rows),
                "formacoes": dict(f.most_common()),
                "media_pontos": mean(round_scores),
                "media_rotacao": mean(round_rotation),
            }
        )

    top_captains = [{"atleta_id": k, "vezes": v} for k, v in captain.most_common(20)]
    return {
        "gerado_em": now_iso(),
        "estudo": "Estratégias históricas da coorte atual Top 50 Liga Nacional",
        "status": "ANALISE_DESCRITIVA_CONCLUIDA" if rounds_valid else "SEM_HISTORICO_RECUPERADO",
        "proveniencia_coorte": cohort.get("fonte"),
        "coorte_capturada_em": cohort.get("capturado_em"),
        "alertas_metodologicos": [
            "A coorte definida pelo ranking atual possui survivorship bias ao ser analisada retrospectivamente.",
            "Os resultados históricos são descritivos e não entram como features nem como prova causal do V3.",
            "Para inferência prospectiva, congelar a coorte/ranking antes de cada rodada futura.",
            "Popularidade não é usada como proxy para identificar o Top 50.",
        ],
        "cobertura": {
            "rodadas_com_dados": rounds_valid,
            "time_rodadas": rows_total,
            "media_times_por_rodada": rows_total / rounds_valid if rounds_valid else 0,
        },
        "estrategias": {
            "formacoes": dict(formation.most_common()),
            "posicoes_capitao": dict(captain_pos.most_common()),
            "capitaes_mais_recorrentes": top_captains,
            "exposicao_posicional": dict(position_exposure.most_common()),
            "media_max_jogadores_mesmo_clube": mean(max_same_club),
            "media_fracao_clubes_unicos": mean(unique_club_share),
            "media_custo_escalacao": mean(lineup_costs),
            "media_patrimonio": mean(patrimonios),
            "media_pontos": mean(pontuacoes),
            "media_rotacao_entre_rodadas": mean(rotations),
        },
        "por_rodada": per_round,
        "proximo_passo": (
            "Cruzar as escalações com previsões V2/V3 que já existiam antes de cada rodada e com scouts reais, "
            "mantendo a análise comportamental separada do treino do modelo."
        ),
    }


def main() -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    try:
        cohort, teams = load_cohort()
    except (FileNotFoundError, ValueError) as exc:
        report = {
            "gerado_em": now_iso(),
            "estudo": "Estratégias históricas da coorte Top 50 Liga Nacional",
            "status": "AGUARDANDO_COORTE_AUDITAVEL",
            "motivo": str(exc),
            "proximo_passo": "Não analisar até existir fonte oficial/reproduzível com exatamente 50 time_id.",
        }
        REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"status": report["status"], "report": str(REPORT.relative_to(ROOT))}, ensure_ascii=False))
        return

    ultima = last_closed_round()
    history: dict[int, list[dict[str, Any]]] = {}
    for rodada in range(1, ultima + 1):
        history[rodada] = collect_round(rodada, teams)

    report = analyze(history, cohort)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": report["status"], "report": str(REPORT.relative_to(ROOT))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
