#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "data" / "reports" / "backtest-v3s-nested.json"
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "reports" / "backtest-time-sugerido-walk-forward.json"

FORMACOES = {
    "3-4-3": {"GOL": 1, "LAT": 0, "ZAG": 3, "MEI": 4, "ATA": 3},
    "3-5-2": {"GOL": 1, "LAT": 0, "ZAG": 3, "MEI": 5, "ATA": 2},
    "4-3-3": {"GOL": 1, "LAT": 2, "ZAG": 2, "MEI": 3, "ATA": 3},
    "4-4-2": {"GOL": 1, "LAT": 2, "ZAG": 2, "MEI": 4, "ATA": 2},
    "5-3-2": {"GOL": 1, "LAT": 2, "ZAG": 3, "MEI": 3, "ATA": 2},
}
POSICOES = ["GOL", "LAT", "ZAG", "MEI", "ATA"]
MAX_CLUBE = 3


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def round_market(rodada: int):
    path = RAW / f"rodada-{rodada:02d}" / "jogadores.json"
    if not path.exists():
        return {}
    data = load_json(path)
    return {int(j["id"]): j for j in data if j.get("id") is not None}


def solve_formation(players: list[dict], quotas: dict[str, int]):
    n = len(players)
    if not n:
        return None
    c = -np.array([float(p["projecao"]) for p in players], dtype=float)
    rows, lower, upper = [], [], []

    # Exatamente 11 atletas e as cotas posicionais da formação.
    rows.append(np.ones(n, dtype=float))
    lower.append(11.0)
    upper.append(11.0)
    for pos in POSICOES:
        row = np.array([1.0 if p["posicao"] == pos else 0.0 for p in players])
        rows.append(row)
        q = float(quotas[pos])
        lower.append(q)
        upper.append(q)

    # Mesmo guardrail estrutural do produto: no máximo 3 atletas por clube.
    clubs = sorted({int(p["clube_id"]) for p in players if int(p["clube_id"]) > 0})
    for club in clubs:
        row = np.array([1.0 if int(p["clube_id"]) == club else 0.0 for p in players])
        rows.append(row)
        lower.append(0.0)
        upper.append(float(MAX_CLUBE))

    constraints = LinearConstraint(np.vstack(rows), np.array(lower), np.array(upper))
    result = milp(
        c=c,
        integrality=np.ones(n),
        bounds=Bounds(np.zeros(n), np.ones(n)),
        constraints=constraints,
        options={"time_limit": 20},
    )
    if not result.success or result.x is None:
        return None
    chosen = [players[i] for i, x in enumerate(result.x) if x > 0.5]
    return chosen if len(chosen) == 11 else None


def build_round(rodada: int, predictions: list[dict]):
    market = round_market(rodada)
    players = []
    for row in predictions:
        aid = int(row["atleta_id"])
        raw = market.get(aid, {})
        pos = str(row.get("posicao") or raw.get("posicao") or "")
        if pos not in POSICOES:
            continue
        players.append(
            {
                "atleta_id": aid,
                "apelido": raw.get("apelido") or str(aid),
                "posicao": pos,
                "clube_id": int(raw.get("clubeId") or 0),
                "clube": raw.get("siglaClube") or raw.get("clube") or "",
                "projecao": float(row["v3h_hibrido"]),
                "real": float(row["real"]),
            }
        )

    options = []
    for name, quotas in FORMACOES.items():
        chosen = solve_formation(players, quotas)
        if not chosen:
            continue
        projected_base = sum(p["projecao"] for p in chosen)
        captain = max(chosen, key=lambda p: (p["projecao"], -p["atleta_id"]))
        projected = projected_base + captain["projecao"]
        actual = sum(p["real"] for p in chosen) + captain["real"]
        options.append((projected, name, chosen, captain, actual))

    if not options:
        return None
    projected, formation, chosen, captain, actual = max(options, key=lambda x: (x[0], x[1]))
    diff = actual - projected
    return {
        "rodada": rodada,
        "formacao": formation,
        "projecao": round(projected, 4),
        "pontuacao_real": round(actual, 4),
        "erro": round(diff, 4),
        "erro_abs": round(abs(diff), 4),
        "capitao": {
            "atleta_id": captain["atleta_id"],
            "apelido": captain["apelido"],
            "projecao": round(captain["projecao"], 4),
            "real": round(captain["real"], 4),
        },
        "jogadores": [
            {
                "atleta_id": p["atleta_id"],
                "apelido": p["apelido"],
                "posicao": p["posicao"],
                "clube_id": p["clube_id"],
                "clube": p["clube"],
                "projecao": round(p["projecao"], 4),
                "real": round(p["real"], 4),
                "capitao": p["atleta_id"] == captain["atleta_id"],
            }
            for p in sorted(chosen, key=lambda x: (POSICOES.index(x["posicao"]), -x["projecao"]))
        ],
    }


