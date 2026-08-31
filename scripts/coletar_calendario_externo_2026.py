#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
import unicodedata
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "context" / "calendario-externo-2026.json"
YEAR = 2026

# ESPN permanece como primeira fonte. Sofascore é fallback público independente,
# usado somente quando a borda da ESPN bloqueia o runner. Os IDs abaixo são os
# uniqueTournament públicos exibidos nas próprias páginas dos torneios.
COMPETITIONS = {
    "libertadores": {"espn": "conmebol.libertadores", "sofascore": 384},
    "sulamericana": {"espn": "conmebol.sudamericana", "sofascore": 480},
    "copa_do_brasil": {"espn": "bra.copa_do_brazil", "sofascore": 373},
}
ESPN_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard"
SOFA_BASE = "https://www.sofascore.com/api/v1"


def normalize(value: str | None) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    text = re.sub(r"\b(futebol|football|futbol|clube|club|esporte|sport|associacao|sociedade|saf)\b", " ", text)
    return re.sub(r"[^a-z0-9]+", "", text)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def cartola_clubs():
    folders = sorted(RAW.glob("rodada-*"), key=lambda p: int(p.name.split("-")[-1]), reverse=True)
    for folder in folders:
        path = folder / "partidas.json"
        if not path.exists():
            continue
        payload = load_json(path)
        clubes = payload.get("clubes", {})
        if clubes:
            result = {}
            for cid, c in clubes.items():
                cid = int(cid)
                result[cid] = {
                    "id": cid,
                    "nome": c.get("nome"),
                    "apelido": c.get("apelido"),
                    "abreviacao": str(c.get("abreviacao") or "").upper(),
                    "slug": c.get("slug"),
                }
            return result
    raise RuntimeError("Nenhum catálogo de clubes encontrado em data/raw/rodada-*/partidas.json")


def build_indexes(clubs):
    by_name = {}
    for cid, c in clubs.items():
        for value in (c["nome"], c["apelido"], c["slug"]):
            key = normalize(value)
            if key:
                by_name.setdefault(key, []).append(cid)

    aliases = {
        "atleticomg": "atlético-mg", "atleticomineiro": "atlético-mg",
        "atleticopr": "athletico-pr", "athleticopr": "athletico-pr", "athleticoparanaense": "athletico-pr",
        "redbullbragantino": "bragantino", "rbbragantino": "bragantino",
        "vascodagama": "vasco", "crvascodagama": "vasco",
        "gremio": "grêmio", "internacional": "internacional",
        "corinthians": "corinthians", "palmeiras": "palmeiras", "santos": "santos",
        "saopaulo": "são paulo", "flamengo": "flamengo", "fluminense": "fluminense",
        "botafogo": "botafogo", "cruzeiro": "cruzeiro", "bahia": "bahia",
        "fortaleza": "fortaleza", "ceara": "ceará", "sportrecife": "sport",
        "vitoria": "vitória", "mirassol": "mirassol", "juventude": "juventude",
    }
    alias_to_id = {}
    for alias, target in aliases.items():
        target_n = normalize(target)
        ids = by_name.get(target_n, [])
        if len(ids) == 1:
            alias_to_id[normalize(alias)] = ids[0]
    return by_name, alias_to_id


def map_team_values(values, by_name, alias_to_id):
    """Mapeia por identidade textual; sigla curta isolada é deliberadamente proibida."""
    for field, value in values:
        key = normalize(value)
        if not key:
            continue
        ids = by_name.get(key, [])
        if len(ids) == 1:
            return ids[0], f"nome:{field}"
        if key in alias_to_id:
            return alias_to_id[key], f"alias:{field}"
    return None, None


def month_windows(start: date, end: date):
    cur = date(start.year, start.month, 1)
    while cur <= end:
        nxt = date(cur.year + 1, 1, 1) if cur.month == 12 else date(cur.year, cur.month + 1, 1)
        last = min(end, nxt - timedelta(days=1))
        yield max(start, cur), last
        cur = nxt


def _session() -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
    })
    return session


def _get_json(session: requests.Session, url: str, params=None, attempts: int = 3):
    last_error = None
    for attempt in range(attempts):
        try:
            response = session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            if attempt < attempts - 1:
                time.sleep(1.5 * (attempt + 1))
    raise last_error


def fetch_espn(league_slug: str, start: date, end: date):
    events = {}
    session = _session()
    session.headers.update({"Referer": "https://www.espn.com/", "Origin": "https://www.espn.com"})
    for ini, fim in month_windows(start, end):
        payload = _get_json(
            session,
            ESPN_URL.format(league=league_slug),
            params={"dates": f"{ini:%Y%m%d}-{fim:%Y%m%d}", "limit": 1000},
        )
        for event in payload.get("events", []):
            if event.get("id"):
                events[str(event["id"])] = event
        time.sleep(0.15)
    return list(events.values())


