#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import requests

V2_BASE = "https://raw.githubusercontent.com/renatovalerio88/cartola-estatistico/main/data/api"
API_BASE = "https://api.cartolafc.globo.com"
ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
FILES = ("jogadores.json", "pontuados.json", "partidas.json", "resumo.json")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/150 Safari/537.36",
    "Accept": "application/json",
}
POSICOES = {1: "GOL", 2: "LAT", 3: "ZAG", 4: "MEI", 5: "ATA", 6: "TEC"}


def download(url: str):
    r = requests.get(url, timeout=30, headers=HEADERS)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.content


def buscar_json(endpoint: str):
    r = requests.get(f"{API_BASE}{endpoint}", timeout=30, headers=HEADERS)
    r.raise_for_status()
    return r.json()


def save_with_meta(url: str, target: Path):
    content = download(url)
    if content is None:
        return None
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return {
        "bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
        "url": url,
    }


def salvar_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    path.write_bytes(data)
    return {
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def inteiro(valor):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def indexar_contexto_partidas(partidas, clubes):
    lista = partidas.get("partidas", []) if isinstance(partidas, dict) else []
    contexto = {}
    for p in lista:
        if not isinstance(p, dict):
            continue
        casa = inteiro(p.get("clube_casa_id"))
        fora = inteiro(p.get("clube_visitante_id"))
        if casa is None or fora is None:
            continue
        data = p.get("partida_data") or p.get("data") or p.get("data_hora")
        casa_info = clubes.get(str(casa), clubes.get(casa, {})) or {}
        fora_info = clubes.get(str(fora), clubes.get(fora, {})) or {}
        contexto[casa] = {
            "mando": "casa",
            "adversarioId": fora,
            "siglaAdversario": fora_info.get("abreviacao") or fora_info.get("nome") or "",
            "dataPartida": data,
        }
        contexto[fora] = {
            "mando": "fora",
            "adversarioId": casa,
            "siglaAdversario": casa_info.get("abreviacao") or casa_info.get("nome") or "",
            "dataPartida": data,
        }
    return contexto


def normalizar_mercado(mercado, partidas):
    atletas = mercado.get("atletas", []) if isinstance(mercado, dict) else []
    clubes = mercado.get("clubes", {}) if isinstance(mercado, dict) else {}
    contexto = indexar_contexto_partidas(partidas, clubes)
    saida = []
    for a in atletas:
        if not isinstance(a, dict):
            continue
        aid = inteiro(a.get("atleta_id") or a.get("id"))
        pos_id = inteiro(a.get("posicao_id") or a.get("posicaoId"))
        clube_id = inteiro(a.get("clube_id") or a.get("clubeId"))
        if aid is None or pos_id not in POSICOES or clube_id is None:
            continue
        clube = clubes.get(str(clube_id), clubes.get(clube_id, {})) or {}
        ctx = contexto.get(clube_id, {})
        status_id = inteiro(a.get("status_id") or a.get("statusId"))
        titularidade = 95 if status_id == 7 else 45
        minutos = 85 if status_id == 7 else 45
        saida.append(
            {
                "id": aid,
                "rodada": None,
                "apelido": a.get("apelido") or a.get("nome") or str(aid),
                "nome": a.get("nome") or a.get("apelido") or str(aid),
                "posicao": POSICOES[pos_id],
                "posicaoId": pos_id,
                "clubeId": clube_id,
                "siglaClube": clube.get("abreviacao") or clube.get("nome") or "",
                "statusId": status_id,
                "preco": a.get("preco_num") if a.get("preco_num") is not None else a.get("preco"),
                "variacao": a.get("variacao_num") if a.get("variacao_num") is not None else a.get("variacao"),
                "media": a.get("media_num") if a.get("media_num") is not None else a.get("media"),
                "jogos": a.get("jogos_num") if a.get("jogos_num") is not None else a.get("jogos"),
                "mando": ctx.get("mando"),
                "adversarioId": ctx.get("adversarioId"),
                "siglaAdversario": ctx.get("siglaAdversario"),
                "dataPartida": ctx.get("dataPartida"),
                "titularidade": titularidade,
                "minutosEsperados": minutos,
            }
        )
    return saida


def sincronizar_rodada_vigente(manifest):
    status = buscar_json("/mercado/status")
    rodada = inteiro(status.get("rodada_atual") or status.get("rodada"))
    if rodada is None:
        raise RuntimeError("API oficial não informou rodada atual")

    status_meta = salvar_json(RAW / "status.json", status)
    manifest["status_oficial"] = {
        **status_meta,
        "url": f"{API_BASE}/mercado/status",
        "rodada": rodada,
    }

    status_mercado = inteiro(status.get("status_mercado"))
    if status_mercado != 1:
        print(f"API oficial: R{rodada:02d} com mercado status={status_mercado}; nenhum lock novo pré-rodada será criado.")
        return

    mercado = buscar_json("/atletas/mercado")
    partidas = buscar_json(f"/partidas/{rodada}")
    jogadores = normalizar_mercado(mercado, partidas)
    if not jogadores:
        raise RuntimeError(f"API oficial retornou zero jogadores normalizados para R{rodada:02d}")
    for j in jogadores:
        j["rodada"] = rodada

    pasta = RAW / f"rodada-{rodada:02d}"
    metas = {
        "jogadores.json": salvar_json(pasta / "jogadores.json", jogadores),
        "partidas.json": salvar_json(pasta / "partidas.json", partidas),
        "pontuados.json": salvar_json(pasta / "pontuados.json", {}),
    }
    resumo = {
        "rodada": rodada,
        "statusMercado": status_mercado,
        "fonte": "api_oficial_cartola",
        "capturadoEmUtc": datetime.now(timezone.utc).isoformat(),
        "totalJogadores": len(jogadores),
    }
    metas["resumo.json"] = salvar_json(pasta / "resumo.json", resumo)
    manifest["rodada_vigente_oficial"] = {
        "rodada": rodada,
        "status_mercado": status_mercado,
        "jogadores": len(jogadores),
        "arquivos": metas,
    }
    print(f"API oficial: R{rodada:02d} sincronizada diretamente na V3 com {len(jogadores)} jogadores.")


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    manifest = {
        "fonte_historica": V2_BASE,
        "fonte_rodada_vigente": API_BASE,
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "modo": "historico_v2_somente_leitura_com_rodada_vigente_direta_da_api_oficial",
        "status": None,
        "rodadas": {},
    }

    # A V2 permanece estritamente somente leitura e serve apenas como histórico já consolidado.
    status_url = f"{V2_BASE}/status.json"
    manifest["status"] = save_with_meta(status_url, RAW / "status-v2.json")

    found = files_saved = 0
    for rodada in range(1, 39):
        key = f"rodada-{rodada:02d}"
        meta = {}
        any_file = False
        for name in FILES:
            url = f"{V2_BASE}/{key}/{name}"
            item = save_with_meta(url, RAW / key / name)
            if item is None:
                continue
            any_file = True
            meta[name] = item
            files_saved += 1
        if any_file:
            found += 1
            manifest["rodadas"][str(rodada)] = meta

    # Sobrescreve SOMENTE a cópia local V3 da rodada vigente com dados oficiais atuais.
    # Nenhuma escrita é feita no repositório V2.
    sincronizar_rodada_vigente(manifest)

    (RAW / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Base V3 sincronizada: {found} rodadas históricas da V2 + rodada vigente oficial direta; {files_saved} arquivos históricos.")
    if found < 2:
        raise SystemExit("Histórico insuficiente para laboratório.")


if __name__ == "__main__":
    main()
