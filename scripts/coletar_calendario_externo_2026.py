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

COMPETITIONS = {
    "libertadores": {
        "espn": "conmebol.libertadores",
        "sofascore": 384,
        "openfootball": "copa-libertadores/2026_copal.txt",
    },
    "sulamericana": {
        "espn": "conmebol.sudamericana",
        "sofascore": 480,
        "openfootball": None,
    },
    "copa_do_brasil": {
        "espn": "bra.copa_do_brazil",
        "sofascore": 373,
        "openfootball": None,
    },
}
ESPN_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard"
SOFA_BASE = "https://www.sofascore.com/api/v1"
OPENFOOTBALL_BASE = "https://raw.githubusercontent.com/openfootball/south-america/master"
OPENFOOTBALL_REPO = "openfootball/south-america"


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
        "atleticomg": "atlético-mg", "atleticomineiro": "atlético-mg", "clubatleticomineiro": "atlético-mg",
        "atleticopr": "athletico-pr", "athleticopr": "athletico-pr", "athleticoparanaense": "athletico-pr", "clubathleticoparanaense": "athletico-pr",
        "redbullbragantino": "bragantino", "rbbragantino": "bragantino",
        "vascodagama": "vasco", "crvascodagama": "vasco",
        "gremio": "grêmio", "internacional": "internacional", "scinternacional": "internacional",
        "corinthians": "corinthians", "sccorinthianspaulista": "corinthians",
        "palmeiras": "palmeiras", "sepalmeiras": "palmeiras",
        "santos": "santos", "santosfc": "santos",
        "saopaulo": "são paulo", "saopaulofc": "são paulo",
        "flamengo": "flamengo", "crflamengo": "flamengo",
        "fluminense": "fluminense", "fluminensefc": "fluminense",
        "botafogo": "botafogo", "botafogofr": "botafogo",
        "cruzeiro": "cruzeiro", "cruzeiroec": "cruzeiro",
        "bahia": "bahia", "ecbahia": "bahia",
        "fortaleza": "fortaleza", "fortalezaec": "fortaleza",
        "ceara": "ceará", "cearasc": "ceará",
        "sportrecife": "sport", "sportclubdorecife": "sport",
        "vitoria": "vitória", "ecvitoria": "vitória",
        "mirassol": "mirassol", "mirassolfc": "mirassol",
        "juventude": "juventude", "ecjuventude": "juventude",
    }
    alias_to_id = {}
    for alias, target in aliases.items():
        ids = by_name.get(normalize(target), [])
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
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140 Safari/537.36",
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


def _get_text(session: requests.Session, url: str, attempts: int = 3):
    last_error = None
    for attempt in range(attempts):
        try:
            response = session.get(url, timeout=30)
            response.raise_for_status()
            response.encoding = "utf-8"
            return response.text
        except requests.RequestException as exc:
            last_error = exc
            if attempt < attempts - 1:
                time.sleep(1.5 * (attempt + 1))
    raise last_error


def fetch_espn(league_slug: str, start: date, end: date):
    events = {}
    session = _session()
    session.headers.update({"Referer": "https://www.espn.com/", "Origin": "https://www.espn.com"})
    for ini, fim in month_windows(start, end):
        payload = _get_json(session, ESPN_URL.format(league=league_slug), params={"dates": f"{ini:%Y%m%d}-{fim:%Y%m%d}", "limit": 1000})
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


def fetch_sofascore(tournament_id: int):
    session = _session()
    session.headers.update({"Referer": "https://www.sofascore.com/"})
    season_id = sofascore_season_id(session, tournament_id)
    events = {}
    page = 0
    while page < 30:
        payload = _get_json(session, f"{SOFA_BASE}/unique-tournament/{tournament_id}/season/{season_id}/events/last/{page}")
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


