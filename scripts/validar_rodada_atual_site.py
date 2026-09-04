#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
SITE_DATA = ROOT / "site" / "dados.json"
STATUS_URL = "https://api.cartolafc.globo.com/mercado/status"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Cartola Estatistico Scouts V3 freshness gate)",
    "Accept": "application/json",
}


def carregar_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def status_oficial():
    req = Request(STATUS_URL, headers=HEADERS, method="GET")
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    if not SITE_DATA.exists():
        raise SystemExit("GATE RODADA: site/dados.json ausente")

    payload = carregar_json(SITE_DATA)
    produto = payload.get("produto") or {}
    rodada_site = produto.get("rodada")
    jogadores = produto.get("jogadores") or []

    try:
        oficial = status_oficial()
    except Exception as exc:
        raise SystemExit(f"GATE RODADA: não foi possível validar o status oficial do Cartola: {exc}")

    rodada_oficial = oficial.get("rodada_atual") or oficial.get("rodada")
    status_mercado = oficial.get("status_mercado")
    nome_rodada = oficial.get("nome_rodada")

    try:
        rodada_site = int(rodada_site)
        rodada_oficial = int(rodada_oficial)
    except (TypeError, ValueError):
        raise SystemExit(
            f"GATE RODADA: rodada inválida (site={rodada_site!r}, oficial={rodada_oficial!r})"
        )

    if rodada_site != rodada_oficial:
        raise SystemExit(
            "GATE RODADA REPROVADO: o site não pode publicar previsão velha como atual. "
            f"Site=R{rodada_site:02d}; Cartola oficial=R{rodada_oficial:02d} ({nome_rodada or 'sem nome'})."
        )

    if not jogadores:
        raise SystemExit(f"GATE RODADA REPROVADO: R{rodada_site:02d} sem jogadores no payload")

    print(
        f"GATE RODADA APROVADO: site=R{rodada_site:02d}, oficial=R{rodada_oficial:02d}, "
        f"status_mercado={status_mercado}, jogadores={len(jogadores)}"
    )


if __name__ == "__main__":
    main()
