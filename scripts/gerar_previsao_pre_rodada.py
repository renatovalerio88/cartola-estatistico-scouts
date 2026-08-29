#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.backtest_v3s_nested import (
    POSITIONS,
    SCOUT_WEIGHTS,
    choose_hybrid_alpha,
    choose_model,
    direct_rf_predict,
    fit_predict,
)

RAW = ROOT / "data" / "raw"
DATA = ROOT / "data" / "derived" / "dataset-walk-forward.csv"
BACKTEST = ROOT / "data" / "reports" / "backtest-v3s-nested.json"
ARCHIVE = ROOT / "predictions" / "pre_round" / "2026"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def mean(v):
    return sum(v) / len(v) if v else 0.0


def ewma(v, alpha=.45):
    v = list(v)
    if not v:
        return 0.0
    acc = float(v[0])
    for x in v[1:]:
        acc = alpha * float(x) + (1 - alpha) * acc
    return acc


def partidas_lista(path: Path):
    if not path.exists():
        return []
    raw = load(path)
    return raw.get("partidas", raw if isinstance(raw, list) else [])


def atualizar_times(team_history, partidas):
    for p in partidas:
        if not isinstance(p, dict):
            continue
        try:
            casa = int(p.get("clube_casa_id"))
            fora = int(p.get("clube_visitante_id"))
            gc = p.get("placar_oficial_mandante")
            gf = p.get("placar_oficial_visitante")
            if gc is None or gf is None:
                continue
            gc = float(gc)
            gf = float(gf)
        except (TypeError, ValueError):
            continue
        team_history[casa]["gf"].append(gc)
        team_history[casa]["ga"].append(gf)
        team_history[fora]["gf"].append(gf)
        team_history[fora]["ga"].append(gc)


def team_features(team_history, club_id, prefix):
    h = team_history[int(club_id or 0)]
    gf = list(h["gf"])
    ga = list(h["ga"])
    return {
        f"{prefix}_jogos": len(gf),
        f"{prefix}_gf_media5": mean(gf[-5:]),
        f"{prefix}_ga_media5": mean(ga[-5:]),
        f"{prefix}_gf_ewma": ewma(gf),
        f"{prefix}_ga_ewma": ewma(ga),
    }


def pontuados_dict(path: Path):
    if not path.exists():
        return {}
    raw = load(path)
    atletas = raw.get("atletas", raw if isinstance(raw, dict) else {})
    return atletas if isinstance(atletas, dict) else {}


def detectar_rodada_aberta():
    candidatas = []
    for folder in sorted(RAW.glob("rodada-*")):
        try:
            rodada = int(folder.name.split("-")[-1])
        except ValueError:
            continue
        resumo_path = folder / "resumo.json"
        jogadores_path = folder / "jogadores.json"
        pontuados_path = folder / "pontuados.json"
        if not resumo_path.exists() or not jogadores_path.exists():
            continue
        resumo = load(resumo_path)
        pontuados_vazios = True
        if pontuados_path.exists():
            try:
                p = load(pontuados_path)
                if isinstance(p, dict):
                    atletas = p.get("atletas", p)
                    pontuados_vazios = not bool(atletas)
                elif isinstance(p, list):
                    pontuados_vazios = not bool(p)
            except Exception:
                pontuados_vazios = True
        if int(resumo.get("statusMercado") or 0) == 1 and pontuados_vazios:
            candidatas.append((rodada, folder, resumo))
    if not candidatas:
        return None
    return max(candidatas, key=lambda x: x[0])


