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
    "pitch", "bench", "alternatives", "historyChart", "historyAudit", "modal", "modalContent",
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
    assert not (REQUIRED_PAGES - parser.ids), f"abas ausentes: {sorted(REQUIRED_PAGES - parser.ids)}"
    assert not (REQUIRED_CONTROLS - parser.ids), f"controles ausentes: {sorted(REQUIRED_CONTROLS - parser.ids)}"

    # Linguagem pública e explicabilidade.
    assert "Cartola Estatístico V3" not in html, "versão técnica voltou ao título público"
    assert "Projeção V3" not in html and "V3-S por scouts" not in html, "rótulo técnico voltou à interface pública"
    assert "Parcela explicada por scouts" in html, "rótulo amigável da decomposição ausente"
    assert "function scoutAllowed" in html, "filtro de scouts por posição ausente"
    assert "s.esperado??s.valor_esperado??s.expected" in html, "campo real de expected scout não é lido corretamente"
    assert "['GOL','LAT','ZAG'].includes(pos)" in html, "saldo de gol não está limitado às posições corretas"
    assert "['DP','DE','GS'].includes(scout)" in html, "scouts exclusivos de goleiro não estão protegidos"

    # Alternativas pós-escalação.
    assert "Outras boas opções" in html, "seção de alternativas ausente"
    assert "slice(0,3)" in html and "renderAlternatives" in html, "não há três alternativas por posição"
    assert "!used.has(String(p.atleta_id))" in html, "alternativas podem repetir campo/banco"

    # UX/mobile.
    assert 'name="viewport"' in html, "viewport responsivo ausente"
    assert "@media(max-width:700px)" in html, "breakpoint mobile principal ausente"
    assert "@media(max-width:430px)" in html, "breakpoint estreito ausente"
    assert "scrollbar-width:none" in html and "-webkit-overflow-scrolling:touch" in html, "rolagem touch incompleta"
    assert ".player-ball{width:64px}" in html, "campo mobile pode estourar horizontalmente"
    assert "grid-template-columns:1fr" in html, "controles não colapsam em telas estreitas"

    # Histórico principal = Time Sugerido projetado x real.
    assert "Histórico do Time Sugerido" in html, "Histórico principal não é da escalação sugerida"
    assert "times_sugeridos" in html, "Histórico não consome snapshots de times sugeridos"
    assert "pontuacao_real" in html and "projecao" in html, "gráfico não compara projetado e real"
    assert "Não reconstruímos times antigos" in html, "proteção contra reconstrução retroativa não está explícita"

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
    assert isinstance(prospectivo.get("rodadas") or [], list), "avaliação prospectiva sem lista de rodadas"
    assert isinstance(prospectivo.get("times_sugeridos") or [], list), "avaliação prospectiva sem times sugeridos"
    protocolo = str(prospectivo.get("protocolo") or "").lower()
    # O protocolo pode descrever o corte temporal como "antes da rodada" ou,
    # de forma mais forte, exigir prova de mercado aberto no congelamento.
    # Em ambos os casos a ausência de reconstrução retroativa é obrigatória.
    if "times_sugeridos" in prospectivo:
        corte_pre_rodada = "antes da rodada" in protocolo or "mercado aberto" in protocolo
        sem_retroatividade = "nenhuma reconstrução retroativa" in protocolo or "não são reconstru" in protocolo
        assert corte_pre_rodada and sem_retroatividade, "protocolo não protege o histórico real"

    print(
        f"Site OK | R{rodada} | jogadores={len(jogadores)} | elegíveis={len(elegiveis)} | "
        f"posições={dict(sorted(pos.items()))} | scouts_posicionais=OK | alternativas=OK | histórico_time=OK | mobile=OK"
    )


if __name__ == "__main__":
    main()
