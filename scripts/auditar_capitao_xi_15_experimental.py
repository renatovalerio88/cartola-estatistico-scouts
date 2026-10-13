#!/usr/bin/env python3
"""Auditoria isolada: recálculo do bônus do capitão em backtest XI histórico.

Não altera V2, optimizer.js, escalações, escolha de capitão ou resultados reais.
O relatório original foi construído com bônus de 100%; recalculamos os dois
totais (projetado e real) com bônus de 50%, mantendo exatamente o mesmo XI.
Não é backtest de elegibilidade, orçamento, técnico ou banco prospectivo.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data/reports/backtest-time-sugerido-walk-forward.json"
EPS = 0.025


def analisar(dados: dict) -> dict:
    resultados = []
    for rodada in dados.get("rodadas", []):
        r = int(rodada["rodada"])
        if r == 1 or r == 21 or r >= 30:
            continue
        jogadores = rodada["jogadores"]
        capitaes = [j for j in jogadores if j.get("capitao")]
        if len(jogadores) != 11 or len(capitaes) != 1:
            raise ValueError(f"R{r}: XI ou capitão inconsistente")
        cap = capitaes[0]
        soma_projetada = sum(float(j["projecao"]) for j in jogadores)
        soma_real = sum(float(j["real"]) for j in jogadores)
        bonus_projetado = float(cap["projecao"])
        bonus_real = float(cap["real"])
        original_projetado = float(rodada["projecao"])
        original_real = float(rodada["pontuacao_real"])
        if abs(original_projetado - soma_projetada - bonus_projetado) > EPS:
            raise ValueError(f"R{r}: projeção original não reproduz capitão 2x")
        if abs(original_real - soma_real - bonus_real) > EPS:
            raise ValueError(f"R{r}: real original não reproduz capitão 2x")
        novo_projetado = soma_projetada + 0.5 * bonus_projetado
        novo_real = soma_real + 0.5 * bonus_real
        resultados.append({
            "rodada": r,
            "formacao": rodada.get("formacao"),
            "capitao_atleta_id": cap["atleta_id"],
            "projecao_original_2x": round(original_projetado, 4),
            "real_original_2x": round(original_real, 4),
            "projecao_recalculada_1_5x": round(novo_projetado, 4),
            "real_recalculado_1_5x": round(novo_real, 4),
            "erro_absoluto_original": round(abs(original_projetado - original_real), 4),
            "erro_absoluto_recalculado": round(abs(novo_projetado - novo_real), 4),
        })
    if not resultados:
        raise ValueError("Nenhuma rodada auditável")
    if len({x["rodada"] for x in resultados}) != len(resultados):
        raise ValueError("Rodadas duplicadas")
    media = lambda valores: round(sum(valores) / len(valores), 4)
    antigo = media([x["erro_absoluto_original"] for x in resultados])
    novo = media([x["erro_absoluto_recalculado"] for x in resultados])
    return {
        "tipo": "AUDITORIA_EXPERIMENTAL_RECALCULO_XI",
        "base": "data/reports/backtest-time-sugerido-walk-forward.json",
        "rodadas": [x["rodada"] for x in resultados],
        "n_rodadas": len(resultados),
        "mae_original_capitao_2x": antigo,
        "mae_recalculado_capitao_1_5x": novo,
        "reducao_mae_pontos": round(antigo - novo, 4),
        "media_projetada_1_5x": media([x["projecao_recalculada_1_5x"] for x in resultados]),
        "media_real_1_5x": media([x["real_recalculado_1_5x"] for x in resultados]),
        "rodadas_melhora_mae": sum(x["erro_absoluto_recalculado"] < x["erro_absoluto_original"] for x in resultados),
        "rodadas_piora_mae": sum(x["erro_absoluto_recalculado"] > x["erro_absoluto_original"] for x in resultados),
        "limitacoes": [
            "Não é melhoria de seleção ou de modelo; XI e capitão permanecem idênticos.",
            "Histórico retrospectivo não comprova universo elegível, preço/status pré-mercado.",
            "Sem técnico, orçamento histórico, banco ou Reserva de Luxo reproduzidos.",
            "Não extrapolar este MAE para o desempenho prospectivo da V2.",
        ],
        "detalhes": resultados,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, help="Opcional: gravar JSON fora da produção")
    args = parser.parse_args()
    relatorio = analisar(json.loads(args.input.read_text(encoding="utf-8")))
    saida = json.dumps(relatorio, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(saida + "\n", encoding="utf-8")
    print(saida)


if __name__ == "__main__":
    main()
