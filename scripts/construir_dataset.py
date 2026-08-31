#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import defaultdict, deque
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "derived"
SCOUTS = ["G", "A", "FT", "FD", "FF", "FS", "PS", "I", "DS", "SG", "DP", "DE", "GC", "CV", "CA", "GS", "FC", "PC", "PP"]
POS = {1: "GOL", 2: "LAT", 3: "ZAG", 4: "MEI", 5: "ATA", 6: "TEC"}
POS_JOGADORES = {1, 2, 3, 4, 5}


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def partidas_lista(path: Path):
    if not path.exists():
        return []
    raw = load(path)
    return raw.get("partidas", raw if isinstance(raw, list) else [])


def jogadores_lista(path: Path):
    if not path.exists():
        return []
    raw = load(path)
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        return raw.get("atletas", raw.get("jogadores", []))
    return []


def pontuados_map(path: Path):
    if not path.exists():
        return {}
    raw = load(path)
    atletas = raw.get("atletas", raw if isinstance(raw, dict) else {})
    out = {}
    for aid_raw, atleta in atletas.items():
        if not isinstance(atleta, dict):
            continue
        try:
            aid = int(aid_raw)
        except (TypeError, ValueError):
            continue
        out[aid] = atleta
    return out


def rodada_resolvida(partidas, pontuados):
    """Só autoriza targets quando a rodada possui resultados finais observáveis.

    Isso impede que uma rodada futura/em andamento, cujo pontuados.json ainda esteja vazio
    ou parcial, seja interpretada como se todos os jogadores tivessem feito zero ponto.
    Uma rodada incompleta também fica fora do histórico até todos os placares oficiais
    estarem disponíveis.
    """
    if not pontuados or not partidas:
        return False
    validas = [p for p in partidas if isinstance(p, dict)]
    if not validas:
        return False
    for p in validas:
        if p.get("placar_oficial_mandante") is None or p.get("placar_oficial_visitante") is None:
            return False
    return True


def partida_context(partidas):
    ctx = {}
    for p in partidas:
        if not isinstance(p, dict):
            continue
        casa = p.get("clube_casa_id") or p.get("clube_casa")
        fora = p.get("clube_visitante_id") or p.get("clube_visitante")
        try:
            casa, fora = int(casa), int(fora)
        except (TypeError, ValueError):
            continue
        ctx[casa] = {"mando": 1, "adversario_id": fora}
        ctx[fora] = {"mando": 0, "adversario_id": casa}
    return ctx


def mean(values):
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def ewma(values, alpha=.45):
    values = list(values)
    if not values:
        return 0.0
    acc = float(values[0])
    for x in values[1:]:
        acc = alpha * float(x) + (1 - alpha) * acc
    return acc


def streak(values, target):
    count = 0
    for value in reversed(list(values)):
        if int(value) != int(target):
            break
        count += 1
    return count


def team_features(team_history, club_id, prefix):
    h = team_history[club_id]
    gf = list(h["gf"])
    ga = list(h["ga"])
    return {
        f"{prefix}_jogos": len(gf),
        f"{prefix}_gf_media5": mean(gf[-5:]),
        f"{prefix}_ga_media5": mean(ga[-5:]),
        f"{prefix}_gf_ewma": ewma(gf),
        f"{prefix}_ga_ewma": ewma(ga),
    }


def atualizar_times(team_history, partidas):
    # Só é chamado DEPOIS de congelar as features da rodada R e apenas para rodadas resolvidas.
    for p in partidas:
        if not isinstance(p, dict):
            continue
        try:
            casa = int(p.get("clube_casa_id"))
            fora = int(p.get("clube_visitante_id"))
            gols_casa = p.get("placar_oficial_mandante")
            gols_fora = p.get("placar_oficial_visitante")
            if gols_casa is None or gols_fora is None:
                continue
            gols_casa = float(gols_casa)
            gols_fora = float(gols_fora)
        except (TypeError, ValueError):
            continue
        team_history[casa]["gf"].append(gols_casa)
        team_history[casa]["ga"].append(gols_fora)
        team_history[fora]["gf"].append(gols_fora)
        team_history[fora]["ga"].append(gols_casa)


def jogador_id(j):
    raw = j.get("id", j.get("atleta_id"))
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def jogador_posicao_id(j):
    raw = j.get("posicaoId", j.get("posicao_id", 0))
    try:
        return int(raw or 0)
    except (TypeError, ValueError):
        return 0


