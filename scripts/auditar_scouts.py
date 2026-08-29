#!/usr/bin/env python3
from __future__ import annotations
import json, sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from src.cartola_scoring import POSITION_NAMES, SCOUT_WEIGHTS, score_from_scouts
RAW=ROOT/"data"/"raw"; REPORT=ROOT/"data"/"reports"/"auditoria-scouts.json"
def load(path): return json.loads(path.read_text(encoding="utf-8"))
def resumo_erros(values):
    if not values:return {"n":0,"mae":None,"taxa_ate_0_05":None,"divergencias_maiores_0_05":0}
    return {"n":len(values),"mae":round(sum(abs(v) for v in values)/len(values),6),"taxa_ate_0_05":round(sum(abs(v)<=.051 for v in values)/len(values),6),"divergencias_maiores_0_05":sum(abs(v)>.051 for v in values)}
def main():
    scout_counts=Counter(); by_pos=defaultdict(Counter); unknown=Counter(); unknown_field=Counter(); discrepancies=[]; discrepancies_field=[]; n_players=n_on_field=0; errors=[]; errors_field=[]; errors_by_pos=defaultdict(list); rounds=[]
    for folder in sorted(RAW.glob("rodada-*")):
        p=folder/"pontuados.json"
        if not p.exists(): continue
        rodada=int(folder.name.split("-")[-1]); data=load(p); atletas=data.get("atletas",data if isinstance(data,dict) else {}); used=0
        for aid,atleta in atletas.items():
            if not isinstance(atleta,dict): continue
            n_players+=1
            if not atleta.get("entrou_em_campo",False): continue
            n_on_field+=1; used+=1; pos=POSITION_NAMES.get(int(atleta.get("posicao_id") or 0),"?"); scouts=atleta.get("scout") or {}
            for code,value in scouts.items():
                try: count=float(value or 0)
                except (TypeError,ValueError): continue
                scout_counts[code]+=count; by_pos[pos][code]+=count
            reconstructed,unknown_codes=score_from_scouts(scouts)
            for code in unknown_codes:
                unknown[code]+=1
                if pos!="TEC": unknown_field[code]+=1
            official=atleta.get("pontuacao")
            if official is None: continue
            err=round(float(official)-reconstructed,4); errors.append(err); errors_by_pos[pos].append(err)
            if pos!="TEC": errors_field.append(err)
            item={"rodada":rodada,"atleta_id":str(aid),"apelido":atleta.get("apelido"),"posicao":pos,"oficial":official,"reconstruida":reconstructed,"erro":err,"scouts":scouts}
            if abs(err)>.051:
                discrepancies.append(item)
                if pos!="TEC": discrepancies_field.append(item)
        rounds.append({"rodada":rodada,"atletas_em_campo":used})
    report={"gerado_em":datetime.now(timezone.utc).isoformat(),"rodadas_auditadas":len(rounds),"atletas_registrados":n_players,"atletas_em_campo":n_on_field,"regras":SCOUT_WEIGHTS,"scouts_observados":dict(sorted(scout_counts.items())),"scouts_por_posicao":{p:dict(sorted(c.items())) for p,c in sorted(by_pos.items())},"codigos_desconhecidos":dict(unknown),"codigos_desconhecidos_jogadores":dict(unknown_field),"reconstrucao":resumo_erros(errors),"reconstrucao_jogadores_sem_tecnico":resumo_erros(errors_field),"reconstrucao_por_posicao":{p:resumo_erros(v) for p,v in sorted(errors_by_pos.items())},"amostra_divergencias":discrepancies[:30],"amostra_divergencias_jogadores":discrepancies_field[:50],"rodadas":rounds}
    REPORT.parent.mkdir(parents=True,exist_ok=True); REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    f=report["reconstrucao_jogadores_sem_tecnico"]
    print(f"Auditoria: {len(rounds)} rodadas; {n_on_field} atuações; {len(scout_counts)} scouts observados.")
    print(f"Jogadores (sem TEC): MAE={f['mae']}; divergências >0,05={f['divergencias_maiores_0_05']}; desconhecidos={dict(unknown_field)}")
if __name__=="__main__": main()
