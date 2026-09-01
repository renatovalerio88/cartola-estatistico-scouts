#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "data" / "reports"
ARCHIVE = ROOT / "predictions" / "pre_round" / "2026"
SITE_DATA = ROOT / "site" / "dados.json"


def load(name):
    p = REPORTS / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def load_latest_explicabilidade():
    arquivos = sorted(ARCHIVE.glob("R??.explicabilidade.json"), reverse=True)
    if not arquivos:
        return {}
    return json.loads(arquivos[0].read_text(encoding="utf-8"))


def main():
    SITE_DATA.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "auditoria": load("auditoria-scouts.json"),
        "auditoria_universo": load("auditoria-universo-jogadores.json"),
        "auditoria_vazamento": load("auditoria-vazamento-temporal.json"),
        "auditoria_previsoes_imutaveis": load("auditoria-previsoes-imutaveis.json"),
        "auditoria_explicabilidade_pre_rodada": load("auditoria-explicabilidade-pre-rodada.json"),
        "explicabilidade_pre_rodada_status": load("explicabilidade-pre-rodada.json"),
        "explicabilidade_pre_rodada": load_latest_explicabilidade(),
        "auditoria_clima_pre_rodada": load("auditoria-clima-pre-rodada.json"),
        "clima_pre_rodada": load("clima-pre-rodada.json"),
        "campeonato": load("campeonato-modelos.json"),
        "campeonato_estendido": load("campeonato-modelos-estendido.json"),
        "auditoria_eventos_raros": load("auditoria-eventos-raros.json"),
        "guardrail_scouts_raros": load("guardrail-scouts-raros.json"),
        "backtest_guardrail_raros_nested": load("backtest-v3s-guardrail-raros-nested.json"),
        "gate_guardrail_raros": load("gate-guardrail-raros.json"),
        "backtest_pontos": load("backtest-pontos-scouts.json"),
        "backtest_v3s_nested": load("backtest-v3s-nested.json"),
        "backtest_v3s_catboost": load("backtest-v3s-catboost-nested.json"),
        "backtest_v3s_dois_estagios": load("backtest-v3s-dois-estagios.json"),
        "ablation_participacao_enriquecida": load("ablation-participacao-enriquecida.json"),
        "ablation_descanso_brasileirao": load("ablation-descanso-brasileirao.json"),
        "ablation_calendario_externo": load("ablation-calendario-externo.json"),
        "ablation_mudanca_tecnico": load("ablation-mudanca-tecnico.json"),
        "ablation_horario_partida": load("ablation-horario-partida.json"),
        "resumo_contextos": load("resumo-contextos.json"),
        "calibracao_participacao": load("calibracao-participacao-dois-estagios.json"),
        "calibracao_producao_condicional": load("calibracao-producao-condicional-dois-estagios.json"),
        "ablation_contexto": load("ablation-contexto.json"),
        "ablation_catboost_contexto": load("ablation-catboost-contexto-nested.json"),
        "comparacao_v2": load("comparacao-v2-oficial-v3.json"),
        "comparacao_catboost_v2": load("comparacao-catboost-off-v2.json"),
        "ranking_arquiteturas_comum": load("ranking-arquiteturas-comum.json"),
        "seletor_posicional_temporal": load("seletor-posicional-temporal.json"),
        "holdout_posicional": load("holdout-posicional-catboost-v2.json"),
        "significancia": load("significancia-arquiteturas.json"),
        "meta_seletor": load("meta-seletor-v2-v3.json"),
        "calibracao_catboost": load("calibracao-catboost-nested-resumo.json"),
    }
    SITE_DATA.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("Painel V3 atualizado com explicabilidade por scouts, auditorias, previsões imutáveis, clima prospectivo, campeonatos, eventos raros e seu gate nested, ranking comum V2/V3/CatBoost, seletor posicional temporal, dois estágios, ablations, calibrações e holdout posicional.")


if __name__ == "__main__":
    main()
