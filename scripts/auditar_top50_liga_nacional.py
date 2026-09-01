#!/usr/bin/env python3
"""Audita fontes públicas para o estudo Top 50 da liga Nacional oficial do Cartola.

Objetivo científico:
- descobrir se o ranking nacional atual pode ser obtido de fonte oficial/reproduzível;
- tratar como alvo a liga oficial exibida pelo Cartola em "Ligas do Cartola > Nacional > Clássica";
- extrair ids dos times somente quando a estrutura da resposta for inequívoca;
- nunca exigir autenticação nem armazenar credenciais;
- nunca inferir Top 50 a partir de popularidade ou de uma liga criada por usuário com nome parecido;
- produzir relatório explícito quando a fonte não estiver confirmada.

Este script é deliberadamente conservador. Ele prepara o estudo comportamental
sem contaminar o laboratório de projeção e sem tocar no repositório V2.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote

import requests

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "data" / "reports" / "top50-liga-nacional-viabilidade.json"
RAW_DIR = ROOT / "data" / "raw" / "top50-liga-nacional"
TIMEOUT = 15
HEADERS = {
    "User-Agent": "cartola-estatistico-scouts-v3/1.0 (scientific audit)",
    "Accept": "application/json,text/plain,*/*",
}


@dataclass
class Probe:
    nome: str
    url: str
    tipo: str = "descoberta"
    http_status: int | None = None
    content_type: str | None = None
    json_valido: bool = False
    requer_auth: bool = False
    contem_times: bool = False
    quantidade_times_detectada: int = 0
    identidade_nacional_detectada: bool = False
    candidato_promocao: bool = False
    erro: str | None = None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_json(url: str) -> tuple[requests.Response | None, Any | None, str | None]:
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    except requests.RequestException as exc:
        return None, None, f"{type(exc).__name__}: {exc}"
    try:
        data = r.json()
    except ValueError:
        data = None
    return r, data, None


def iter_dicts(obj: Any) -> Iterable[dict[str, Any]]:
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from iter_dicts(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from iter_dicts(value)


def team_candidate(d: dict[str, Any]) -> bool:
    id_keys = {"time_id", "timeId", "id"}
    name_keys = {"nome", "nome_time", "time_nome"}
    has_id = any(k in d for k in id_keys)
    has_name = any(k in d for k in name_keys)
    has_team_signal = (
        "nome_cartola" in d
        or "url_escudo_png" in d
        or "slug" in d
        or "patrimonio" in d
        or "pontos" in d
        or "ranking" in d
    )
    return has_id and has_name and has_team_signal


def extract_team_candidates(data: Any) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for d in iter_dicts(data):
        if not team_candidate(d):
            continue
        team_id = d.get("time_id", d.get("timeId", d.get("id")))
        if team_id is None:
            continue
        key = str(team_id)
        if key in seen:
            continue
        seen.add(key)
        out.append(d)
    return out


def numeric_points(d: dict[str, Any]) -> float | None:
    pontos = d.get("pontos")
    candidates: list[Any] = []
    if isinstance(pontos, dict):
        candidates.extend([pontos.get("campeonato"), pontos.get("total")])
    candidates.extend([
        d.get("pontos_campeonato"),
        d.get("pontos_total"),
        d.get("pontuacao"),
    ])
    for value in candidates:
        try:
            if value is not None:
                return float(value)
        except (TypeError, ValueError):
            pass
    return None


def normalize_team(d: dict[str, Any]) -> dict[str, Any]:
    ranking = d.get("ranking") if isinstance(d.get("ranking"), dict) else {}
    pontos = d.get("pontos") if isinstance(d.get("pontos"), dict) else {}
    return {
        "time_id": d.get("time_id", d.get("timeId", d.get("id"))),
        "nome": d.get("nome", d.get("nome_time", d.get("time_nome"))),
        "nome_cartola": d.get("nome_cartola"),
        "slug": d.get("slug"),
        "patrimonio": d.get("patrimonio"),
        "pontos_campeonato": numeric_points(d),
        "ranking_campeonato": ranking.get("campeonato", d.get("ranking_campeonato")),
        "ranking_rodada": ranking.get("rodada", d.get("ranking_rodada")),
        "pontos_rodada": pontos.get("rodada", d.get("pontos_rodada")),
    }


def ranking_is_credible(teams: list[dict[str, Any]]) -> bool:
    if len(teams) < 50:
        return False
    ranks = []
    points = []
    for t in teams:
        rank = t.get("ranking_campeonato")
        if isinstance(rank, (int, float)):
            ranks.append(float(rank))
        if isinstance(t.get("pontos_campeonato"), (int, float)):
            points.append(float(t["pontos_campeonato"]))
    return len(ranks) >= 40 or len(points) >= 40


def identity_is_nacional(data: Any) -> bool:
    """Procura identidade inequívoca da liga oficial Nacional no payload.

    Não basta a palavra aparecer em texto solto. Exigimos um objeto com nome/slug
    compatível e sinais de entidade de liga. A busca pública serve apenas para
    descoberta; ela nunca é promovida automaticamente a coorte.
    """
    for d in iter_dicts(data):
        nome = str(d.get("nome") or "").strip().casefold()
        slug = str(d.get("slug") or "").strip().casefold()
        has_league_signal = any(
            k in d
            for k in (
                "liga_id",
                "tipo",
                "editorial",
                "patrocinador",
                "quantidade_times",
                "url_flamula_svg",
                "url_flamula_png",
            )
        )
        if has_league_signal and (nome == "nacional" or slug == "nacional"):
            return True
    return False


def main() -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    # Fontes de descoberta podem revelar slug/metadados, mas NÃO podem ser
    # promovidas sozinhas, pois existem ligas de usuários com nomes parecidos.
    candidates: list[tuple[str, str, str]] = []
    for q in ("Nacional", "Liga Nacional", "liga nacional"):
        candidates.extend([
            (f"busca_ligas_{q}", f"https://api.cartolafc.globo.com/ligas?q={quote(q)}", "descoberta"),
            (f"busca_geral_{q}", f"https://api.cartolafc.globo.com/busca?q={quote(q)}", "descoberta"),
        ])

    # Endpoints historicamente documentados pelo ecossistema Cartola. São
    # auditados porque pertencem aos hosts oficiais; respostas 401/403 são
    # registradas como bloqueio legítimo, nunca contornadas.
    candidates.extend([
        ("liga_publica_nacional", "https://api.cartolafc.globo.com/liga/nacional", "direta"),
        ("liga_auth_nacional", "https://api.cartolafc.globo.com/auth/liga/nacional", "direta"),
        ("campeoes_nacionais", "https://api.cartolafc.globo.com/logged/ligas/campeoes-nacionais", "direta"),
        ("rankings_cartola", "https://api.cartola.globo.com/rankings", "ranking_oficial"),
    ])

    probes: list[Probe] = []
    credible_source: dict[str, Any] | None = None
    all_payloads: dict[str, Any] = {}

    for nome, url, tipo in candidates:
        probe = Probe(nome=nome, url=url, tipo=tipo)
        response, data, error = get_json(url)
        if error:
            probe.erro = error
            probes.append(probe)
            continue
        assert response is not None
        probe.http_status = response.status_code
        probe.content_type = response.headers.get("content-type")
        probe.requer_auth = response.status_code in (401, 403)
        probe.json_valido = data is not None

        if data is not None:
            all_payloads[nome] = data
            probe.identidade_nacional_detectada = identity_is_nacional(data)
            raw_candidates = extract_team_candidates(data)
            normalized = [normalize_team(x) for x in raw_candidates]
            probe.quantidade_times_detectada = len(normalized)
            probe.contem_times = len(normalized) > 0

            # Descoberta nunca promove coorte. Em uma rota direta, exigimos a
            # identidade Nacional. Em um endpoint explicitamente de ranking
            # oficial, a própria semântica da rota é aceita como identidade,
            # mas a massa de ranking/pontos ainda precisa passar o gate.
            source_identity_ok = (
                tipo == "ranking_oficial" or (tipo == "direta" and probe.identidade_nacional_detectada)
            )
            probe.candidato_promocao = source_identity_ok and ranking_is_credible(normalized)

            if credible_source is None and probe.candidato_promocao:
                def sort_key(t: dict[str, Any]) -> tuple[int, float]:
                    rank = t.get("ranking_campeonato")
                    if isinstance(rank, (int, float)) and rank > 0:
                        return (0, float(rank))
                    pts = t.get("pontos_campeonato")
                    return (1, -float(pts) if isinstance(pts, (int, float)) else float("inf"))

                top = sorted(normalized, key=sort_key)[:50]
                credible_source = {"nome": nome, "url": url, "top50": top}
        probes.append(probe)

    raw_snapshot = RAW_DIR / "auditoria-fontes.json"
    raw_snapshot.write_text(
        json.dumps(
            {
                "capturado_em": now_iso(),
                "alvo_confirmado": {
                    "nome": "Nacional",
                    "categoria_interface": "Ligas do Cartola",
                    "tipo_interface": "Clássica",
                },
                "payloads": all_payloads,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    if credible_source:
        top50_path = RAW_DIR / "top50-atual.json"
        top50_path.write_text(
            json.dumps(
                {
                    "capturado_em": now_iso(),
                    "liga": {
                        "nome": "Nacional",
                        "categoria_interface": "Ligas do Cartola",
                        "tipo_interface": "Clássica",
                    },
                    "fonte": {"nome": credible_source["nome"], "url": credible_source["url"]},
                    "top50": credible_source["top50"],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        status = "FONTE_PUBLICA_CONFIRMADA"
        proximo_passo = (
            "Usar os time_id confirmados para coletar /time/id/{id}/{rodada} e reconstruir "
            "estrategias rodada a rodada, preservando snapshot do ranking usado para definir a coorte."
        )
    else:
        status = "FONTE_PUBLICA_NAO_CONFIRMADA"
        proximo_passo = (
            "A fonte pública ainda não entregou uma coorte inequívoca da liga oficial Nacional. "
            "Próxima alternativa segura: observar no navegador a requisição que a própria tela "
            "Nacional faz e registrar apenas endpoint/estrutura sanitizada, sem senha, cookie ou token."
        )

    report = {
        "gerado_em": now_iso(),
        "estudo": "Top 50 Nacional oficial - viabilidade e proveniencia",
        "alvo_confirmado": {
            "nome": "Nacional",
            "categoria_interface": "Ligas do Cartola",
            "tipo_interface": "Clássica",
        },
        "status": status,
        "regras": {
            "v2_read_only": True,
            "sem_autenticacao": True,
            "sem_credenciais": True,
            "sem_proxy_por_popularidade": True,
            "sem_liga_homonima_de_usuario": True,
            "coorte_deve_ser_reproduzivel": True,
            "historico_deve_respeitar_rodada": True,
        },
        "probes": [asdict(p) for p in probes],
        "fonte_confirmada": (
            {"nome": credible_source["nome"], "url": credible_source["url"], "n": 50}
            if credible_source
            else None
        ),
        "metricas_planejadas": [
            "formacao por rodada",
            "capitao e multiplicador",
            "concentracao por clube",
            "mando e adversario",
            "perfil de preco e patrimonio",
            "popularidade versus diferenciais quando disponivel pre-rodada",
            "persistencia e rotacao de atletas",
            "exposicao por posicao",
            "scouts realizados dos atletas escolhidos",
            "aderencia ao ranking V2/V3 usando apenas previsoes que existiam antes da rodada",
        ],
        "proximo_passo": proximo_passo,
        "snapshot_fontes": str(raw_snapshot.relative_to(ROOT)),
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": status, "report": str(REPORT.relative_to(ROOT))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
