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
    "customBudget", "customFormation", "buildCustom", "clearCustom", "customPickers",
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
    assert "Parcela por scouts" in html or "Parcela explicada por scouts" in html, "rótulo amigável da decomposição ausente"
    assert "function scoutAllowed" in html, "filtro de scouts por posição ausente"
    assert "s.esperado??s.valor_esperado??s.expected" in html, "campo real de expected scout não é lido corretamente"
    assert "['GOL','LAT','ZAG'].includes(pos)" in html, "saldo de gol não está limitado às posições corretas"
    assert "['DP','DE','GS'].includes(scout)" in html, "scouts exclusivos de goleiro não estão protegidos"
    assert "bindPlayerClicks" in html, "detalhes por clique não estão centralizados"

    # Banco e alternativas pós-escalação.
    assert "Outras boas opções" in html, "seção de alternativas ausente"
    assert "slice(0,3)" in html and "renderAlternatives" in html, "não há três alternativas por posição"
    assert "!used.has(String(p.atleta_id))" in html, "alternativas podem repetir campo/banco"
    assert "data-player-id" in html, "banco/alternativas não são clicáveis"
    assert "POS_ORDER" in html and "team.bench||[]).slice().sort" in html, "banco não é ordenado por posição"
    assert "fixture(p)" in html and "fixture-tag" in html, "clube/adversário/mando não estão claros"

    # UX/mobile.
    assert 'name="viewport"' in html, "viewport responsivo ausente"
    assert "@media(max-width:700px)" in html, "breakpoint mobile principal ausente"
    assert "@media(max-width:430px)" in html, "breakpoint estreito ausente"
    assert "scrollbar-width:none" in html and "-webkit-overflow-scrolling:touch" in html, "rolagem touch incompleta"
    assert ".pitch{min-height:395px" in html, "campo mobile não recebeu compactação aprovada"
    assert ".player-ball{width:70px}" in html, "largura dos atletas no campo mobile diverge do layout aprovado"
    assert ".bench{grid-template-columns:1fr}" in html, "banco não colapsa verticalmente no mobile"
    assert "grid-template-columns:1fr" in html, "controles não colapsam em telas estreitas"
    assert "[['Projeção do time'" in html and "['Banco'" not in html, "card redundante do banco voltou ao resumo"

    # Monte seu Time: seleção manual + complemento do modelo.
    assert "customPickers" in html and "custom-pick" in html, "seleção manual do Monte seu Time ausente"
    assert "optimizeWithForced" in html, "modelo não completa escolhas manuais"
    assert "Montar / completar" in html or "Completar" in html, "ação de complemento do time não está explícita"

    # Análise da rodada.
    assert "teamStars" in html and "match-stars" in html, "destaques por posição nos confrontos ausentes"
    assert "Raio-X da Rodada" in html and "Confrontos" in html, "Raio-X/confrontos ausentes"

    # Histórico principal = Time Sugerido projetado x real, sem retroatividade.
    assert "Histórico do Time Sugerido" in html, "Histórico principal não é da escalação sugerida"
    assert "times_sugeridos" in html, "Histórico não consome snapshots de times sugeridos"
    assert "pontuacao_real" in html and "projecao" in html, "gráfico/histórico não compara projetado e real"
    assert "não" in html.lower() and "retro" in html.lower(), "proteção contra reconstrução retroativa não está explícita"
    assert "entra_no_historico_publico===true" in html, "Histórico não respeita o gate prospectivo"

    # Metodologia ampliada.
    for termo in (
        "Corte temporal e anti-vazamento", "Scouts esperados e explicabilidade", "Modelos candidatos",
        "Validação walk-forward", "Otimização da escalação", "Capitão, banco e Reserva de Luxo",
        "Histórico prospectivo", "Escala de processamento por rodada", "Exemplo didático",
    ):
        assert termo in html, f"metodologia incompleta: {termo}"
    assert "methodRuntime" in html and "methodStats" in html, "métricas reais do pipeline não aparecem na metodologia"

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
    if "times_sugeridos" in prospectivo:
        corte_pre_rodada = "antes da rodada" in protocolo or "mercado aberto" in protocolo
        sem_retroatividade = "nenhuma reconstrução retroativa" in protocolo or "não são reconstru" in protocolo
        assert corte_pre_rodada and sem_retroatividade, "protocolo não protege o histórico real"

    print(
        f"Site OK | R{rodada} | jogadores={len(jogadores)} | elegíveis={len(elegiveis)} | "
        f"posições={dict(sorted(pos.items()))} | scouts=OK | banco=OK | alternativas=OK | "
        f"monte_time=OK | análise=OK | histórico=OK | metodologia=OK | mobile=OK"
    )


if __name__ == "__main__":
    main()