def reconstruir_historico(rodada_atual: int):
    players = defaultdict(
        lambda: {
            "points": deque(maxlen=40),
            "scouts": defaultdict(lambda: deque(maxlen=40)),
        }
    )
    teams = defaultdict(lambda: {"gf": deque(maxlen=40), "ga": deque(maxlen=40)})
    for rodada in range(1, rodada_atual):
        folder = RAW / f"rodada-{rodada:02d}"
        for aid_raw, a in pontuados_dict(folder / "pontuados.json").items():
            if not isinstance(a, dict) or not a.get("entrou_em_campo", False):
                continue
            try:
                aid = int(aid_raw)
            except (TypeError, ValueError):
                continue
            h = players[aid]
            h["points"].append(float(a.get("pontuacao") or 0))
            scouts = a.get("scout") or {}
            for s in SCOUT_WEIGHTS:
                h["scouts"][s].append(float(scouts.get(s, 0) or 0))
        atualizar_times(teams, partidas_lista(folder / "partidas.json"))
    return players, teams


def montar_frame_atual(rodada: int, folder: Path):
    jogadores = load(folder / "jogadores.json")
    if not isinstance(jogadores, list):
        raise SystemExit("jogadores.json da rodada aberta não é uma lista")
    player_history, team_history = reconstruir_historico(rodada)
    rows = []
    meta = []
    for j in jogadores:
        if not isinstance(j, dict):
            continue
        try:
            aid = int(j.get("id"))
        except (TypeError, ValueError):
            continue
        pos = str(j.get("posicao") or "").upper()
        if pos not in POSITIONS:
            continue
        h = player_history.get(aid)
        if not h or not h["points"]:
            continue
        clube_id = int(j.get("clubeId") or 0)
        adversario_id = int(j.get("adversarioId") or 0)
        mando_raw = j.get("mando")
        mando = 1 if mando_raw == "casa" else 0 if mando_raw == "fora" else -1
        pontos = list(h["points"])
        row = {
            "rodada": rodada,
            "atleta_id": aid,
            "posicao": pos,
            "clube_id": clube_id,
            "mando": mando,
            "adversario_id": adversario_id,
            "historico_jogos": len(pontos),
            "pontos_media3": mean(pontos[-3:]),
            "pontos_media5": mean(pontos[-5:]),
            "pontos_ewma": ewma(pontos),
        }
        row.update(team_features(team_history, clube_id, "time"))
        row.update(team_features(team_history, adversario_id, "adversario"))
        for s in SCOUT_WEIGHTS:
            vals = list(h["scouts"][s])
            row[f"{s}_media3"] = mean(vals[-3:])
            row[f"{s}_media5"] = mean(vals[-5:])
            row[f"{s}_ewma"] = ewma(vals)
        rows.append(row)
        meta.append(
            {
                "atleta_id": aid,
                "apelido": j.get("apelido") or j.get("nome") or str(aid),
                "posicao": pos,
                "clube_id": clube_id,
                "sigla_clube": j.get("siglaClube"),
                "status_id": j.get("statusId"),
                "titularidade_pre_rodada": j.get("titularidade"),
                "minutos_esperados_pre_rodada": j.get("minutosEsperados"),
                "mando": mando_raw,
                "adversario_id": adversario_id,
                "sigla_adversario": j.get("siglaAdversario"),
                "data_partida": j.get("dataPartida"),
            }
        )
    return pd.DataFrame(rows), pd.DataFrame(meta)


def sha256_bytes(data: bytes):
    return hashlib.sha256(data).hexdigest()


def canonical_csv(df: pd.DataFrame):
    return df.to_csv(index=False, lineterminator="\n", float_format="%.6f").encode("utf-8")


def escrever_imutavel(path: Path, data: bytes):
    if path.exists():
        atual = path.read_bytes()
        if atual != data:
            raise SystemExit(
                f"PREVISÃO IMUTÁVEL: {path} já existe com conteúdo diferente; sobrescrita recusada"
            )
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return True