def fetch_openfootball(path: str):
    session = _session()
    url = f"{OPENFOOTBALL_BASE}/{path}"
    text = _get_text(session, url)
    if not text.strip():
        raise RuntimeError(f"OpenFootball: arquivo vazio em {path}")
    return text, url


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
            cid, method = map_team_values([
                ("displayName", team.get("displayName")), ("shortDisplayName", team.get("shortDisplayName")),
                ("name", team.get("name")), ("location", team.get("location")),
            ], by_name, alias_to_id)
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
        parsed.append({"evento_id": f"espn:{event.get('id')}", "competicao": comp, "fonte_evento": "espn", "league_slug": slug, "data": dt.astimezone(timezone.utc).isoformat(), "nome_evento": event.get("name") or event.get("shortName"), "clubes_cartola_ids": ids, "times": mapped, "status": status.get("name") or status.get("state") or "completed"})
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
            cid, method = map_team_values([("name", team.get("name")), ("shortName", team.get("shortName")), ("slug", team.get("slug"))], by_name, alias_to_id)
            mapped.append({"homeAway": side, "source_id": team.get("id"), "nome": team.get("name") or team.get("shortName"), "abreviacao": team.get("nameCode"), "clube_id": cid, "metodo_match": method})
        ids = sorted({int(t["clube_id"]) for t in mapped if t.get("clube_id") is not None})
        if not ids:
            continue
        parsed.append({"evento_id": f"sofascore:{event.get('id')}", "competicao": comp, "fonte_evento": "sofascore", "tournament_id": tournament_id, "data": dt.isoformat(), "nome_evento": f"{mapped[0]['nome']} x {mapped[1]['nome']}", "clubes_cartola_ids": ids, "times": mapped, "status": status.get("description") or status.get("type") or "finished"})
        unmatched.extend({"competicao": comp, "nome": t.get("nome"), "abreviacao": t.get("abreviacao")} for t in mapped if t.get("clube_id") is None)
    return parsed, unmatched


DATE_RE = re.compile(r"^\s*(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2})(?:\s+(\d{4}))?\s*$")
MONTHS = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6, "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}
RESULT_RE = re.compile(r"(?:\s|^)(?:\d+-\d+|\d+-\d+\s+pen\.)")
COUNTRY_RE = re.compile(r"\s+\([A-Z]{3}\)\s*$")


def _clean_openfootball_team(value: str) -> str:
    value = COUNTRY_RE.sub("", value.strip())
    return re.sub(r"\s+", " ", value).strip()


