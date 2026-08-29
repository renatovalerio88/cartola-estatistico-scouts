#!/usr/bin/env python3
from __future__ import annotations
import json, sys
from datetime import datetime, timezone
from pathlib import Path
import numpy as np, pandas as pd
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from src.cartola_scoring import SCOUT_WEIGHTS
DATA=ROOT/"data"/"derived"/"dataset-walk-forward.csv"; OUT=ROOT/"data"/"reports"/"backtest-pontos-scouts.json"

def metrics(y,p):
    y=np.asarray(y,float); p=np.asarray(p,float); e=p-y
    return {"n":int(len(y)),"mae":round(float(np.mean(np.abs(e))),6),"rmse":round(float(np.sqrt(np.mean(e**2))),6),"bias":round(float(np.mean(e)),6)}

def scout_projection(df,suffix):
    total=np.zeros(len(df),dtype=float)
    usados=[]
    for scout,w in SCOUT_WEIGHTS.items():
        col=f"{scout}_{suffix}"
        if col in df.columns:
            total+=df[col].fillna(0).to_numpy(float)*float(w); usados.append(scout)
    return total,usados

def main():
    df=pd.read_csv(DATA); df=df[df.posicao.isin(["GOL","LAT","ZAG","MEI","ATA"])].copy()
    # Avaliação começa na R7 para dar histórico mínimo razoável e espelhar o campeonato inicial.
    df=df[df.rodada>=7].copy(); y=df.target_pontos.to_numpy(float)
    v3_ewma,scouts= scout_projection(df,"ewma"); v3_m3,_=scout_projection(df,"media3")
    models={"direta_media3":df.pontos_media3.to_numpy(float),"direta_ewma":df.pontos_ewma.to_numpy(float),"scouts_media3":v3_m3,"scouts_ewma":v3_ewma}
    geral={name:metrics(y,p) for name,p in models.items()}
    ranking=sorted(geral,key=lambda n:(geral[n]["mae"],geral[n]["rmse"]))
    por_pos={}
    for pos,g in df.groupby("posicao"):
        idx=g.index.to_numpy(); local_y=g.target_pontos.to_numpy(float); por_pos[pos]={}
        for name in models:
            if name=="direta_media3": pred=g.pontos_media3.to_numpy(float)
            elif name=="direta_ewma": pred=g.pontos_ewma.to_numpy(float)
            else: pred=scout_projection(g,"media3" if name.endswith("media3") else "ewma")[0]
            por_pos[pos][name]=metrics(local_y,pred)
    por_rodada={}
    for rodada,g in df.groupby("rodada"):
        por_rodada[str(int(rodada))]={"n":int(len(g)),"direta_ewma_mae":metrics(g.target_pontos,g.pontos_ewma)["mae"],"scouts_ewma_mae":metrics(g.target_pontos,scout_projection(g,"ewma")[0])["mae"]}
    payload={"gerado_em":datetime.now(timezone.utc).isoformat(),"protocolo":"baseline arquitetural sem seleção otimista: features de cada R usam apenas rodadas < R; comparação inicia R7","scouts_usados":scouts,"rodadas":[int(df.rodada.min()),int(df.rodada.max())] if len(df) else [],"linhas":int(len(df)),"ranking":ranking,"geral":geral,"por_posicao":por_pos,"por_rodada":por_rodada,"nota":"Este estágio usa apenas médias/EWMA de scouts. V3 com campeões ML por scout será avaliada depois em nested walk-forward para evitar escolher e testar o vencedor no mesmo período."}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    print("Backtest pontos:",ranking,{k:geral[k]["mae"] for k in ranking})
if __name__=="__main__":main()
