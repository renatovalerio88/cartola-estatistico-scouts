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
def main():
    scout_counts=Counter(); by_pos=defaultdict(Counter); unknown=Counter(); discrepancies=[]; n_players=n_on_field=0; abs_errors=[]; rounds=[]
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
            for code in unknown_codes: unknown[code]+=1
            official=atleta.get("pontuacao")
            if official is None: continue
            err=round(float(official)-reconstructed,4); abs_errors.append(abs(err))
            if abs(err)>0.051:
                discrepancies.append({"rodada":rodada,"atleta_id":str(aid),"apelido":atleta.get("apelido"),"posicao":pos,"oficial":official,"reconstruida":reconstructed,"erro":err,"scouts":scouts})
        rounds.append({"rodada":rodada,"atletas_em_campo":used})
    mae=sum(abs_errors)/len(abs_errors) if abs_errors else None; exact=sum(e<=0.051 for e in abs_errors)
    report={"gerado_em":datetime.now(timezone.utc).isoformat(),"rodadas_auditadas":len(rounds),"atletas_registrados":n_players,"atletas_em_campo":n_on_field,"regras":SCOUT_WEIGHTS,"scouts_observados":dict(sorted(scout_counts.items())),"scouts_por_posicao":{p:dict(sorted(c.items())) for p,c in sorted(by_pos.items())},"codigos_desconhecidos":dict(unknown),"reconstrucao":{"n":len(abs_errors),"mae":round(mae,6) if mae is not None else None,"taxa_ate_0_05":round(exact/len(abs_errors),6) if abs_errors else None,"divergencias_maiores_0_05":len(discrepancies),"amostra_divergencias":discrepancies[:50]},"rodadas":rounds}
    REPORT.parent.mkdir(parents=True,exist_ok=True); REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"Auditoria: {len(rounds)} rodadas; {n_on_field} atuações; {len(scout_counts)} scouts observados.")
    print(f"Reconstrução: MAE={mae:.4f}; divergências >0,05={len(discrepancies)}; desconhecidos={dict(unknown)}")
if __name__=="__main__": main()
