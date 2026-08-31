#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUTDIR = ROOT / "predictions" / "clima"
REPORT = ROOT / "data" / "reports" / "clima-pre-rodada.json"
MIN_COVERAGE_TO_FREEZE = 0.80

CITY = {
    "america-mg": (-19.9167, -43.9345), "athletico-pr": (-25.4284, -49.2733),
    "atletico-mg": (-19.9167, -43.9345), "bahia": (-12.9714, -38.5014),
    "botafogo": (-22.9068, -43.1729), "bragantino": (-22.9527, -46.5442),
    "chapecoense": (-27.1004, -52.6152), "corinthians": (-23.5505, -46.6333),
    "coritiba": (-25.4284, -49.2733), "cruzeiro": (-19.9167, -43.9345),
    "flamengo": (-22.9068, -43.1729), "fluminense": (-22.9068, -43.1729),
    "fortaleza": (-3.7319, -38.5267), "gremio": (-30.0346, -51.2177),
    "internacional": (-30.0346, -51.2177), "mirassol": (-20.8169, -49.5206),
    "palmeiras": (-23.5505, -46.6333), "remo": (-1.4558, -48.4902),
    "santos": (-23.9608, -46.3336), "sao-paulo": (-23.5505, -46.6333),
    "sport": (-8.0476, -34.8770), "vasco": (-22.9068, -43.1729),
    "vitoria": (-12.9714, -38.5014),
}


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def parse_dt(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def status_deadline(status):
    fechamento = status.get("fechamento") or {}
    ts = fechamento.get("timestamp")
    if ts:
        try:
            return datetime.fromtimestamp(int(ts), tz=timezone.utc)
        except Exception:
            pass
    try:
        return datetime(
            int(fechamento["ano"]), int(fechamento["mes"]), int(fechamento["dia"]),
            int(fechamento["hora"]), int(fechamento.get("minuto", 0)),
            tzinfo=__import__("zoneinfo").ZoneInfo("America/Sao_Paulo"),
        ).astimezone(timezone.utc)
    except Exception:
        return None


def future_matches(raw, now):
    matches = raw.get("partidas", []) if isinstance(raw, dict) else []
    return [p for p in matches if parse_dt(p.get("partida_data")) and parse_dt(p.get("partida_data")) > now]


def select_current_round(now):
    status_path = RAW / "status.json"
    if not status_path.exists():
        return None, "STATUS_OFICIAL_AUSENTE"
    try:
        status = load(status_path)
        rodada = int(status.get("rodada_atual"))
    except Exception:
        return None, "STATUS_OFICIAL_INVALIDO"

    deadline = status_deadline(status)
    if deadline is None:
        return None, "FECHAMENTO_OFICIAL_AUSENTE"
    if now >= deadline:
        return None, "MERCADO_JA_FECHADO_AGUARDAR_PROXIMA_RODADA"

    path = RAW / f"rodada-{rodada:02d}" / "partidas.json"
    if not path.exists():
        return None, "FIXTURE_RODADA_ATUAL_AUSENTE"
    raw = load(path)
    future = future_matches(raw, now)
    if not future:
        return None, "SEM_PARTIDAS_FUTURAS_NA_RODADA_ATUAL"
    return (rodada, raw, future, deadline), None


def nearest_hour(hourly, target_local):
    times = hourly.get("time", [])
    if not times:
        return None
    target = target_local.strftime("%Y-%m-%dT%H:00")
    try:
        idx = times.index(target)
    except ValueError:
        same_day = [(i, t) for i, t in enumerate(times) if t.startswith(target_local.strftime("%Y-%m-%d"))]
        if not same_day:
            return None
        idx = min(same_day, key=lambda it: abs(int(it[1][11:13]) - target_local.hour))[0]
    fields = ["temperature_2m", "apparent_temperature", "precipitation_probability", "relative_humidity_2m", "wind_speed_10m"]
    return {k: hourly.get(k, [None] * len(times))[idx] for k in fields} | {"forecast_time": times[idx]}


def forecast(lat, lon, target_dt):
    params = {
        "latitude": lat, "longitude": lon,
        "hourly": "temperature_2m,apparent_temperature,precipitation_probability,relative_humidity_2m,wind_speed_10m",
        "timezone": "America/Sao_Paulo", "forecast_days": 16,
    }
    r = requests.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=25)
    r.raise_for_status()
    data = r.json()
    local = target_dt.astimezone(__import__("zoneinfo").ZoneInfo("America/Sao_Paulo"))
    return nearest_hour(data.get("hourly", {}), local), r.url