def sofascore_season_id(session: requests.Session, tournament_id: int) -> int:
    payload = _get_json(session, f"{SOFA_BASE}/unique-tournament/{tournament_id}/seasons")
    for season in payload.get("seasons", []):
        if str(season.get("year")) == str(YEAR) or str(YEAR) in str(season.get("name", "")):
            return int(season["id"])
    raise RuntimeError(f"Sofascore: temporada {YEAR} não encontrada para torneio {tournament_id}")


def fetch_sofascore(tournament_id: int, end: date):
    session = _session()
    session.headers.update({"Referer": "https://www.sofascore.com/"})
    season_id = sofascore_season_id(session, tournament_id)
    events = {}
    page = 0
    while page < 30:
        payload = _get_json(
            session,
            f"{SOFA_BASE}/unique-tournament/{tournament_id}/season/{season_id}/events/last/{page}",
        )
        rows = payload.get("events", [])
        for event in rows:
            if event.get("id") is not None:
                events[str(event["id"])] = event
        if not payload.get("hasNextPage") or not rows:
            break
        page += 1
        time.sleep(0.12)
    if not events:
        raise RuntimeError(f"Sofascore: nenhum evento retornado para torneio {tournament_id}, temporada {season_id}")
    return list(events.values()), season_id


def parse_espn(comp, slug, raw_events, by_name, alias_to_id, end):
    parsed, unmatched = [], []
    for event in raw_events:
        contests = event.get("competitions") or []
        if not contests:
            continue
        contest = contests[0]
        status = (event.get("status") or {}).get("type") or {}
        if not status.get("completed", False):
            continue
        mapped = []
        for competitor in contest.get("competitors") or []:
            team = competitor.get("team") or {}
            cid, method = map_team_values(
                [("displayName", team.get("displayName")), ("shortDisplayName", team.get("shortDisplayName")), ("name", team.get("name")), ("location", team.get("location"))],
                by_name, alias_to_id,
            )
            mapped.append({"homeAway": competitor.get("homeAway"), "source_id": team.get("id"), "nome": team.get("displayName") or team.get("shortDisplayName"), "abreviacao": team.get("abbreviation"), "clube_id": cid, "metodo_match": method})
        ids = sorted({int(t["clube_id"]) for t in mapped if t.get("clube_id") is not None})
        if not ids:
            continue
        try:
            dt = datetime.fromisoformat(str(event.get("date")).replace("Z", "+00:00"))
        except Exception:
            continue
        if dt.year != YEAR or dt.date() > end:
            continue
        eid = f"espn:{event.get('id')}"
        parsed.append({"evento_id": eid, "competicao": comp, "fonte_evento": "espn", "league_slug": slug, "data": dt.astimezone(timezone.utc).isoformat(), "nome_evento": event.get("name") or event.get("shortName"), "clubes_cartola_ids": ids, "times": mapped, "status": status.get("name") or status.get("state") or "completed"})
        unmatched.extend({"competicao": comp, "nome": t.get("nome"), "abreviacao": t.get("abreviacao")} for t in mapped if t.get("clube_id") is None)
    return parsed, unmatched


def parse_sofascore(comp, tournament_id, raw_events, by_name, alias_to_id, end):
    parsed, unmatched = [], []
    for event in raw_events:
        status = event.get("status") or {}
        if status.get("type") not in {"finished", "afterpenalties", "afterextra"} and int(status.get("code") or 0) != 100:
            continue
        timestamp = event.get("startTimestamp")
        if not timestamp:
            continue
        dt = datetime.fromtimestamp(int(timestamp), tz=timezone.utc)
        if dt.year != YEAR or dt.date() > end:
            continue
        mapped = []
        for side, key in (("home", "homeTeam"), ("away", "awayTeam")):
            team = event.get(key) or {}
            cid, method = map_team_values(
                [("name", team.get("name")), ("shortName", team.get("shortName")), ("slug", team.get("slug"))],
                by_name, alias_to_id,
            )
            mapped.append({"homeAway": side, "source_id": team.get("id"), "nome": team.get("name") or team.get("shortName"), "abreviacao": team.get("nameCode"), "clube_id": cid, "metodo_match": method})
        ids = sorted({int(t["clube_id"]) for t in mapped if t.get("clube_id") is not None})
        if not ids:
            continue
        eid = f"sofascore:{event.get('id')}"
        parsed.append({"evento_id": eid, "competicao": comp, "fonte_evento": "sofascore", "tournament_id": tournament_id, "data": dt.isoformat(), "nome_evento": f"{mapped[0]['nome']} x {mapped[1]['nome']}", "clubes_cartola_ids": ids, "times": mapped, "status": status.get("description") or status.get("type") or "finished"})
        unmatched.extend({"competicao": comp, "nome": t.get("nome"), "abreviacao": t.get("abreviacao")} for t in mapped if t.get("clube_id") is None)
    return parsed, unmatched


