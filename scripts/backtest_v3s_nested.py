#!/usr/bin/env python3
from __future__ import annotations
import json, sys
from datetime import datetime, timezone
from pathlib import Path
import numpy as np, pandas as pd
from sklearn.ensemble import ExtraTreesRegressor, RandomForestRegressor, HistGradientBoostingRegressor, GradientBoostingRegressor
from sklearn.linear_model import PoissonRegressor, Ridge, ElasticNet, BayesianRidge
from sklearn.metrics import mean_absolute_error
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from src.cartola_scoring import SCOUT_WEIGHTS
DATA=ROOT/"data"/"derived"/"dataset-walk-forward.csv"; OUT=ROOT/"data"/"reports"/"backtest-v3s-nested.json"
POSITIONS=["GOL","LAT","ZAG","MEI","ATA"]; MIN_TRAIN=80; START_ROUND=10

def feature_cols(s): return ["historico_jogos","mando","pontos_media3","pontos_media5","pontos_ewma",f"{s}_media3",f"{s}_media5",f"{s}_ewma"]
def factories():
    return {
        "ridge":lambda:make_pipeline(StandardScaler(),Ridge(alpha=2.0)),
        "elastic_net":lambda:make_pipeline(StandardScaler(),ElasticNet(alpha=.02,l1_ratio=.25,max_iter=2000,random_state=42)),
        "bayesian_ridge":lambda:make_pipeline(StandardScaler(),BayesianRidge()),
        "poisson":lambda:make_pipeline(StandardScaler(),PoissonRegressor(alpha=.2,max_iter=300)),
        "random_forest":lambda:RandomForestRegressor(n_estimators=60,min_samples_leaf=5,random_state=42,n_jobs=-1),
        "extra_trees":lambda:ExtraTreesRegressor(n_estimators=60,min_samples_leaf=5,random_state=42,n_jobs=-1),
        "gradient_boosting":lambda:GradientBoostingRegressor(n_estimators=60,max_depth=2,min_samples_leaf=5,learning_rate=.05,loss="huber",random_state=42),
        "hist_gradient_boosting":lambda:HistGradientBoostingRegressor(max_iter=60,max_leaf_nodes=15,l2_regularization=1.0,random_state=42),
    }

def metric(y,p):
    y=np.asarray(y,float); p=np.asarray(p,float); e=p-y
    return {"n":int(len(y)),"mae":round(float(np.mean(np.abs(e))),6),"rmse":round(float(np.sqrt(np.mean(e**2))),6),"bias":round(float(np.mean(e)),6)}

def baseline_predict(frame,s,name):
    col=f"{s}_{'media3' if name=='media3' else 'ewma'}"
    return np.clip(frame[col].fillna(0).to_numpy(float),0,None)

def fit_predict(name,train,test,s):
    if name in ("media3","ewma"): return baseline_predict(test,s,name)
    ycol=f"target_{s}"; feats=feature_cols(s)
    ytr=train[ycol].fillna(0).to_numpy(float)
    if len(ytr)==0 or float(np.sum(ytr))==0:return np.zeros(len(test))
    model=factories()[name](); model.fit(train[feats].fillna(0).to_numpy(float),ytr)
    return np.clip(model.predict(test[feats].fillna(0).to_numpy(float)),0,None)

def choose_model(history,s,current_round):
    # Nested temporal selection: the two most recent prior rounds are validation;
    # training for model selection ends before that validation window.
    prior=history[history.rodada<current_round].copy()
    rounds=sorted(prior.rodada.unique())
    if len(rounds)<5:return "ewma",{}
    val_rounds=rounds[-2:]; inner_train=prior[~prior.rodada.isin(val_rounds)]; val=prior[prior.rodada.isin(val_rounds)]
    if len(inner_train)<MIN_TRAIN or val.empty:return "ewma",{}
    y=val[f"target_{s}"].fillna(0).to_numpy(float); scores={}
    for name in ["media3","ewma",*factories().keys()]:
        try:p=fit_predict(name,inner_train,val,s); scores[name]=float(mean_absolute_error(y,p))
        except Exception:scores[name]=999999.0
    winner=min(scores,key=lambda n:(scores[n],n))
    return winner,{k:round(v,6) for k,v in sorted(scores.items(),key=lambda kv:kv[1])}

