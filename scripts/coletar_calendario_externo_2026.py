#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import unicodedata
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "context" / "calendario-externo-2026.json"
YEAR = 2026
LEAGUES = {
    "libertadores": "conmebol.libertadores",
    "sulamericana": "conmebol.sudamericana",
    "copa_do_brasil": "bra.copa_do_brazil",
}
BASE_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard"


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
    by_abbr = {}
    by_name = {}
    for cid, c in clubs.items():
        abbr = c["abreviacao"]
        if abbr:
            by_abbr.setdefault(abbr, []).append(cid)
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
    return by_abbr, by_name, alias_to_id


def map_team(team, by_abbr, by_name, alias_to_id):
    abbr = str(team.get("abbreviation") or "").upper().strip()
    ids = by_abbr.get(abbr, [])
    if len(ids) == 1:
        return ids[0], "abreviacao"
    for field in ("displayName", "shortDisplayName", "name", "location"):
        key = normalize(team.get(field))
        ids = by_name.get(key, [])
        if len(ids) == 1:
            return ids[0], f"nome:{field}"
        if key in alias_to_id:
            return alias_to_id[key], f"alias:{field}"
    return None, None


def month_windows(start: date, end: date):
    cur = date(start.year, start.month, 1)
    while cur <= end:
        if cur.month == 12:
            nxt = date(cur.year + 1, 1, 1)
        else:
            nxt = date(cur.year, cur.month + 1, 1)
        last = min(end, nxt - timedelta(days=1))
        yield max(start, cur), last
        cur = nxt


def fetch_events(league_slug: str, start: date, end: date):
    events = {}
    headers = {"User-Agent": "cartola-estatistico-scouts-v3/1.0"}
    for ini, fim in month_windows(start, end):
        params = {"dates": f"{ini:%Y%m%d}-{fim:%Y%m%d}", "limit": 1000}
        response = requests.get(BASE_URL.format(league=league_slug), params=params, headers=headers, timeout=30)
        response.raise_for_status()
        for event in response.json().get("events", []):
            if event.get("id"):
                events[str(event["id"])] = event
    return list(events.values())


def main():
    clubs = cartola_clubs()
    by_abbr, by_name, alias_to_id = build_indexes(clubs)
    start = date(YEAR, 1, 1)
    end = min(date.today(), date(YEAR, 12, 31))

    prior = load_json(OUT) if OUT.exists() else {}
    prior_events = {str(e.get("evento_id")): e for e in prior.get("eventos", []) if e.get("evento_id")}
    collected = dict(prior_events)
    sources = {}
    errors = []
    unmatched = []

    for comp, slug in LEAGUES.items():
        try:
            raw_events = fetch_events(slug, start, end)
            sources[comp] = {"slug": slug, "eventos_recebidos": len(raw_events), "status": "ok"}
        except Exception as exc:
            sources[comp] = {"slug": slug, "eventos_recebidos": 0, "status": "erro"}
            errors.append({"competicao": comp, "erro": str(exc)[:400]})
            continue

        for event in raw_events:
            comps = event.get("competitions") or []
            if not comps:
                continue
            contest = comps[0]
            status = (event.get("status") or {}).get("type") or {}
            if not status.get("completed", False):
                continue
            competitors = contest.get("competitors") or []
            mapped = []
            for competitor in competitors:
                team = competitor.get("team") or {}
                cid, method = map_team(team, by_abbr, by_name, alias_to_id)
                mapped.append({
                    "homeAway": competitor.get("homeAway"),
                    "espn_id": team.get("id"),
                    "nome": team.get("displayName") or team.get("shortDisplayName"),
                    "abreviacao": team.get("abbreviation"),
                    "clube_id": cid,
                    "metodo_match": method,
                })
            cartola_ids = sorted({int(t["clube_id"]) for t in mapped if t.get("clube_id") is not None})
            if not cartola_ids:
                continue
            try:
                dt = datetime.fromisoformat(str(event.get("date")).replace("Z", "+00:00"))
            except Exception:
                continue
            if dt.year != YEAR or dt.date() > end:
                continue
            eid = str(event.get("id"))
            collected[eid] = {
                "evento_id": eid,
                "competicao": comp,
                "league_slug": slug,
                "data": dt.astimezone(timezone.utc).isoformat(),
                "nome_evento": event.get("name") or event.get("shortName"),
                "clubes_cartola_ids": cartola_ids,
                "times": mapped,
                "status": status.get("name") or status.get("state") or "completed",
            }
            for t in mapped:
                if t.get("clube_id") is None:
                    unmatched.append({"competicao": comp, "nome": t.get("nome"), "abreviacao": t.get("abreviacao")})

    relevant = sorted(collected.values(), key=lambda e: (e.get("data", ""), e.get("evento_id", "")))
    if not relevant and errors:
        raise RuntimeError(f"Falha na coleta ESPN e nenhum snapshot anterior disponível: {errors}")

    counts = {}
    for comp in LEAGUES:
        comp_events = [e for e in relevant if e.get("competicao") == comp]
        counts[comp] = {
            "eventos_com_clube_cartola": len(comp_events),
            "clubes_cartola_distintos": len({cid for e in comp_events for cid in e.get("clubes_cartola_ids", [])}),
        }

    dedup_unmatched = sorted({(x["competicao"], str(x.get("nome")), str(x.get("abreviacao"))) for x in unmatched})
    payload = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "temporada": YEAR,
        "fonte": "ESPN scoreboard JSON público (endpoint não oficial, sem chave); snapshot versionado no laboratório.",
        "regra_anti_leakage": "Somente partidas marcadas como concluídas são armazenadas. Features históricas filtram data_externa < data_da_partida_alvo; placares e resultados não são usados.",
        "janela_coletada": {"inicio": start.isoformat(), "fim": end.isoformat()},
        "fontes": sources,
        "erros_coleta": errors,
        "resumo": counts,
        "clubes_cartola": clubs,
        "nao_mapeados_em_eventos_relevantes": [
            {"competicao": a, "nome": b, "abreviacao": c} for a, b, c in dedup_unmatched
        ],
        "eventos": relevant,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Calendário externo 2026:", counts, "| erros:", len(errors), "| eventos:", len(relevant))


if __name__ == "__main__":
    main()
