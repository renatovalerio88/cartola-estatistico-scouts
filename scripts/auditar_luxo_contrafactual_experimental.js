#!/usr/bin/env node
"use strict";
// Auditoria EXPLORATÓRIA de snapshots: NÃO modifica a V2, o otimizador ou o site.
const fs=require("fs"),path=require("path");
const FORM={"3-4-3":[1,0,3,4,3],"3-5-2":[1,0,3,5,2],"4-3-3":[1,2,2,3,3],"4-4-2":[1,2,2,4,2],"5-3-2":[1,2,3,3,2]};
const POS=["GOL","LAT","ZAG","MEI","ATA"];
const rnd=x=>Math.round((x+Number.EPSILON)*100)/100;
const actual=(p,pts)=>{const a=pts[String(p.atleta_id)];return {id:p.atleta_id,name:p.apelido,pos:p.posicao,score:a?Number(a.pontuacao):0,played:!!a?.entrou_em_campo,found:!!a};};
function validate(s) {
 const errs=[],ids=[...s.titulares,...s.banco].map(x=>x.atleta_id);
 if(s.titulares.length!==11)errs.push("11 titulares");
 if(new Set(ids).size!==ids.length)errs.push("IDs repetidos");
 if(!s.titulares.some(x=>x.atleta_id===s.capitao_atleta_id))errs.push("capitão ausente");
 if(!FORM[s.formacao])errs.push("formação desconhecida");
 else POS.forEach((pos,i)=>{if(s.titulares.filter(x=>x.posicao===pos).length!==FORM[s.formacao][i])errs.push("cota "+pos);});
 const clubs={};s.titulares.forEach(x=>{if(x.sigla_clube)clubs[x.sigla_clube]=(clubs[x.sigla_clube]||0)+1;});
 if(Object.values(clubs).some(x=>x>(s.max_por_clube||3)))errs.push("limite clube");
 if(s.custo>s.orcamento+0.001)errs.push("orçamento");
 if(Math.abs(s.titulares.reduce((a,x)=>a+Number(x.preco),0)-s.custo)>0.06)errs.push("soma preço");
 if(s.banco.filter(x=>x.reserva_luxo).length!==1)errs.push("luxo não único");
 for(const b of s.banco){const t=s.titulares.filter(x=>x.posicao===b.posicao);
  if(!t.length)errs.push("posição reserva inválida");
  else if(b.preco>Math.min(...t.map(x=>x.preco))+0.001)errs.push("preço reserva "+b.posicao);}
 return errs;
}
function simulate(s,pts,luxId) {
 const t=s.titulares.map(x=>actual(x,pts)),b=s.banco.map(x=>actual(x,pts)),chosen=t.slice(),changes=[],blockers=[];
 let cap=s.capitao_atleta_id;
 for(const reserve of b) {
  const same=t.filter(x=>x.pos===reserve.pos),missing=same.filter(x=>!x.played);
  let out=null,kind="";
  if(missing.length>1&&reserve.played&&reserve.score>0){blockers.push("múltiplos ausentes "+reserve.pos);continue;}
  if(missing.length===1&&reserve.played&&reserve.score>0){out=missing[0];kind="normal";}
  else if(!missing.length&&reserve.id===luxId&&reserve.played){
   const min=Math.min(...same.map(x=>x.score)),ties=same.filter(x=>Math.abs(x.score-min)<1e-9);
   if(reserve.score>min){out=ties.find(x=>x.id===cap)||ties[0];kind="luxo";
    if(ties.length>1&&!ties.some(x=>x.id===cap)){blockers.push("desempate cronológico "+reserve.pos);out=null;}
   }
  }
  if(out){const i=chosen.findIndex(x=>x.id===out.id);if(i<0){blockers.push("troca repetida");continue;}
   chosen[i]=reserve;if(out.id===cap)cap=reserve.id;
   changes.push({tipo:kind,sai:out.name,entra:reserve.name,ganho_bruto:rnd(reserve.score-out.score),transfere_capitao:out.id===s.capitao_atleta_id});}
 }
 const c=chosen.find(x=>x.id===cap);
 return {total:rnd(chosen.reduce((a,x)=>a+x.score,0)+0.5*(c?.score||0)),changes,blockers,
  jogaram:t.filter(x=>x.played).length,ausentes:t.filter(x=>!x.found).map(x=>x.name)};
}
function audit(s,pts) {
 const errors=validate(s);if(errors.length)throw Error("R"+s.rodada+" inválida: "+errors.join("; "));
 const lux=s.banco.find(x=>x.reserva_luxo),base=simulate(s,pts,null),current=simulate(s,pts,lux.atleta_id);
 const options=s.banco.map(x=>({nome:x.apelido,pos:x.posicao,...simulate(s,pts,x.atleta_id)}));
 if([base,current,...options].some(x=>x.blockers.length))throw Error("R"+s.rodada+" requer cronologia");
 const best=options.reduce((a,b)=>b.total>a.total?b:a,options[0]);
 const captain=s.titulares.find(x=>x.atleta_id===s.capitao_atleta_id);
 const projected=s.projecao_titulares_sem_bonus_capitao+0.5*captain.projecao;
 return {rodada:s.rodada,formacao:s.formacao,custo:s.custo,orcamento:s.orcamento,
  projetado_15:rnd(projected),real_sem_luxo:base.total,real_com_luxo:current.total,
  ganho_luxo:rnd(current.total-base.total),luxo_escolhido:lux.apelido,
  luxo_oraculo:best.nome,real_oraculo:best.total,lacuna_oraculo:rnd(best.total-current.total),
  titulares_que_jogaram:current.jogaram,ausentes:current.ausentes,trocas:current.changes};
}
function selfTest() {
 const p=(id)=>({atleta_id:id,apelido:"P"+id,posicao:"ATA"});
 const s={titulares:[p(1),p(2)],banco:[p(3)],capitao_atleta_id:1};
 const pts=(a,b,c,x=true,y=true,z=true)=>({1:{pontuacao:a,entrou_em_campo:x},2:{pontuacao:b,entrou_em_campo:y},3:{pontuacao:c,entrou_em_campo:z}});
 const eq=(x,y,msg)=>{if(Math.abs(x-y)>1e-9)throw Error("Teste "+msg+": "+x+" != "+y);};
 eq(simulate(s,pts(2,5,4),null).total,8,"cap 1,5x");
 eq(simulate(s,pts(2,5,4),3).total,11,"luxo herda cap");
 eq(simulate(s,pts(2,5,2),3).total,8,"luxo igual não entra");
 eq(simulate(s,pts(-3,2,-1),3).total,0.5,"luxo negativo");
 eq(simulate(s,pts(0,5,4,false),null).total,11,"reserva normal herda cap");
 eq(simulate(s,pts(0,5,-1,false),3).total,5,"reserva negativo não entra");
 eq(simulate(s,pts(0,5,4,false),3).total,11,"ausência prevalece");
 eq(simulate(s,pts(2,2,3),3).total,6.5,"empate prioriza cap");
 if(!simulate(s,pts(0,0,4,false,false),3).blockers.length)throw Error("cronologia não bloqueada");
 return 9;
}
function run(root) {
 const rows=[];
 for(const n of [26,27,28,29,30]){
  const snap=JSON.parse(fs.readFileSync(path.join(root,"predictions/pre_round/2026/R"+n+".time-sugerido.json"),"utf8"));
  const pts=JSON.parse(fs.readFileSync(path.join(root,"data/raw/rodada-"+n+"/pontuados.json"),"utf8")).atletas;
  rows.push(audit(snap,pts));
 }
 const sum=k=>rnd(rows.reduce((a,x)=>a+x[k],0)),avg=k=>rnd(sum(k)/rows.length);
 return {status:"EXPLORATORIO_NAO_CERTIFICADO",escopo:"R26-R30; sem técnico; não comparável com times completos da V2; oráculo conhece resultados futuros",
  rodadas:rows,resumo:{n:rows.length,media_projetada:avg("projetado_15"),media_real:avg("real_com_luxo"),
  erro_medio_previsto_menos_real:rnd(avg("projetado_15")-avg("real_com_luxo")),
  ganho_total_luxo:sum("ganho_luxo"),lacuna_total_oraculo:sum("lacuna_oraculo")}};
}
module.exports={simulate,validate,audit,selfTest,run};
if(require.main===module){const report=run(path.resolve(__dirname,".."));console.log(JSON.stringify({testes_sinteticos:selfTest(),...report},null,2));}
