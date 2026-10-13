#!/usr/bin/env python3
"""Auditoria do XI retrospectivo com capitao 1,5x e calibracao sem olhar o futuro.

Nao altera selecao, V2, otimizador ou modelo cientifico. O relatorio historico
nao equivale a previsoes congeladas antes do mercado.
"""
from __future__ import annotations

import argparse
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data/reports/backtest-time-sugerido-walk-forward.json"
OUTPUT = ROOT / "data/reports/auditoria-calibracao-xi-walk-forward.json"
METODOS = ("sem_ajuste", "media_passada", "media_3_passadas",
           "media_5_passadas", "mediana_passada", "media_regularizada_5")


def media(xs):
    return statistics.mean(xs) if xs else 0.0


def corrigir(nome, erros):
    if not erros or nome == "sem_ajuste":
        return 0.0
    if nome == "media_passada":
        return media(erros)
    if nome == "media_3_passadas":
        return media(erros[-3:])
    if nome == "media_5_passadas":
        return media(erros[-5:])
    if nome == "mediana_passada":
        return statistics.median(erros)
    if nome == "media_regularizada_5":
        return media(erros) * len(erros) / (len(erros) + 5)
    raise ValueError(nome)


def auditar(dados):
    linhas = sorted(dados["rodadas"], key=lambda r: int(r["rodada"]))
    if not linhas or len({r["rodada"] for r in linhas}) != len(linhas):
        raise ValueError("Rodadas vazias ou duplicadas")
    passados, resultados, posicoes = [], [], {}
    for r in linhas:
        rodada = int(r["rodada"])
        atletas = r["jogadores"]
        capitaes = [p for p in atletas if p.get("capitao")]
        if len(atletas) != 11 or len(capitaes) != 1:
            raise ValueError(f"R{rodada}: XI/capitao invalidos")
        cap = capitaes[0]
        if int(cap["atleta_id"]) != int(r["capitao"]["atleta_id"]):
            raise ValueError(f"R{rodada}: capitao inconsistente")
        p = sum(float(a["projecao"]) for a in atletas) + .5 * float(cap["projecao"])
        y = sum(float(a["real"]) for a in atletas) + .5 * float(cap["real"])
        # O arquivo original computa 2x para o capitao; confirmar a premissa.
        if abs(float(r["projecao"]) - p - .5 * float(cap["projecao"])) > .03:
            raise ValueError(f"R{rodada}: projeção 2x nao confere")
        if abs(float(r["pontuacao_real"]) - y - .5 * float(cap["real"])) > .03:
            raise ValueError(f"R{rodada}: real 2x nao confere")
        metodos = {}
        for nome in METODOS:
            offset = corrigir(nome, passados)
            metodos[nome] = {"ajuste": round(offset, 4),
                             "mae_rodada": round(abs(p - offset - y), 4)}
        resultados.append({"rodada": rodada, "formacao": r["formacao"],
                           "projetado_1_5x": round(p, 4),
                           "real_1_5x": round(y, 4),
                           "vies": round(p - y, 4), "metodos": metodos})
        for a in atletas:
            k = a["posicao"]
            posicoes.setdefault(k, []).append((float(a["projecao"]), float(a["real"])))
        passados.append(p - y)
    comparacao = {}
    for nome in METODOS:
        # Mesma amostra para todos, com pelo menos uma rodada anterior disponivel.
        comparacao[nome] = {"rodadas": len(resultados) - 1,
                            "mae": round(media([r["metodos"][nome]["mae_rodada"]
                                                for r in resultados[1:]]), 4)}
    pos = {k: {"n": len(v), "media_projetada": round(media([x for x, _ in v]), 4),
               "media_real": round(media([y for _, y in v]), 4),
               "vies": round(media([x-y for x, y in v]), 4),
               "mae": round(media([abs(x-y) for x, y in v]), 4)}
           for k, v in posicoes.items()}
    return {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "fonte": str(INPUT.relative_to(ROOT)),
        "natureza": "retrospectivo; sem prova de congelamento pre-mercado",
        "rodadas": [r["rodada"] for r in resultados],
        "formacoes": sorted({r["formacao"] for r in resultados}),
        "media_projetada_1_5x": round(media([r["projetado_1_5x"] for r in resultados]), 4),
        "media_real_1_5x": round(media([r["real_1_5x"] for r in resultados]), 4),
        "mae_sem_calibracao_1_5x": round(media([abs(r["vies"]) for r in resultados]), 4),
        "vies_medio": round(media([r["vies"] for r in resultados]), 4),
        "posicoes": pos, "comparacao_temporal": comparacao, "detalhes": resultados,
        "ressalvas": [
            "A calibracao usa somente erros anteriores a cada rodada, mas comparar metodos na mesma amostra nao prova ganho futuro.",
            "Calibrar o total nao altera a escolha dos jogadores ou os pontos reais.",
            "Sem mercado pre-rodada, preco, status, tecnico e banco historicos comprovados.",
            "Auditar universo de candidatos para evitar selecao condicionada a quem pontuou na rodada.",
            "Nao promover ao site sem validacao temporal independente e aprovacao."
        ]
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--entrada", type=Path, default=INPUT)
    parser.add_argument("--saida", type=Path, default=OUTPUT)
    args = parser.parse_args()
    resultado = auditar(json.loads(args.entrada.read_text(encoding="utf-8")))
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Rodadas:", len(resultado["rodadas"]))
    print("MAE 1,5x:", resultado["mae_sem_calibracao_1_5x"])
    for nome, valores in resultado["comparacao_temporal"].items():
        print(nome, valores)


if __name__ == "__main__":
    main()