def parse_openfootball(comp, path, text, by_name, alias_to_id, end):
    parsed, unmatched = [], []
    current_date = None
    current_year = YEAR
    for raw_line in text.splitlines():
        dm = DATE_RE.match(raw_line)
        if dm:
            month, day, year = dm.groups()
            if year:
                current_year = int(year)
            try:
                current_date = date(current_year, MONTHS[month], int(day))
            except ValueError:
                current_date = None
            continue
        if current_date is None or current_date.year != YEAR or current_date > end:
            continue
        line = raw_line.strip()
        if " v " not in line or not RESULT_RE.search(line) or "[cancelled]" in line.lower():
            continue
        line = re.sub(r"^\d{1,2}:\d{2}\s+", "", line)
        result_match = RESULT_RE.search(line)
        if not result_match:
            continue
        fixture = line[:result_match.start()].rstrip()
        if " v " not in fixture:
            continue
        home_raw, away_raw = fixture.split(" v ", 1)
        home, away = _clean_openfootball_team(home_raw), _clean_openfootball_team(away_raw)
        if not home or not away or home == "N.N." or away == "N.N.":
            continue
        mapped = []
        for side, name in (("home", home), ("away", away)):
            cid, method = map_team_values([("openfootball_name", name)], by_name, alias_to_id)
            mapped.append({"homeAway": side, "source_id": None, "nome": name, "abreviacao": None, "clube_id": cid, "metodo_match": method})
        ids = sorted({int(t["clube_id"]) for t in mapped if t.get("clube_id") is not None})
        if not ids:
            continue
        dt = datetime.combine(current_date, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=12)
        parsed.append({
            "evento_id": f"openfootball:{comp}:{current_date.isoformat()}:{normalize(home)}:{normalize(away)}",
            "competicao": comp, "fonte_evento": "openfootball", "source_repo": OPENFOOTBALL_REPO,
            "source_path": path, "data": dt.isoformat(), "nome_evento": f"{home} x {away}",
            "clubes_cartola_ids": ids, "times": mapped, "status": "completed",
        })
        unmatched.extend({"competicao": comp, "nome": t.get("nome"), "abreviacao": None} for t in mapped if t.get("clube_id") is None)
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
        provider_errors = {}
        try:
            raw = fetch_espn(cfg["espn"], start, end)
            parsed, um = parse_espn(comp, cfg["espn"], raw, by_name, alias_to_id, end)
            unmatched.extend(um)
            sources[comp] = {"fonte": "espn", "slug": cfg["espn"], "eventos_recebidos": len(raw), "eventos_mapeados": len(parsed), "status": "ok" if parsed else "sem_cobertura_mapeada"}
        except Exception as exc:
            provider_errors["espn"] = str(exc)[:400]

        if not parsed:
            try:
                raw, season_id = fetch_sofascore(cfg["sofascore"])
                parsed, um = parse_sofascore(comp, cfg["sofascore"], raw, by_name, alias_to_id, end)
                unmatched.extend(um)
                sources[comp] = {"fonte": "sofascore", "tournament_id": cfg["sofascore"], "season_id": season_id, "eventos_recebidos": len(raw), "eventos_mapeados": len(parsed), "status": "ok" if parsed else "sem_cobertura_mapeada", "fallback_de": "espn"}
            except Exception as exc:
                provider_errors["sofascore"] = str(exc)[:400]

        if not parsed and cfg.get("openfootball"):
            try:
                text, url = fetch_openfootball(cfg["openfootball"])
                parsed, um = parse_openfootball(comp, cfg["openfootball"], text, by_name, alias_to_id, end)
                unmatched.extend(um)
                sources[comp] = {
                    "fonte": "openfootball", "repositorio": OPENFOOTBALL_REPO, "path": cfg["openfootball"],
                    "url_raw": url, "licenca": "CC0-1.0 conforme repositório upstream",
                    "eventos_recebidos": sum(1 for line in text.splitlines() if " v " in line and RESULT_RE.search(line)),
                    "eventos_mapeados": len(parsed), "status": "ok" if parsed else "sem_cobertura_mapeada",
                    "fallback_de": ["espn", "sofascore"],
                }
            except Exception as exc:
                provider_errors["openfootball"] = str(exc)[:400]

        if not parsed:
            existing_comp = [e for e in prior_events.values() if e.get("competicao") == comp]
            sources[comp] = {
                "fonte": "snapshot", "slug": cfg["espn"], "tournament_id": cfg["sofascore"],
                "openfootball_path": cfg.get("openfootball"), "eventos_recebidos": len(existing_comp),
                "eventos_mapeados": len(existing_comp), "status": "snapshot_anterior" if existing_comp else "indisponivel",
            }
            errors.append({"competicao": comp, **{f"erro_{k}": v for k, v in provider_errors.items()}})
            continue
        if provider_errors:
            sources[comp]["erros_fallback_anteriores"] = provider_errors
        for event in parsed:
            collected[event["evento_id"]] = event

    relevant = sorted([
        e for e in collected.values() if e.get("competicao") in COMPETITIONS
        and str(e.get("data", ""))[:4] == str(YEAR) and str(e.get("data", ""))[:10] <= end.isoformat()
    ], key=lambda e: (e.get("data", ""), e.get("evento_id", "")))
    counts = {}
    for comp in COMPETITIONS:
        rows = [e for e in relevant if e.get("competicao") == comp]
        counts[comp] = {"eventos_com_clube_cartola": len(rows), "clubes_cartola_distintos": len({cid for e in rows for cid in e.get("clubes_cartola_ids", [])})}

    comps_ok = sum(1 for v in counts.values() if v["eventos_com_clube_cartola"] > 0)
    coverage_ok = comps_ok >= 2 and len(relevant) >= 10
    dedup_unmatched = sorted({(x["competicao"], str(x.get("nome")), str(x.get("abreviacao"))) for x in unmatched})
    payload = {
        "gerado_em": datetime.now(timezone.utc).isoformat(), "temporada": YEAR,
        "status_coleta": "ok" if coverage_ok else ("parcial" if relevant else "indisponivel"),
        "cobertura_suficiente_para_ablation": coverage_ok,
        "fontes_prioridade": ["ESPN scoreboard JSON público", "Sofascore API pública", "OpenFootball/openfootball/south-america (arquivo versionado, quando disponível)", "snapshot versionado anterior"],
        "fonte": "Coleta redundante ESPN/Sofascore/OpenFootball, com snapshot versionado e gate de cobertura sem imputação artificial de ausência.",
        "regra_match_clubes": "Nome/slug exato normalizado ou alias explícito. Sigla curta isolada é proibida para evitar colisão internacional.",
        "regra_anti_leakage": "Somente partidas concluídas são armazenadas. Features filtram data_externa < data_da_partida_alvo; placares/resultados não são usados como features.",
        "regra_cobertura": "Ablation somente com >=2 competições contendo jogos de clubes Cartola e >=10 eventos totais. Adicionar uma fonte não reduz esse gate.",
        "janela_coletada": {"inicio": start.isoformat(), "fim": end.isoformat()}, "fontes": sources,
        "erros_coleta": errors, "resumo": counts, "clubes_cartola": clubs,
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
