#!/usr/bin/env python3
import json
import math
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
HTML = SITE / "index.html"
DATA = SITE / "dados.json"

REQUIRED_PAGES = {"time", "monte", "projecoes", "analise", "historico", "metodologia"}
REQUIRED_CONTROLS = {
    "budget", "excludeClub", "excludePlayer", "recalc", "reset",
    "customBudget", "customFormation", "buildCustom",
    "filterPos", "filterClub", "search", "projectionTable",
    "pitch", "bench", "historyChart", "historyAudit", "modal", "modalContent",
}
FORMATIONS = {
    "3-4-3": {"GOL": 1, "ZAG": 3, "MEI": 4, "ATA": 3},
    "3-5-2": {"GOL": 1, "ZAG": 3, "MEI": 5, "ATA": 2},
    "4-3-3": {"GOL": 1, "ZAG": 2, "LAT": 2, "MEI": 3, "ATA": 3},
    "4-4-2": {"GOL": 1, "ZAG": 2, "LAT": 2, "MEI": 4, "ATA": 2},
    "5-3-2": {"GOL": 1, "ZAG": 3, "LAT": 2, "MEI": 3, "ATA": 2},
}


class IdCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key == "id" and value:
                self.ids.add(value)


def finite(value):
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def main():
    assert HTML.exists(), "site/index.html ausente"
    assert DATA.exists(), "site/dados.json ausente"

    html = HTML.read_text(encoding="utf-8")
    parser = IdCollector()
    parser.feed(html)
    missing_pages = REQUIRED_PAGES - parser.ids
    missing_controls = REQUIRED_CONTROLS - parser.ids
    assert not missing_pages, f"abas ausentes: {sorted(missing_pages)}"
    assert not missing_controls, f"controles ausentes: {sorted(missing_controls)}"
    assert "Por quê?" in html, "explicabilidade amigável não encontrada"
    assert "expected scouts" in html.lower() or "scouts esperados" in html.lower(), "metodologia de scouts não encontrada"

    # Gates de UX/mobile: impedem regressões nos ajustes responsivos já aprovados.
    assert 'name="viewport"' in html, "viewport responsivo ausente"
    assert "@media(max-width:700px)" in html, "breakpoint mobile principal ausente"
    assert "@media(max-width:430px)" in html, "breakpoint para telas estreitas ausente"
    assert "scrollbar-width:none" in html and "-webkit-overflow-scrolling:touch" in html, "navegação/rolagem touch incompleta"
    assert ".player-ball{width:64px}" in html, "campo mobile pode voltar a estourar horizontalmente"
    assert "grid-template-columns:1fr" in html, "controles não colapsam para uma coluna em telas estreitas"

    # Gate do Histórico: o produto deve mostrar placar prospectivo real, e não
    # apresentar backtest histórico como se fosse desempenho prospectivo.
    assert "Placar prospectivo" in html, "rótulo prospectivo do Histórico ausente"
    assert "function prospectiveMetric" in html, "leitura das métricas prospectivas ausente"
    assert "avaliacao_prospectiva_imutavel" in html, "Histórico não consome avaliação prospectiva imutável"
    assert "MAE histórico V2" not in html, "Histórico voltou a misturar backtest V2 no placar prospectivo"

    payload = json.loads(DATA.read_text(encoding="utf-8"))
    produto = payload.get("produto") or {}
    rodada = produto.get("rodada")
    jogadores = produto.get("jogadores") or []
    assert isinstance(rodada, int) and rodada > 0, "rodada inválida"
    assert len(jogadores) > 100, "universo de jogadores insuficiente"

    ids = [j.get("atleta_id") for j in jogadores]
    assert all(i is not None for i in ids), "há jogador sem atleta_id"
    assert len(ids) == len(set(ids)), "atleta_id duplicado no payload"

    invalid = []
    for j in jogadores:
        if not j.get("apelido") or not j.get("posicao") or not j.get("sigla_clube"):
            invalid.append(j.get("atleta_id"))
            continue
        if not finite(j.get("projecao")) or not finite(j.get("preco")):
            invalid.append(j.get("atleta_id"))
    assert not invalid, f"jogadores inválidos no payload: {invalid[:10]}"

    elegiveis = [j for j in jogadores if int(j.get("status_id") or 0) == 7]
    assert len(elegiveis) >= 50, "poucos jogadores prováveis/elegíveis"
    pos = Counter(j.get("posicao") for j in elegiveis)
    for nome, req in FORMATIONS.items():
        faltas = {p: n for p, n in req.items() if pos[p] < n}
        assert not faltas, f"formação {nome} inviável por falta de atletas: {faltas}"

    congelamento = payload.get("auditoria_previsoes_imutaveis") or {}
    if congelamento:
        status = str(congelamento.get("status") or congelamento.get("resultado") or "").upper()
        assert not any(x in status for x in ("FALHA", "REPROV", "INVALID")), "auditoria de imutabilidade reprovada"

    prospectivo = payload.get("avaliacao_prospectiva_imutavel") or {}
    assert isinstance(prospectivo.get("rodadas") or [], list), "placar prospectivo sem lista de rodadas"
    protocolo = str(prospectivo.get("protocolo") or "").lower()
    if prospectivo:
        assert "snapshot" in protocolo and "antes da rodada" in protocolo, "protocolo prospectivo não garante corte pré-rodada"

    print(
        f"Site V3 OK | R{rodada} | jogadores={len(jogadores)} | "
        f"elegíveis={len(elegiveis)} | posições={dict(sorted(pos.items()))} | "
        f"mobile=OK | histórico_prospectivo=OK"
    )


if __name__ == "__main__":
    main()