def main():
    if not REPORT.exists():
        raise SystemExit(f"Relatório walk-forward ausente: {REPORT}")
    report = load_json(REPORT)
    rows = report.get("previsoes") or []
    by_round: dict[int, list[dict]] = {}
    for row in rows:
        by_round.setdefault(int(row["rodada"]), []).append(row)

    rounds = []
    for rodada in sorted(by_round):
        result = build_round(rodada, by_round[rodada])
        if result:
            rounds.append(result)

    if not rounds:
        raise SystemExit("Nenhuma rodada elegível para o backtest do XI")

    mae = sum(r["erro_abs"] for r in rounds) / len(rounds)
    avg_proj = sum(r["projecao"] for r in rounds) / len(rounds)
    avg_real = sum(r["pontuacao_real"] for r in rounds) / len(rounds)
    first = min(r["rodada"] for r in rounds)
    last = max(r["rodada"] for r in rounds)

    payload = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "tipo": "backtest_walk_forward",
        "modelo": "v3h_hibrido",
        "protocolo": (
            "Em cada rodada R, a projeção v3h_hibrido foi produzida pelo backtest nested usando "
            "somente dados de rodadas anteriores a R. O XI é escolhido sem consultar o resultado de R; "
            "a pontuação real só é anexada depois para avaliação."
        ),
        "distincao_prospectiva": (
            "Este bloco é um backtest histórico walk-forward e não afirma que a escalação foi publicada "
            "ou congelada naquela data. Previsões realmente congeladas antes do mercado permanecem "
            "separadas em avaliacao_prospectiva_imutavel."
        ),
        "escopo": {
            "rodada_solicitada_inicial": 2,
            "primeira_rodada_modelo": first,
            "ultima_rodada_modelo": last,
            "rodadas": len(rounds),
            "indisponiveis_antes_do_modelo": list(range(2, first)),
            "motivo_inicio": (
                "A arquitetura V3H nested atual inicia na R10 para exigir histórico mínimo de treino. "
                "R2-R9 não são preenchidas com outro modelo nem com dados futuros."
            ),
        },
        "restricoes_reproduzidas": [
            "formações oficiais 3-4-3, 3-5-2, 4-3-3, 4-4-2 e 5-3-2",
            "11 titulares",
            "máximo de 3 atletas por clube quando clube_id está disponível",
            "capitão = maior projeção do XI, com pontuação dobrada",
        ],
        "restricoes_historicas_nao_reproduzidas": [
            "orçamento/preço histórico",
            "status provável histórico",
            "técnico e banco",
        ],
        "nota_restricoes": (
            "Os snapshots históricos antigos não preservam preço e status pré-rodada de forma confiável. "
            "Por isso este gráfico mede a assertividade do modelo sobre um XI temporalmente válido, "
            "mas não é apresentado como reprodução exata do otimizador de produção."
        ),
        "kpis": {
            "rodadas": len(rounds),
            "media_projetada": round(avg_proj, 4),
            "media_real": round(avg_real, 4),
            "erro_medio_absoluto": round(mae, 4),
        },
        "rodadas": rounds,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Backtest do XI: R{first}-R{last}, {len(rounds)} rodadas, MAE={mae:.2f}")


if __name__ == "__main__":
    main()