def main():
    clubs = cartola_clubs()
    by_name, alias_to_id = build_indexes(clubs)
    start = date(YEAR, 1, 1)
    end = min(date.today(), date(YEAR, 12, 31))

    prior = load_json(OUT) if OUT.exists() and OUT.stat().st_size > 2 else {}
    prior_events = {str(e.get("evento_id")): e for e in prior.get("eventos", []) if e.get("evento_id")}
    collected = dict(prior_events)
    sources, errors, unmatched = {}, [], []

    for comp, cfg in COMPETITIONS.items():
        parsed = []
        espn_error = None
        try:
            raw = fetch_espn(cfg["espn"], start, end)
            parsed, um = parse_espn(comp, cfg["espn"], raw, by_name, alias_to_id, end)
            unmatched.extend(um)
            sources[comp] = {"fonte": "espn", "slug": cfg["espn"], "eventos_recebidos": len(raw), "eventos_mapeados": len(parsed), "status": "ok" if parsed else "sem_cobertura_mapeada"}
        except Exception as exc:
            espn_error = str(exc)[:400]

        # Fallback independente: também é acionado quando ESPN responde sem nenhum
        # evento brasileiro mapeável, pois isso é indistinguível de uma resposta
        # incompleta para o objetivo científico.
        if not parsed:
            try:
                raw, season_id = fetch_sofascore(cfg["sofascore"], end)
                parsed, um = parse_sofascore(comp, cfg["sofascore"], raw, by_name, alias_to_id, end)
                unmatched.extend(um)
                sources[comp] = {"fonte": "sofascore", "tournament_id": cfg["sofascore"], "season_id": season_id, "eventos_recebidos": len(raw), "eventos_mapeados": len(parsed), "status": "ok" if parsed else "sem_cobertura_mapeada", "fallback_de": "espn"}
                if espn_error:
                    sources[comp]["erro_espn"] = espn_error
            except Exception as sofa_exc:
                sources[comp] = {"fonte": "snapshot", "slug": cfg["espn"], "tournament_id": cfg["sofascore"], "eventos_recebidos": 0, "eventos_mapeados": 0, "status": "snapshot_anterior" if prior_events else "indisponivel"}
                errors.append({"competicao": comp, "erro_espn": espn_error, "erro_sofascore": str(sofa_exc)[:400]})
                continue

        for event in parsed:
            collected[event["evento_id"]] = event

    relevant = sorted(collected.values(), key=lambda e: (e.get("data", ""), e.get("evento_id", "")))
    counts = {}
    for comp in COMPETITIONS:
        rows = [e for e in relevant if e.get("competicao") == comp]
        counts[comp] = {"eventos_com_clube_cartola": len(rows), "clubes_cartola_distintos": len({cid for e in rows for cid in e.get("clubes_cartola_ids", [])})}

    # Cobertura científica exige ao menos duas competições com eventos brasileiros.
    # Uma resposta parcial não deve ser confundida com ausência de congestionamento.
    comps_ok = sum(1 for v in counts.values() if v["eventos_com_clube_cartola"] > 0)
    coverage_ok = comps_ok >= 2 and len(relevant) >= 10
    dedup_unmatched = sorted({(x["competicao"], str(x.get("nome")), str(x.get("abreviacao"))) for x in unmatched})
    payload = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "temporada": YEAR,
        "status_coleta": "ok" if coverage_ok and not errors else ("parcial" if relevant else "indisponivel"),
        "cobertura_suficiente_para_ablation": coverage_ok,
        "fontes_prioridade": ["ESPN scoreboard JSON público", "Sofascore API pública", "snapshot versionado anterior"],
        "fonte": "Coleta redundante pública ESPN/Sofascore; snapshot versionado no laboratório.",
        "regra_match_clubes": "Nome/slug exato normalizado ou alias explícito. Sigla curta isolada é proibida para evitar colisão internacional.",
        "regra_anti_leakage": "Somente partidas concluídas são armazenadas. Features filtram data_externa < data_da_partida_alvo; placares/resultados não são usados.",
        "janela_coletada": {"inicio": start.isoformat(), "fim": end.isoformat()},
        "fontes": sources,
        "erros_coleta": errors,
        "resumo": counts,
        "clubes_cartola": clubs,
        "nao_mapeados_em_eventos_relevantes": [{"competicao": a, "nome": b, "abreviacao": c} for a, b, c in dedup_unmatched],
        "eventos": relevant,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Calendário externo 2026:", counts, "| erros:", len(errors), "| eventos:", len(relevant), "| cobertura:", coverage_ok)
    if not coverage_ok:
        print("AVISO_CIENTIFICO: cobertura externa insuficiente; ablation deve bloquear inferência, nunca preencher ausência de fonte como zero jogos.")


if __name__ == "__main__":
    main()
