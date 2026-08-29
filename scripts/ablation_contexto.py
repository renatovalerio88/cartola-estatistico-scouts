#!/usr/bin/env python3
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"data"/"derived"/"dataset-walk-forward.csv"
OUT=ROOT/"data"/"reports"/"ablation-contexto.json"
POSITIONS=["GOL","LAT","ZAG","MEI","ATA"]
MIN_TRAIN=80

BASE=["historico_jogos","pontos_media3","pontos_media5","pontos_ewma"]
MANDO=["mando"]
FORCA=[
    "time_jogos","time_gf_media5","time_ga_media5","time_gf_ewma","time_ga_ewma",
    "adversario_jogos","adversario_gf_media5","adversario_ga_media5","adversario_gf_ewma","adversario_ga_ewma",
]
FEATURE_SETS={
    "base":BASE,
    "base_mando":BASE+MANDO,
    "base_forca":BASE+FORCA,
    "base_mando_forca":BASE+MANDO+FORCA,
}

def models():
    return {
        "ridge":lambda:make_pipeline(StandardScaler(),Ridge(alpha=2.0)),
        "extra_trees":lambda:ExtraTreesRegressor(n_estimators=100,min_samples_leaf=5,random_state=42,n_jobs=-1),
        "hist_gradient_boosting":lambda:HistGradientBoostingRegressor(max_iter=100,max_leaf_nodes=15,l2_regularization=1.0,random_state=42),
    }

def folds(rounds):
    rounds=sorted(int(r) for r in set(rounds)); tests=[r for r in rounds if r>=7]
    if len(tests)<=4:return [(r,[r]) for r in tests]
    starts=sorted(set(tests[i] for i in np.linspace(0,len(tests)-1,4,dtype=int)))
    out=[]
    for i,start in enumerate(starts):
        end=starts[i+1] if i+1<len(starts) else max(tests)+1
        out.append((start,[r for r in tests if start<=r<end]))
    return out

def metric(y,p):
    y=np.asarray(y,float); p=np.asarray(p,float); e=p-y
    return {"n":int(len(y)),"mae":round(float(np.mean(np.abs(e))),6),"rmse":round(float(np.sqrt(np.mean(e**2))),6),"bias":round(float(np.mean(e)),6)}

def evaluate_position(df,pos,model_name,features):
    sub=df[df.posicao.eq(pos)].copy(); ys=[]; ps=[]; used=[]
    for start,test_rounds in folds(sub.rodada.unique()):
        train=sub[sub.rodada<start]; test=sub[sub.rodada.isin(test_rounds)]
        if len(train)<MIN_TRAIN or test.empty:continue
        model=models()[model_name](); model.fit(train[features].fillna(0).to_numpy(float),train.target_pontos.to_numpy(float))
        pred=model.predict(test[features].fillna(0).to_numpy(float))
        ys.extend(test.target_pontos.to_numpy(float)); ps.extend(pred); used.extend(test.rodada.astype(int).tolist())
    return (metric(ys,ps),sorted(set(used))) if ys else (None,[])

def main():
    df=pd.read_csv(DATA); df=df[df.posicao.isin(POSITIONS)].copy()
    missing=[c for c in set(sum(FEATURE_SETS.values(),[])) if c not in df.columns]
    if missing:raise SystemExit(f"Features ausentes para ablation: {missing}")
    detailed={}; aggregated={}
    for model_name in models():
        detailed[model_name]={}; aggregated[model_name]={}
        for variant,features in FEATURE_SETS.items():
            all_y=[]; all_p=[]; by_pos={}; rounds=set()
            for pos in POSITIONS:
                sub=df[df.posicao.eq(pos)].copy(); ys=[]; ps=[]; used=[]
                for start,test_rounds in folds(sub.rodada.unique()):
                    train=sub[sub.rodada<start]; test=sub[sub.rodada.isin(test_rounds)]
                    if len(train)<MIN_TRAIN or test.empty:continue
                    model=models()[model_name](); model.fit(train[features].fillna(0).to_numpy(float),train.target_pontos.to_numpy(float))
                    pred=model.predict(test[features].fillna(0).to_numpy(float))
                    ys.extend(test.target_pontos.to_numpy(float)); ps.extend(pred); used.extend(test.rodada.astype(int).tolist())
                if ys:
                    by_pos[pos]=metric(ys,ps); all_y.extend(ys); all_p.extend(ps); rounds.update(used)
            m=metric(all_y,all_p) if all_y else None
            detailed[model_name][variant]={"geral":m,"por_posicao":by_pos,"rodadas":sorted(rounds),"features":features}
            aggregated[model_name][variant]=m
            if m:print(f"{model_name}/{variant}: MAE={m['mae']} N={m['n']}")
    factors={}
    for variant,label in [("base_mando","mando"),("base_forca","forca_time_adversario"),("base_mando_forca","mando_mais_forca")]:
        deltas={}; wins=0; valid=0
        for model_name in models():
            base=aggregated[model_name].get("base"); cur=aggregated[model_name].get(variant)
            if not base or not cur:continue
            delta=round(cur["mae"]-base["mae"],6); deltas[model_name]=delta; valid+=1; wins+=int(delta<0)
        mean_delta=round(float(np.mean(list(deltas.values()))),6) if deltas else None
        factors[label]={"delta_mae_vs_base_por_modelo":deltas,"delta_mae_medio":mean_delta,"modelos_com_melhora":wins,"modelos_validos":valid,"sinal":"PROMISSORIO" if valid and wins>=2 and mean_delta is not None and mean_delta<0 else "NAO_COMPROVADO"}
    payload={
        "gerado_em":datetime.now(timezone.utc).isoformat(),
        "protocolo":"Ablation walk-forward: mesmo alvo, mesmas janelas e mesmos modelos; muda apenas o bloco de features de contexto. Placar da rodada R só atualiza força dos times depois de congelar features de R.",
        "modelos_fixos":list(models()),"feature_sets":FEATURE_SETS,"agregado":aggregated,"fatores":factors,"detalhado":detailed,
        "regra_exploratoria":"Contexto só recebe sinal PROMISSORIO se reduzir MAE em pelo menos 2 de 3 famílias fixas e também no delta médio. Isso ainda não promove feature ao modelo oficial."
    }
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    print("Ablation concluída:",factors)
if __name__=="__main__":main()
