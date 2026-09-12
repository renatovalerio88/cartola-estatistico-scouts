#!/usr/bin/env python3
"""Corrige a camada de produto sem alterar o modelo estatístico.

Objetivos:
- manter todos os atletas presentes na previsão pré-rodada no payload do site;
- acrescentar técnicos disponíveis no mercado para a experiência Monte seu Time;
- preservar projeções V2/V3 e optimizer.js: técnicos recebem apenas metadados de mercado,
  não uma projeção inventada.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site" / "dados.json"
RAW = ROOT / "data" / "raw"


def main():
    data = json.loads(SITE.read_text(encoding="utf-8"))
    produto = data.setdefault("produto", {})
    rodada = int(produto.get("rodada") or 0)
    jogadores = produto.setdefault("jogadores", [])
    if not rodada:
        raise SystemExit("Rodada do produto ausente")

    mercado_path = RAW / f"rodada-{rodada:02d}" / "jogadores.json"
    mercado = json.loads(mercado_path.read_text(encoding="utf-8")) if mercado_path.exists() else []
    ids = {int(j.get("atleta_id")) for j in jogadores if j.get("atleta_id") is not None}

    tecnicos = 0
    for m in mercado:
        pos = m.get("posicao")
        if pos != "TEC":
            continue
        aid = m.get("id")
        if aid is None or int(aid) in ids:
            continue
        jogadores.append({
            "atleta_id": int(aid),
            "apelido": m.get("apelido") or str(aid),
            "posicao": "TEC",
            "clube_id": int(m.get("clubeId") or 0),
            "sigla_clube": m.get("siglaClube"),
            "status_id": int(m.get("statusId") or 0),
            "titularidade": float(m.get("titularidade") or 0),
            "minutos_esperados": 0,
            "mando": m.get("mando"),
            "sigla_adversario": m.get("siglaAdversario"),
            "data_partida": m.get("dataPartida"),
            "v3s": None,
            "direta_rf": None,
            "projecao": 0.0,
            "preco": float(m.get("preco") or 0),
            "media": float(m.get("media") or 0),
            "jogos": int(m.get("jogos") or 0),
            "foto": m.get("foto"),
            "chance_sg": 0.0,
            "forca_adversario": float(m.get("forcaAdversarioIndice") or 0),
            "pontos_cedidos_posicao": 0.0,
            "somente_selecao_manual": True,
        })
        ids.add(int(aid))
        tecnicos += 1

    produto["jogadores"] = jogadores
    produto["cobertura_interface"] = {
        "jogadores_total": len(jogadores),
        "tecnicos_adicionados": tecnicos,
        "observacao": "Técnicos adicionados apenas para seleção manual; projeções dos atletas permanecem intactas.",
    }
    SITE.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(f"Cobertura do site corrigida: {len(jogadores)} registros; {tecnicos} técnicos adicionados.")


if __name__ == "__main__":
    main()