def jogador_clube_id(j):
    raw = j.get("clubeId", j.get("clube_id", 0))
    try:
        return int(raw or 0)
    except (TypeError, ValueError):
        return 0


def target_atleta(pontuado):
    if not isinstance(pontuado, dict):
        return 0.0, 0, {}
    entrou = bool(pontuado.get("entrou_em_campo", pontuado.get("entrouEmCampo", False)))
    if not entrou:
        return 0.0, 0, {}
    pontos = float(pontuado.get("pontuacao", pontuado.get("pontuacaoReal", 0)) or 0)
    scouts = pontuado.get("scout", pontuado.get("scouts", {})) or {}
    return pontos, 1, scouts


def main():
    history = defaultdict(lambda: {
        "points": deque(maxlen=20),
        "entered": deque(maxlen=20),
        "scouts": defaultdict(lambda: deque(maxlen=20)),
        "points_cond": deque(maxlen=20),
        "scouts_cond": defaultdict(lambda: deque(maxlen=20)),
    })
    team_history = defaultdict(lambda: {"gf": deque(maxlen=20), "ga": deque(maxlen=20)})
    rows = []
    round_stats = []
    unresolved_rounds = []

    for folder in sorted(RAW.glob("rodada-*")):
        jogadores_path = folder / "jogadores.json"
        pontuados_path = folder / "pontuados.json"
        if not jogadores_path.exists() or not pontuados_path.exists():
            continue

        rodada = int(folder.name.split("-")[-1])
        jogadores = jogadores_lista(jogadores_path)
        pontuados = pontuados_map(pontuados_path)
        partidas = partidas_lista(folder / "partidas.json")
        resolvida = rodada_resolvida(partidas, pontuados)
        ctx = partida_context(partidas)

        candidatos = []
        for j in jogadores:
            if not isinstance(j, dict):
                continue
            aid = jogador_id(j)
            pos_id = jogador_posicao_id(j)
            if aid is None or pos_id not in POS_JOGADORES:
                continue
            candidatos.append((aid, j, pos_id))

        if not resolvida:
            unresolved_rounds.append(rodada)
            round_stats.append({
                "rodada": rodada,
                "resolvida": False,
                "universo_jogadores": len(candidatos),
                "entraram_em_campo": None,
                "nao_entraram": None,
                "linhas_dataset": 0,
                "motivo": "rodada sem pontuados completos e/ou sem todos os placares oficiais; excluída de treino e validação",
            })
            # Regra crítica: rodada futura/em andamento não altera histórico de jogador nem de clube.
            continue

        created = 0
        entered_count = 0
        zero_count = 0
        for aid, j, pos_id in candidatos:
            h = history[aid]
            pontos_atual, entrou_atual, scouts_atual = target_atleta(pontuados.get(aid))
            entered_count += entrou_atual
            zero_count += 1 - entrou_atual

            past_n = len(h["points"])
            if past_n >= 1:
                clube_id = jogador_clube_id(j)
                adversario_id = int(ctx.get(clube_id, {}).get("adversario_id", 0) or 0)
                entered_vals = list(h["entered"])
                atuacoes_passadas = int(sum(entered_vals))
                desde_atuou = 20
                for distancia, flag in enumerate(reversed(entered_vals), start=1):
                    if flag:
                        desde_atuou = distancia - 1
                        break

                points_cond = list(h["points_cond"])
                row = {
                    "rodada": rodada,
                    "atleta_id": aid,
                    "apelido": j.get("apelido") or str(aid),
                    "posicao_id": pos_id,
                    "posicao": POS.get(pos_id, "?"),
                    "clube_id": clube_id,
                    "mando": ctx.get(clube_id, {}).get("mando", -1),
                    "adversario_id": adversario_id,
                    "historico_jogos": past_n,
                    "historico_atuacoes": atuacoes_passadas,
                    "taxa_atuacao_historica": atuacoes_passadas / past_n,
                    "entrou_media2": mean(entered_vals[-2:]),
                    "entrou_media3": mean(entered_vals[-3:]),
                    "entrou_media5": mean(entered_vals[-5:]),
                    "entrou_media10": mean(entered_vals[-10:]),
                    "entrou_ewma": ewma(entered_vals),
                    "rodadas_desde_atuou": desde_atuou,
                    "sequencia_atuacoes": streak(entered_vals, 1),
                    "sequencia_ausencias": streak(entered_vals, 0),
                    "pontos_media3": mean(list(h["points"])[-3:]),
                    "pontos_media5": mean(list(h["points"])[-5:]),
                    "pontos_ewma": ewma(list(h["points"])),
                    "cond_atuacoes": len(points_cond),
                    "pontos_cond_media3": mean(points_cond[-3:]),
                    "pontos_cond_media5": mean(points_cond[-5:]),
                    "pontos_cond_ewma": ewma(points_cond),
                    "target_entrou": entrou_atual,
                    "target_pontos": pontos_atual,
                }
                row.update(team_features(team_history, clube_id, "time"))
                row.update(team_features(team_history, adversario_id, "adversario"))

                for scout in SCOUTS:
                    vals = list(h["scouts"][scout])
                    vals_cond = list(h["scouts_cond"][scout])
                    row[f"{scout}_media3"] = mean(vals[-3:])
                    row[f"{scout}_media5"] = mean(vals[-5:])
                    row[f"{scout}_ewma"] = ewma(vals)
                    row[f"{scout}_cond_media3"] = mean(vals_cond[-3:])
                    row[f"{scout}_cond_media5"] = mean(vals_cond[-5:])
                    row[f"{scout}_cond_ewma"] = ewma(vals_cond)
                    row[f"target_{scout}"] = float(scouts_atual.get(scout, 0) or 0) if entrou_atual else 0.0

                rows.append(row)
                created += 1

            h["points"].append(pontos_atual)
            h["entered"].append(entrou_atual)
            for scout in SCOUTS:
                valor = float(scouts_atual.get(scout, 0) or 0) if entrou_atual else 0.0
                h["scouts"][scout].append(valor)
            if entrou_atual:
                h["points_cond"].append(pontos_atual)
                for scout in SCOUTS:
                    h["scouts_cond"][scout].append(float(scouts_atual.get(scout, 0) or 0))

        atualizar_times(team_history, partidas)
        round_stats.append({
            "rodada": rodada,
            "resolvida": True,
            "universo_jogadores": len(candidatos),
            "entraram_em_campo": entered_count,
            "nao_entraram": zero_count,
            "linhas_dataset": created,
        })

    df = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT / "dataset-walk-forward.csv", index=False)

    context_cols = [
        c for c in df.columns
        if c.startswith("time_") or c.startswith("adversario_") or c in {
            "mando", "historico_atuacoes", "taxa_atuacao_historica", "entrou_media2",
            "entrou_media3", "entrou_media5", "entrou_media10", "entrou_ewma",
            "rodadas_desde_atuou", "sequencia_atuacoes", "sequencia_ausencias"
        }
    ] if len(df) else []
    conditional_cols = [c for c in df.columns if "_cond_" in c or c == "cond_atuacoes"] if len(df) else []

    meta = {
        "linhas": len(df),
        "rodada_min": int(df.rodada.min()) if len(df) else None,
        "rodada_max": int(df.rodada.max()) if len(df) else None,
        "jogadores": int(df.atleta_id.nunique()) if len(df) else 0,
        "colunas": list(df.columns),
        "features_contexto": context_cols,
        "features_condicionais_participacao": conditional_cols,
        "rodadas_nao_resolvidas_excluidas": unresolved_rounds,
        "criterio_rodada_resolvida": "pontuados.json não vazio e todos os jogos da rodada com placar_oficial_mandante/visitante disponíveis",
        "universo_amostral": "Todos os jogadores válidos presentes em jogadores.json (GOL/LAT/ZAG/MEI/ATA) das rodadas resolvidas, inclusive os que não entraram em campo; não participantes recebem target_pontos/scouts=0. Rodadas futuras/em andamento são totalmente excluídas de treino/validação até possuírem resultado final observável.",
        "anti_leakage": "Features da rodada R usam exclusivamente histórico acumulado até R-1 resolvida. Participação, pontos, scouts e placar de R só são incorporados depois de congelar todas as linhas de R. Rodadas não resolvidas não geram targets zero e não alteram o histórico. Taxas, sequências e janelas de participação são calculadas exclusivamente sobre flags target_entrou de rodadas resolvidas anteriores. As features *_cond_* usam somente atuações anteriores a R em que o atleta entrou em campo. statusId/preço/média pós-rodada de jogadores.json não entram como features.",
        "por_rodada": round_stats,
    }
    (OUT / "dataset-meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"Dataset walk-forward universo completo: {len(df)} linhas, "
        f"{len(df.columns) if len(df) else 0} colunas, {meta['jogadores']} jogadores; "
        f"contexto anti-leakage={len(context_cols)} features; condicionais={len(conditional_cols)}; "
        f"rodadas não resolvidas excluídas={unresolved_rounds}."
    )


if __name__ == "__main__":
    main()