def main():
    df=pd.read_csv(DATA); df=df[df.posicao.isin(POSITIONS)].copy(); df=df.sort_values(["rodada","atleta_id"]).reset_index(drop=True)
    scouts=[s for s in SCOUT_WEIGHTS if f"target_{s}" in df.columns]
    predictions=[]; champion_counts={}; selection_log=[]
    for rodada in sorted(int(r) for r in df.rodada.unique() if int(r)>=START_ROUND):
        current=df[df.rodada.eq(rodada)].copy(); previous=df[df.rodada.lt(rodada)].copy()
        if current.empty:continue
        score=np.zeros(len(current),float)
        for pos in POSITIONS:
            mask=current.posicao.eq(pos); test=current[mask]
            hist=previous[previous.posicao.eq(pos)]
            if test.empty:continue
            local_score=np.zeros(len(test),float)
            for s,w in SCOUT_WEIGHTS.items():
                if f"target_{s}" not in df.columns:continue
                winner,inner_scores=choose_model(hist,s,rodada)
                champion_counts[winner]=champion_counts.get(winner,0)+1
                train=hist
                if len(train)<MIN_TRAIN:
                    winner="ewma"
                try:pred=fit_predict(winner,train,test,s)
                except Exception:pred=baseline_predict(test,s,"ewma"); winner="ewma_fallback"
                local_score+=pred*float(w)
                selection_log.append({"rodada":rodada,"posicao":pos,"scout":s,"modelo":winner,"mae_validacao":inner_scores.get(winner)})
            score[np.flatnonzero(mask.to_numpy())]=local_score
        for i,row in current.iterrows():
            local_index=current.index.get_loc(i)
            predictions.append({"rodada":rodada,"atleta_id":int(row.atleta_id),"posicao":row.posicao,"real":float(row.target_pontos),"v3s_nested":float(score[local_index]),"direta_ewma":float(row.pontos_ewma)})
        print(f"R{rodada}: {len(current)} jogadores previstos")
    pred=pd.DataFrame(predictions)
    if pred.empty:raise SystemExit("Sem previsões nested suficientes")
    geral={"v3s_nested":metric(pred.real,pred.v3s_nested),"direta_ewma":metric(pred.real,pred.direta_ewma)}
    por_pos={p:{"v3s_nested":metric(g.real,g.v3s_nested),"direta_ewma":metric(g.real,g.direta_ewma)} for p,g in pred.groupby("posicao")}
    por_rodada={str(int(r)):{"n":int(len(g)),"v3s_mae":metric(g.real,g.v3s_nested)["mae"],"direta_ewma_mae":metric(g.real,g.direta_ewma)["mae"]} for r,g in pred.groupby("rodada")}
    wins=sum(1 for v in por_rodada.values() if v["v3s_mae"]<v["direta_ewma_mae"]); ties=sum(1 for v in por_rodada.values() if v["v3s_mae"]==v["direta_ewma_mae"])
    payload={"gerado_em":datetime.now(timezone.utc).isoformat(),"protocolo":"nested walk-forward: para cada rodada R, escolha de modelo usa apenas validação em rodadas < R; vencedor é retreinado apenas com histórico < R e então prevê R","inicio_rodada":START_ROUND,"linhas":int(len(pred)),"rodadas":sorted(pred.rodada.astype(int).unique().tolist()),"scouts":scouts,"modelos_selecao":["media3","ewma",*factories().keys()],"geral":geral,"por_posicao":por_pos,"por_rodada":por_rodada,"vitorias_rodada_v3s":wins,"empates_rodada":ties,"vitorias_rodada_direta":len(por_rodada)-wins-ties,"selecoes_modelos":dict(sorted(champion_counts.items(),key=lambda kv:(-kv[1],kv[0]))),"log_selecao":selection_log}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    print("Nested V3-S:",geral,"vitórias rodada",wins,"de",len(por_rodada))
if __name__=="__main__":main()