def write_report(payload):
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    now = datetime.now(timezone.utc)
    selected, block_reason = select_current_round(now)
    if not selected:
        write_report({
            "gerado_em": now.isoformat(), "status": "NAO_CAPTURADO",
            "decisao": "AGUARDAR_CONDICAO_PRE_RODADA_VALIDA", "motivo": block_reason,
            "protocolo": "Clima só é elegível se congelado antes do fechamento oficial do mercado da rodada.",
        })
        print(f"Clima: não capturado ({block_reason}).")
        return

    rodada, raw, future, deadline = selected
    outfile = OUTDIR / f"2026-r{rodada:02d}.json"
    if outfile.exists():
        existing = load(outfile)
        write_report({
            "gerado_em": now.isoformat(), "status": "SNAPSHOT_JA_EXISTE_IMUTAVEL",
            "decisao": "NAO_SOBRESCREVER", "rodada": rodada,
            "arquivo": str(outfile.relative_to(ROOT)), "capturado_em": existing.get("capturado_em"),
            "limite_decisao": existing.get("limite_decisao"), "sha256": existing.get("sha256_payload"),
        })
        print(f"Clima R{rodada}: snapshot já existe; preservado.")
        return

    clubs = raw.get("clubes", {})
    rows, errors = [], []
    for p in future:
        home_id = str(p.get("clube_casa_id"))
        slug = str((clubs.get(home_id) or {}).get("slug") or "").strip().lower()
        coords, dt = CITY.get(slug), parse_dt(p.get("partida_data"))
        if not coords or not dt:
            errors.append({"partida_id": p.get("partida_id"), "mandante_slug": slug, "erro": "sem_coordenada_ou_data"})
            continue
        try:
            values, source = forecast(coords[0], coords[1], dt)
        except Exception as exc:
            errors.append({"partida_id": p.get("partida_id"), "mandante_slug": slug, "erro": str(exc)[:180]})
            continue
        if not values:
            errors.append({"partida_id": p.get("partida_id"), "mandante_slug": slug, "erro": "fora_horizonte_forecast"})
            continue
        rows.append({
            "partida_id": p.get("partida_id"), "rodada": rodada,
            "clube_casa_id": p.get("clube_casa_id"), "clube_visitante_id": p.get("clube_visitante_id"),
            "mandante_slug": slug, "partida_data": p.get("partida_data"),
            "latitude": coords[0], "longitude": coords[1], **values, "fonte": source,
        })

    coverage = len(rows) / max(1, len(future))
    if coverage < MIN_COVERAGE_TO_FREEZE:
        write_report({
            "gerado_em": now.isoformat(), "status": "COBERTURA_INSUFICIENTE_NAO_CONGELADA",
            "decisao": "REPETIR_CAPTURA_ANTES_DO_FECHAMENTO", "rodada": rodada,
            "limite_decisao": deadline.isoformat(), "partidas_futuras": len(future),
            "partidas_com_forecast": len(rows), "cobertura": round(coverage, 6),
            "cobertura_minima_para_congelar": MIN_COVERAGE_TO_FREEZE, "erros": errors,
        })
        print(f"Clima R{rodada}: cobertura {coverage:.1%}; nada congelado.")
        return

    payload = {
        "temporada": 2026, "rodada": rodada, "capturado_em": now.isoformat(),
        "limite_decisao": deadline.isoformat(), "elegivel_pre_rodada": True,
        "natureza": "PREVISAO_METEOROLOGICA_PRE_RODADA", "fonte": "Open-Meteo Forecast API",
        "criterio_selecao": "rodada_atual_status_oficial",
        "regra_imutabilidade": "Arquivo nunca é sobrescrito após a primeira criação.",
        "regra_cientifica": "Captura obrigatoriamente anterior ao fechamento oficial do mercado; clima observado pós-jogo é proibido.",
        "cobertura": round(coverage, 6), "partidas": rows, "erros": errors,
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    payload["sha256_payload"] = hashlib.sha256(canonical).hexdigest()
    OUTDIR.mkdir(parents=True, exist_ok=True)
    outfile.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report({
        "gerado_em": now.isoformat(), "status": "CAPTURADO", "decisao": "ACUMULAR_AMOSTRA_PROSPECTIVA",
        "rodada": rodada, "arquivo": str(outfile.relative_to(ROOT)), "limite_decisao": deadline.isoformat(),
        "partidas_futuras": len(future), "partidas_com_forecast": len(rows), "cobertura": round(coverage, 6),
        "sha256": payload["sha256_payload"],
    })
    print(f"Clima R{rodada}: {len(rows)}/{len(future)} partidas congeladas antes do fechamento ({coverage:.1%}).")


if __name__ == "__main__":
    main()
