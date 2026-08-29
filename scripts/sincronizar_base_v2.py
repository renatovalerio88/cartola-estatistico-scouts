#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json
from datetime import datetime, timezone
from pathlib import Path
import requests
BASE="https://raw.githubusercontent.com/renatovalerio88/cartola-estatistico/main/data/api"
ROOT=Path(__file__).resolve().parents[1]; RAW=ROOT/"data"/"raw"; FILES=("jogadores.json","pontuados.json","partidas.json","resumo.json")

def download(url):
    r=requests.get(url,timeout=30)
    if r.status_code==404:return None
    r.raise_for_status(); return r.content

def main():
    RAW.mkdir(parents=True,exist_ok=True)
    manifest={"fonte":BASE,"gerado_em":datetime.now(timezone.utc).isoformat(),"rodadas":{}}
    found=files_saved=0
    for rodada in range(1,39):
        key=f"rodada-{rodada:02d}"; meta={}; any_file=False
        for name in FILES:
            content=download(f"{BASE}/{key}/{name}")
            if content is None: continue
            any_file=True; target=RAW/key/name; target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(content)
            meta[name]={"bytes":len(content),"sha256":hashlib.sha256(content).hexdigest(),"url":f"{BASE}/{key}/{name}"}; files_saved+=1
        if any_file: found+=1; manifest["rodadas"][str(rodada)]=meta
    (RAW/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"Base V3 sincronizada: {found} rodadas, {files_saved} arquivos.")
    if found<2: raise SystemExit("Histórico insuficiente para laboratório.")
if __name__=="__main__": main()