def main():
    aberta = detectar_rodada_aberta()
    if not aberta:
        print("Nenhuma rodada aberta com dados pré-jogo disponíveis; nada a arquivar.")
        return
    rodada, folder, resumo = aberta
    dataset = pd.read_csv(DATA)
    dataset = dataset[(dataset.rodada < rodada) & dataset.posicao.isin(POSITIONS)].copy()
    current, meta = montar_frame_atual(rodada, folder)
    if current.empty:
        raise SystemExit("Sem jogadores com histórico suficiente para previsão pré-rodada")

    v3s_score = np.zeros(len(current), float)
    direct_score = np.zeros(len(current), float)
    selections = []
    for pos in POSITIONS:
        mask = current.posicao.eq(pos)
        test = current[mask]
        history = dataset[dataset.posicao.eq(pos)]
        if test.empty:
            continue
        local = np.zeros(len(test), float)
        for scout, weight in SCOUT_WEIGHTS.items():
            if f"target_{scout}" not in history.columns:
                continue
            winner, inner_scores = choose_model(history, scout, rodada)
            try:
                pred = fit_predict(winner, history, test, scout)
            except Exception:
                pred = test[f"{scout}_ewma"].fillna(0).to_numpy(float)
                winner = "ewma_fallback"
            local += pred * float(weight)
            selections.append(
                {
                    "posicao": pos,
                    "scout": scout,
                    "modelo": winner,
                    "mae_validacao_passada": inner_scores.get(winner),
                }
            )
        v3s_score[np.flatnonzero(mask.to_numpy())] = local
        direct_score[np.flatnonzero(mask.to_numpy())] = direct_rf_predict(history, test)

    bt = load(BACKTEST)
    prior_oos = pd.DataFrame(bt.get("previsoes", []))
    prior_oos = prior_oos[prior_oos.rodada < rodada] if not prior_oos.empty else prior_oos
    alpha, alpha_scores = choose_hybrid_alpha(prior_oos)
    hybrid = alpha * v3s_score + (1 - alpha) * direct_score

    pred = meta.copy()
    pred["rodada"] = rodada
    pred["v3s_expected_scouts"] = v3s_score
    pred["direta_rf_lab"] = direct_score
    pred["v3h_hibrido"] = hybrid
    pred["alpha_v3s"] = alpha
    pred["alpha_rf_direto"] = 1 - alpha
    pred = pred.sort_values(["posicao", "v3h_hibrido", "atleta_id"], ascending=[True, False, True])

    csv_bytes = canonical_csv(pred)
    csv_path = ARCHIVE / f"R{rodada:02d}.csv"
    created = escrever_imutavel(csv_path, csv_bytes)

    source_files = [folder / "jogadores.json", folder / "partidas.json", DATA, BACKTEST]
    manifest_payload = {
        "temporada": 2026,
        "rodada": rodada,
        "gerado_em_utc": datetime.now(timezone.utc).isoformat(),
        "status_mercado": resumo.get("statusMercado"),
        "protocolo": "previsão de R usa exclusivamente resultados < R; contexto corrente permitido apenas se conhecido antes dos jogos; arquivo é imutável após primeiro lock",
        "jogadores_previstos": int(len(pred)),
        "alpha_v3s": alpha,
        "alpha_rf_direto": 1 - alpha,
        "mae_historico_alpha": alpha_scores,
        "csv": str(csv_path.relative_to(ROOT)),
        "csv_sha256": sha256_bytes(csv_bytes),
        "fontes_sha256": {
            str(p.relative_to(ROOT)): sha256_bytes(p.read_bytes()) for p in source_files if p.exists()
        },
        "selecoes_modelos": selections,
    }
    manifest_path = ARCHIVE / f"R{rodada:02d}.manifest.json"
    manifest_bytes = json.dumps(manifest_payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    if manifest_path.exists():
        # O timestamp não pode transformar uma rerun idêntica em mutação. Valida o CSV lockado e preserva o manifest original.
        existing = load(manifest_path)
        if existing.get("csv_sha256") != manifest_payload["csv_sha256"]:
            raise SystemExit("MANIFEST IMUTÁVEL: hash da previsão divergiu do lock existente")
    else:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_bytes(manifest_bytes)

    print(
        f"Previsão pré-rodada R{rodada:02d}: {len(pred)} jogadores; "
        f"V3-H alpha V3-S={alpha:.2f}; {'LOCK CRIADO' if created else 'LOCK JÁ EXISTIA E É IDÊNTICO'}"
    )


if __name__ == "__main__":
    main()
