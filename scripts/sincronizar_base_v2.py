#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE = "https://raw.githubusercontent.com/renatovalerio88/cartola-estatistico/main/data/api"
ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
FILES = ("jogadores.json", "pontuados.json", "partidas.json", "resumo.json")


def download(url):
    r = requests.get(url, timeout=30)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.content


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


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    manifest = {
        "fonte": BASE,
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "modo": "somente_leitura_da_v2",
        "status": None,
        "rodadas": {},
    }

    status_url = f"{BASE}/status.json"
    manifest["status"] = save_with_meta(status_url, RAW / "status.json")

    found = files_saved = 0
    for rodada in range(1, 39):
        key = f"rodada-{rodada:02d}"
        meta = {}
        any_file = False
        for name in FILES:
            url = f"{BASE}/{key}/{name}"
            item = save_with_meta(url, RAW / key / name)
            if item is None:
                continue
            any_file = True
            meta[name] = item
            files_saved += 1
        if any_file:
            found += 1
            manifest["rodadas"][str(rodada)] = meta

    (RAW / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    status_txt = "com status oficial" if manifest["status"] else "sem status oficial"
    print(f"Base V3 sincronizada: {found} rodadas, {files_saved} arquivos, {status_txt}.")
    if found < 2:
        raise SystemExit("Histórico insuficiente para laboratório.")


if __name__ == "__main__":
    main()
