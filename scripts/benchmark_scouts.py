#!/usr/bin/env python3
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
import numpy as np, pandas as pd
from sklearn.ensemble import ExtraTreesRegressor, RandomForestRegressor, HistGradientBoostingRegressor
from sklearn.linear_model import PoissonRegressor, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/"data"/"derived"/"dataset-walk-forward.csv"; OUT=ROOT/"data"/"reports"/"campeonato-modelos.json"
SCOUTS=["G","A","FT","FD","FF","FS","I","DS","SG","DP","DE","GC","CV","CA","GS","FC","PC"]; POSITIONS=["GOL","LAT","ZAG","MEI","ATA"]; MIN_TRAIN_ROUND=5; MIN_ROWS=80
def feature_cols(s): return ["historico_jogos","mando","pontos_media3","pontos_media5","pontos_ewma",f"{s}_media3",f"{s}_media5",f"{s}_ewma"]
def models():
    return {"ridge":lambda:make_pipeline(StandardScaler(),Ridge(alpha=2.0)),"poisson":lambda:make_pipeline(StandardScaler(),PoissonRegressor(alpha=.2,max_iter=500)),"random_forest":lambda:RandomForestRegressor(n_estimators=160,min_samples_leaf=5,random_state=42,n_jobs=-1),"extra_trees":lambda:ExtraTreesRegressor(n_estimators=160,min_samples_leaf=5,random_state=42,n_jobs=-1),"hist_gradient_boosting":lambda:HistGradientBoostingRegressor(max_iter=120,max_leaf_nodes=15,l2_regularization=1.0,random_state=42)}
def evaluate(df,s,pos):
    sub=df[df.posicao.eq(pos)].copy(); ycol=f"target_{s}"; feats=feature_cols(s)
    if len(sub)<MIN_ROWS or sub[ycol].sum()==0:return None
    preds={"media3":[],"ewma":[]}; fitted={n:[] for n in models()}; actuals=[]; rounds=[]
    for rodada in sorted(sub.rodada.unique()):
        train=sub[sub.rodada<rodada]; test=sub[sub.rodada==rodada]
        if rodada<=MIN_TRAIN_ROUND or len(train)<MIN_ROWS or test.empty:continue
        Xtr=train[feats].fillna(0).to_numpy(float); ytr=train[ycol].fillna(0).to_numpy(float); Xte=test[feats].fillna(0).to_numpy(float); yte=test[ycol].fillna(0).to_numpy(float)
        preds["media3"].extend(np.clip(test[f"{s}_media3"].to_numpy(float),0,None)); preds["ewma"].extend(np.clip(test[f"{s}_ewma"].to_numpy(float),0,None)); actuals.extend(yte); rounds.extend([int(rodada)]*len(test))
        for name,factory in models().items():
            try: model=factory(); model.fit(Xtr,ytr); pred=np.clip(model.predict(Xte),0,None)
            except Exception: pred=np.repeat(float(np.mean(ytr)),len(yte))
            fitted[name].extend(pred)
    if not actuals:return None
    actual=np.asarray(actuals,float); metrics={}
    for name,p in {**preds,**fitted}.items():
        p=np.asarray(p,float); metrics[name]={"mae":round(float(mean_absolute_error(actual,p)),6),"rmse":round(float(mean_squared_error(actual,p)**.5),6),"bias":round(float(np.mean(p-actual)),6),"n":int(len(actual))}
    ranking=sorted(metrics,key=lambda n:(metrics[n]["mae"],metrics[n]["rmse"])); return {"scout":s,"posicao":pos,"ranking":ranking,"metricas":metrics,"rodadas_teste":sorted(set(rounds))}
def main():
    df=pd.read_csv(DATA); results=[]
    for s in SCOUTS:
        for pos in POSITIONS:
            r=evaluate(df,s,pos)
            if r: results.append(r); print(f"{s}/{pos}: {r['ranking'][0]} MAE={r['metricas'][r['ranking'][0]]['mae']}")
    wins={}
    for r in results:wins[r["ranking"][0]]=wins.get(r["ranking"][0],0)+1
    payload={"gerado_em":datetime.now(timezone.utc).isoformat(),"protocolo":"walk-forward estrito por rodada; treino usa somente rodada < teste","min_linhas_treino":MIN_ROWS,"modelos":["media3","ewma",*models().keys()],"competicoes_validas":len(results),"vitorias_modelos":dict(sorted(wins.items(),key=lambda x:(-x[1],x[0]))),"resultados":results}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8"); print(f"Campeonato inicial concluído: {len(results)} scout×posição válidos.")
if __name__=="__main__":main()
