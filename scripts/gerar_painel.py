#!/usr/bin/env python3
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "data" / "reports"
ARCHIVE = ROOT / "predictions" / "pre_round" / "2026"
RAW = ROOT / "data" / "raw"
SITE_DATA = ROOT / "site" / "dados.json"


def load(name):
    p = REPORTS / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def load_latest_explicabilidade():
    arquivos = sorted(ARCHIVE.glob("R??.explicabilidade.json"), reverse=True)
    if not arquivos:
        return {}
    return json.loads(arquivos[0].read_text(encoding="utf-8"))


def latest_pre_round():
    arquivos = sorted(
        [p for p in ARCHIVE.glob("R??.csv") if ".catboost." not in p.name],
        reverse=True,
    )
    if not arquivos:
        return {"rodada": None, "jogadores": []}
    p = arquivos[0]
    rodada = int(p.stem[1:])
    mercado_path = RAW / f"rodada-{rodada:02d}" / "jogadores.json"
    mercado = json.loads(mercado_path.read_text(encoding="utf-8")) if mercado_path.exists() else []
    por_id = {int(j.get("id")): j for j in mercado if j.get("id") is not None}
    jogadores = []
    with p.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            aid = int(row["atleta_id"])
            m = por_id.get(aid, {})
            def num(chave, padrao=0.0):
                try:
                    return float(row.get(chave) or padrao)
                except (TypeError, ValueError):
                    return padrao
            jogadores.append({
                "atleta_id": aid,
                "apelido": row.get("apelido") or m.get("apelido") or str(aid),
                "posicao": row.get("posicao") or m.get("posicao"),
                "clube_id": int(row.get("clube_id") or m.get("clubeId") or 0),
                "sigla_clube": row.get("sigla_clube") or m.get("siglaClube"),
                "status_id": int(float(row.get("status_id") or m.get("statusId") or 0)),
                "titularidade": num("titularidade_pre_rodada", m.get("titularidade", 0)),
                "minutos_esperados": num("minutos_esperados_pre_rodada", m.get("minutosEsperados", 0)),
                "mando": row.get("mando") or m.get("mando"),
                "sigla_adversario": row.get("sigla_adversario") or m.get("siglaAdversario"),
                "data_partida": row.get("data_partida") or m.get("dataPartida"),
                "v3s": num("v3s_expected_scouts"),
                "direta_rf": num("direta_rf_lab"),
                "projecao": num("v3h_hibrido"),
                "preco": float(m.get("preco") or 0),
                "media": float(m.get("media") or 0),
                "jogos": int(m.get("jogos") or 0),
                "foto": m.get("foto"),
                "chance_sg": float(m.get("chanceSG") or 0),
                "forca_adversario": float(m.get("forcaAdversarioIndice") or 0),
                "pontos_cedidos_posicao": float(m.get("pontosCedidosMediaPosicao") or 0),
            })
    return {"rodada": rodada, "jogadores": jogadores}


def main():
    SITE_DATA.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "produto": latest_pre_round(),
        "auditoria": load("auditoria-scouts.json"),
        "auditoria_universo": load("auditoria-universo-jogadores.json"),
        "auditoria_vazamento": load("auditoria-vazamento-temporal.json"),
        "auditoria_previsoes_imutaveis": load("auditoria-previsoes-imutaveis.json"),
        "avaliacao_prospectiva_imutavel": load("avaliacao-prospectiva-imutavel.json"),
        "avaliacao_prospectiva_catboost_imutavel": load("avaliacao-prospectiva-catboost-imutavel.json"),
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
        "gate_dois_estagios": load("gate-dois-estagios.json"),
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
        "controle_multipla_comparacao": load("controle-multipla-comparacao.json"),
        "ranking_arquiteturas_comum": load("ranking-arquiteturas-comum.json"),
        "seletor_posicional_temporal": load("seletor-posicional-temporal.json"),
        "holdout_posicional": load("holdout-posicional-catboost-v2.json"),
        "significancia": load("significancia-arquiteturas.json"),
        "meta_seletor": load("meta-seletor-v2-v3.json"),
        "calibracao_catboost": load("calibracao-catboost-nested-resumo.json"),
        "top50_liga_nacional_viabilidade": load("top50-liga-nacional-viabilidade.json"),
        "top50_liga_nacional_coorte": load("top50-liga-nacional-coorte.json"),
        "top50_liga_nacional_estrategias": load("top50-liga-nacional-estrategias.json"),
    }
    SITE_DATA.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Site V3 atualizado: rodada {payload['produto']['rodada']}, {len(payload['produto']['jogadores'])} jogadores no payload de produto.")


if __name__ == "__main__":
    main()
