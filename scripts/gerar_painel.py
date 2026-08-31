#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "data" / "reports"
SITE_DATA = ROOT / "site" / "dados.json"


def load(name):
    p = REPORTS / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def main():
    SITE_DATA.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "auditoria": load("auditoria-scouts.json"),
        "auditoria_universo": load("auditoria-universo-jogadores.json"),
        "auditoria_vazamento": load("auditoria-vazamento-temporal.json"),
        "auditoria_previsoes_imutaveis": load("auditoria-previsoes-imutaveis.json"),
        "campeonato": load("campeonato-modelos.json"),
        "campeonato_estendido": load("campeonato-modelos-estendido.json"),
        "backtest_pontos": load("backtest-pontos-scouts.json"),
        "backtest_v3s_nested": load("backtest-v3s-nested.json"),
        "backtest_v3s_catboost": load("backtest-v3s-catboost-nested.json"),
        "backtest_v3s_dois_estagios": load("backtest-v3s-dois-estagios.json"),
        "ablation_participacao_enriquecida": load("ablation-participacao-enriquecida.json"),
        "ablation_descanso_brasileirao": load("ablation-descanso-brasileirao.json"),
        "ablation_calendario_externo": load("ablation-calendario-externo.json"),
        "ablation_mudanca_tecnico": load("ablation-mudanca-tecnico.json"),
        "calibracao_participacao": load("calibracao-participacao-dois-estagios.json"),
        "calibracao_producao_condicional": load("calibracao-producao-condicional-dois-estagios.json"),
        "ablation_contexto": load("ablation-contexto.json"),
        "ablation_catboost_contexto": load("ablation-catboost-contexto-nested.json"),
        "comparacao_v2": load("comparacao-v2-oficial-v3.json"),
        "comparacao_catboost_v2": load("comparacao-catboost-off-v2.json"),
        "holdout_posicional": load("holdout-posicional-catboost-v2.json"),
        "significancia": load("significancia-arquiteturas.json"),
        "meta_seletor": load("meta-seletor-v2-v3.json"),
        "calibracao_catboost": load("calibracao-catboost-nested-resumo.json"),
    }
    SITE_DATA.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("Painel V3 atualizado com auditorias, previsões imutáveis, campeonatos, V2 x V3, CatBoost, dois estágios, ablations de participação/descanso/calendário externo/mudança de técnico, calibrações e holdout posicional.")


if __name__ == "__main__":
    main()
