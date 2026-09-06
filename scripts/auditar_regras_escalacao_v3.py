#!/usr/bin/env python3
"""Audita regras determinísticas da escalação completa da V3.

O teste executa o módulo JS real usado pelo site e valida:
- capitão único, nunca técnico, escolhido pela maior projeção;
- banco sem repetir titulares;
- reserva apenas quando preço <= titular mais barato da mesma posição;
- no máximo um Reserva de Luxo;
- Reserva de Luxo pertencente ao banco;
- escolha determinística do Reserva de Luxo pelo maior ganho projetado sobre
  o titular de menor projeção da mesma posição.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OPTIMIZER = ROOT / "site" / "optimizer.js"


def run_node(script: str):
    proc = subprocess.run(
        ["node", "-e", script, str(OPTIMIZER)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return json.loads(proc.stdout)


def main():
    assert OPTIMIZER.exists(), "site/optimizer.js ausente"

    script = r"""
const opt=require(process.argv[1]);
const starters=[
  {atleta_id:1,posicao:'GOL',apelido:'G1',preco:12,projecao:6,titularidade:95,status_id:7},
  {atleta_id:2,posicao:'ZAG',apelido:'Z1',preco:10,projecao:7,titularidade:90,status_id:7},
  {atleta_id:3,posicao:'ZAG',apelido:'Z2',preco:8,projecao:5,titularidade:90,status_id:7},
  {atleta_id:4,posicao:'LAT',apelido:'L1',preco:9,projecao:8,titularidade:92,status_id:7},
  {atleta_id:5,posicao:'LAT',apelido:'L2',preco:7,projecao:4,titularidade:85,status_id:7},
  {atleta_id:6,posicao:'MEI',apelido:'M1',preco:14,projecao:10,titularidade:97,status_id:7},
  {atleta_id:7,posicao:'MEI',apelido:'M2',preco:11,projecao:6,titularidade:88,status_id:7},
  {atleta_id:8,posicao:'ATA',apelido:'A1',preco:15,projecao:9,titularidade:94,status_id:7},
  {atleta_id:9,posicao:'ATA',apelido:'A2',preco:10,projecao:7,titularidade:91,status_id:7},
  {atleta_id:10,posicao:'TEC',apelido:'T1',preco:8,projecao:20,titularidade:100,status_id:7}
];
const candidates=[
  {atleta_id:11,posicao:'GOL',apelido:'RG',preco:11,projecao:5,status_id:7},
  {atleta_id:12,posicao:'ZAG',apelido:'RZ caro',preco:9,projecao:20,status_id:7},
  {atleta_id:13,posicao:'ZAG',apelido:'RZ',preco:8,projecao:6,status_id:7},
  {atleta_id:14,posicao:'LAT',apelido:'RL',preco:7,projecao:9,status_id:7},
  {atleta_id:15,posicao:'MEI',apelido:'RM',preco:10,projecao:8,status_id:7},
  {atleta_id:16,posicao:'ATA',apelido:'RA',preco:10,projecao:8,status_id:7},
  {atleta_id:17,posicao:'ATA',apelido:'RA fora',preco:9,projecao:30,status_id:2}
];
const all=starters.concat(candidates);
const eligible=p=>Number(p.status_id)===7;
const captain=opt.selectCaptain(starters);
const b=opt.selectBench(all,starters,{eligible});
const complete=opt.completeTeam(all,{sel:starters,score:0,cost:0,formation:'4-4-2'},{eligible});
process.stdout.write(JSON.stringify({captain,b,complete}));
"""

    out = run_node(script)
    captain = out["captain"]
    bench_info = out["b"]
    complete = out["complete"]
    bench = bench_info["bench"]

    assert captain["atleta_id"] == 6, f"capitão incorreto: {captain}"
    assert captain["posicao"] != "TEC", "técnico não pode ser capitão"

    starter_ids = set(range(1, 11))
    bench_ids = {int(x["atleta_id"]) for x in bench}
    assert not starter_ids.intersection(bench_ids), "banco repetiu titular"
    assert 12 not in bench_ids, "reserva acima do teto de preço foi selecionado"
    assert 17 not in bench_ids, "jogador inelegível foi selecionado para o banco"

    by_id = {int(x["atleta_id"]): x for x in bench}
    expected_ids = {11, 13, 14, 15, 16}
    assert bench_ids == expected_ids, f"banco inesperado: {sorted(bench_ids)}"

    caps = {11: 12, 13: 8, 14: 7, 15: 11, 16: 10}
    for athlete_id, cap in caps.items():
        assert float(by_id[athlete_id]["preco"]) <= cap + 1e-9
        assert abs(float(by_id[athlete_id]["teto_preco_reserva"]) - cap) <= 1e-9

    luxury = [x for x in bench if x.get("reserva_luxo")]
    assert len(luxury) == 1, f"deve haver exatamente um Reserva de Luxo: {luxury}"
    assert luxury[0]["atleta_id"] == 14, f"Reserva de Luxo incorreto: {luxury[0]}"
    assert bench_info["reservaLuxoAtletaId"] == 14

    assert complete["captainAtletaId"] == 6
    assert complete["reservaLuxoAtletaId"] == 14
    assert {int(x["atleta_id"]) for x in complete["bench"]} == expected_ids

    print(
        "Regras da escalação V3 OK | "
        f"capitão={captain['apelido']} | banco={len(bench)} | "
        f"reserva_luxo={luxury[0]['apelido']}"
    )


if __name__ == "__main__":
    main()
