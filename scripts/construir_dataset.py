#!/usr/bin/env python3
from __future__ import annotations
import json
from collections import defaultdict, deque
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]; RAW=ROOT/"data"/"raw"; OUT=ROOT/"data"/"derived"
SCOUTS=["G","A","FT","FD","FF","FS","PS","I","DS","SG","DP","DE","GC","CV","CA","GS","FC","PC","PP"]
POS={1:"GOL",2:"LAT",3:"ZAG",4:"MEI",5:"ATA",6:"TEC"}
def load(path): return json.loads(path.read_text(encoding="utf-8"))
def partida_context(path):
    if not path.exists(): return {}
    raw=load(path); partidas=raw.get("partidas",raw if isinstance(raw,list) else []); ctx={}
    for p in partidas:
        if not isinstance(p,dict): continue
        casa=p.get("clube_casa_id") or p.get("clube_casa"); fora=p.get("clube_visitante_id") or p.get("clube_visitante")
        try: casa,fora=int(casa),int(fora)
        except (TypeError,ValueError): continue
        ctx[casa]={"mando":1,"adversario_id":fora}; ctx[fora]={"mando":0,"adversario_id":casa}
    return ctx
def mean(v): return sum(v)/len(v) if v else 0.0
def ewma(v,alpha=.45):
    if not v:return 0.0
    acc=float(v[0])
    for x in v[1:]: acc=alpha*float(x)+(1-alpha)*acc
    return acc
def main():
    history=defaultdict(lambda:{"points":deque(maxlen=20),"scouts":defaultdict(lambda:deque(maxlen=20))}); rows=[]; round_stats=[]
    for folder in sorted(RAW.glob("rodada-*")):
        p=folder/"pontuados.json"
        if not p.exists(): continue
        rodada=int(folder.name.split("-")[-1]); ctx=partida_context(folder/"partidas.json"); raw=load(p); atletas=raw.get("atletas",raw if isinstance(raw,dict) else {}); created=0
        for aid_raw,a in atletas.items():
            if not isinstance(a,dict) or not a.get("entrou_em_campo",False): continue
            aid=int(aid_raw); h=history[aid]; past_n=len(h["points"])
            if past_n>=1:
                clube_id=int(a.get("clube_id") or 0); row={"rodada":rodada,"atleta_id":aid,"apelido":a.get("apelido") or str(aid),"posicao_id":int(a.get("posicao_id") or 0),"posicao":POS.get(int(a.get("posicao_id") or 0),"?"),"clube_id":clube_id,"mando":ctx.get(clube_id,{}).get("mando",-1),"adversario_id":ctx.get(clube_id,{}).get("adversario_id",0),"historico_jogos":past_n,"pontos_media3":mean(list(h["points"])[-3:]),"pontos_media5":mean(list(h["points"])[-5:]),"pontos_ewma":ewma(list(h["points"])),"target_pontos":float(a.get("pontuacao") or 0)}
                current=a.get("scout") or {}
                for s in SCOUTS:
                    vals=list(h["scouts"][s]); row[f"{s}_media3"]=mean(vals[-3:]); row[f"{s}_media5"]=mean(vals[-5:]); row[f"{s}_ewma"]=ewma(vals); row[f"target_{s}"]=float(current.get(s,0) or 0)
                rows.append(row); created+=1
            h["points"].append(float(a.get("pontuacao") or 0)); scouts=a.get("scout") or {}
            for s in SCOUTS: h["scouts"][s].append(float(scouts.get(s,0) or 0))
        round_stats.append({"rodada":rodada,"linhas":created})
    df=pd.DataFrame(rows); OUT.mkdir(parents=True,exist_ok=True); df.to_csv(OUT/"dataset-walk-forward.csv",index=False)
    meta={"linhas":len(df),"rodada_min":int(df.rodada.min()) if len(df) else None,"rodada_max":int(df.rodada.max()) if len(df) else None,"jogadores":int(df.atleta_id.nunique()) if len(df) else 0,"colunas":list(df.columns),"anti_leakage":"Features da rodada R usam exclusivamente rodadas < R; target é anexado depois.","por_rodada":round_stats}
    (OUT/"dataset-meta.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8"); print(f"Dataset walk-forward: {len(df)} linhas, {len(df.columns) if len(df) else 0} colunas, {meta['jogadores']} jogadores.")
if __name__=="__main__": main()
