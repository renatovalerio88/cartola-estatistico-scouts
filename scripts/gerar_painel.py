#!/usr/bin/env python3
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; REPORTS=ROOT/"data"/"reports"; SITE_DATA=ROOT/"site"/"dados.json"
def load(name):
    p=REPORTS/name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
def main():
    SITE_DATA.parent.mkdir(parents=True,exist_ok=True)
    SITE_DATA.write_text(json.dumps({"auditoria":load("auditoria-scouts.json"),"campeonato":load("campeonato-modelos.json")},ensure_ascii=False,indent=2),encoding="utf-8")
    print("Painel atualizado.")
if __name__=="__main__":main()
