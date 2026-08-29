"""Regras de pontuação e utilidades de scouts do Cartola.

Os pesos são auditados empiricamente contra a pontuação oficial salva em cada rodada.
A auditoria é a fonte de verdade: se o Cartola alterar um peso, o pipeline falha até
que a regra seja revisada conscientemente.
"""
from __future__ import annotations
from typing import Mapping

SCOUT_WEIGHTS: dict[str, float] = {
    "G": 8.0, "A": 5.0, "FT": 3.0, "FD": 1.2, "FF": 0.8, "FS": 0.5,
    "PS": 1.0, "I": -0.1, "DS": 1.5, "SG": 5.0, "DP": 7.0, "DE": 1.3,
    "GC": -3.0, "CV": -3.0, "CA": -1.0, "GS": -1.0, "FC": -0.3,
    "PC": -1.0, "PP": -3.2,
}
POSITION_NAMES = {1: "GOL", 2: "LAT", 3: "ZAG", 4: "MEI", 5: "ATA", 6: "TEC"}
COUNT_SCOUTS = set(SCOUT_WEIGHTS)

def score_from_scouts(scouts: Mapping[str, float] | None) -> tuple[float, set[str]]:
    total = 0.0
    unknown: set[str] = set()
    for code, raw_value in (scouts or {}).items():
        try:
            value = float(raw_value or 0)
        except (TypeError, ValueError):
            continue
        if code not in SCOUT_WEIGHTS:
            unknown.add(code)
            continue
        total += SCOUT_WEIGHTS[code] * value
    return round(total, 4), unknown
