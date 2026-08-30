#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
DATA = ROOT / "data" / "derived" / "dataset-walk-forward.csv"
OUT = ROOT / "data" / "reports" / "auditoria-vazamento-temporal.json"
SCOUTS = ["G", "A", "FT", "FD", "FF", "FS", "PS", "I", "DS", "SG", "DP", "DE", "GC", "CV", "CA", "GS", "FC", "PC", "PP"]
POS_JOGADORES = {1, 2, 3, 4, 5}
TOL = 1e-7


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def mean(values):
    values = list(values)
    return float(np.mean(values)) if values else 0.0


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


def close(a, b):
    return abs(float(a) - float(b)) <= TOL


def jogadores_lista(path: Path):
    raw = load(path)
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        return raw.get("atletas", raw.get("jogadores", []))
    return []


def pontuados_map(path: Path):
    raw = load(path)
    atletas = raw.get("atletas", raw if isinstance(raw, dict) else {})
    out = {}
    for aid_raw, atleta in atletas.items():
        if not isinstance(atleta, dict):
            continue
        try:
            out[int(aid_raw)] = atleta
        except (TypeError, ValueError):
            pass
    return out


def jid(j):
    try:
        return int(j.get("id", j.get("atleta_id")))
    except (TypeError, ValueError):
        return None


def posid(j):
    try:
        return int(j.get("posicaoId", j.get("posicao_id", 0)) or 0)
    except (TypeError, ValueError):
        return 0


def target(pontuado):
    if not isinstance(pontuado, dict):
        return 0.0, 0, {}
    entrou = bool(pontuado.get("entrou_em_campo", pontuado.get("entrouEmCampo", False)))
    if not entrou:
        return 0.0, 0, {}
    pontos = float(pontuado.get("pontuacao", pontuado.get("pontuacaoReal", 0)) or 0)
    scouts = pontuado.get("scout", pontuado.get("scouts", {})) or {}
    return pontos, 1, scouts


def main():
    df = pd.read_csv(DATA)
    indexed = {(int(r.rodada), int(r.atleta_id)): r for _, r in df.iterrows()}
    history = defaultdict(lambda: {
        "pontos": deque(maxlen=20),
        "entered": deque(maxlen=20),
        "scouts": defaultdict(lambda: deque(maxlen=20)),
    })
    violations = []
    checks = 0
    rows_checked = 0

    for folder in sorted(RAW.glob("rodada-*")):
        jogadores_path = folder / "jogadores.json"
        pontuados_path = folder / "pontuados.json"
        if not jogadores_path.exists() or not pontuados_path.exists():
            continue
        rodada = int(folder.name.split("-")[-1])
        pontuados = pontuados_map(pontuados_path)

        candidatos = []
        for j in jogadores_lista(jogadores_path):
            if not isinstance(j, dict):
                continue
            aid = jid(j)
            if aid is None or posid(j) not in POS_JOGADORES:
                continue
            candidatos.append(aid)

        for aid in candidatos:
            h = history[aid]
            pontos_atual, entrou_atual, scouts_atual = target(pontuados.get(aid))
            key = (rodada, aid)

            if len(h["pontos"]) >= 1:
                row = indexed.get(key)
                if row is None:
                    violations.append({"rodada": rodada, "atleta_id": aid, "tipo": "linha_esperada_ausente"})
                else:
                    rows_checked += 1
                    entered_vals = list(h["entered"])
                    desde_atuou = 20
                    for distancia, flag in enumerate(reversed(entered_vals), start=1):
                        if flag:
                            desde_atuou = distancia - 1
                            break
                    expected = {
                        "historico_jogos": len(h["pontos"]),
                        "historico_atuacoes": int(sum(entered_vals)),
                        "taxa_atuacao_historica": float(sum(entered_vals)) / len(entered_vals),
                        "entrou_media2": mean(entered_vals[-2:]),
                        "entrou_media3": mean(entered_vals[-3:]),
                        "entrou_media5": mean(entered_vals[-5:]),
                        "entrou_media10": mean(entered_vals[-10:]),
                        "entrou_ewma": ewma(entered_vals),
                        "rodadas_desde_atuou": desde_atuou,
                        "sequencia_atuacoes": streak(entered_vals, 1),
                        "sequencia_ausencias": streak(entered_vals, 0),
                        "pontos_media3": mean(list(h["pontos"])[-3:]),
                        "pontos_media5": mean(list(h["pontos"])[-5:]),
                        "pontos_ewma": ewma(list(h["pontos"])),
                        "target_entrou": entrou_atual,
                        "target_pontos": pontos_atual,
                    }
                    for scout in SCOUTS:
                        vals = list(h["scouts"][scout])
                        expected[f"{scout}_media3"] = mean(vals[-3:])
                        expected[f"{scout}_media5"] = mean(vals[-5:])
                        expected[f"{scout}_ewma"] = ewma(vals)
                        expected[f"target_{scout}"] = float(scouts_atual.get(scout, 0) or 0) if entrou_atual else 0.0

                    for col, exp in expected.items():
                        checks += 1
                        if col not in row.index:
                            violations.append({"rodada": rodada, "atleta_id": aid, "tipo": "coluna_ausente", "coluna": col})
                            continue
                        got = row[col]
                        if pd.isna(got) or not close(got, exp):
                            violations.append({
                                "rodada": rodada,
                                "atleta_id": aid,
                                "tipo": "feature_ou_target_divergente",
                                "coluna": col,
                                "esperado": round(float(exp), 10),
                                "encontrado": None if pd.isna(got) else round(float(got), 10),
                            })

            h["pontos"].append(pontos_atual)
            h["entered"].append(entrou_atual)
            for scout in SCOUTS:
                h["scouts"][scout].append(float(scouts_atual.get(scout, 0) or 0) if entrou_atual else 0.0)

            if len(violations) >= 100:
                break
        if len(violations) >= 100:
            break

    expected_keys = set(indexed)
    payload = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "status": "APROVADA" if not violations and rows_checked == len(expected_keys) else "REPROVADA",
        "regra_inviolavel": "Para projetar a rodada R, toda feature, treino, seleção e calibração deve usar somente informações de rodadas < R. Targets de R podem existir apenas como rótulo de avaliação.",
        "universo": "Jogadores válidos do jogadores.json, inclusive quem não entrou; ausência de atuação em R vira target 0, nunca feature de R.",
        "linhas_dataset": int(len(df)),
        "linhas_auditadas": int(rows_checked),
        "checks_features_targets": int(checks),
        "violacoes": violations,
        "violacoes_total_amostradas": len(violations),
        "metodo": "Reconstrução cronológica a partir de jogadores.json + pontuados.json; cada linha R é conferida antes de incorporar participação, pontos e scouts de R ao histórico. Inclui auditoria explícita de taxas, janelas e sequências de participação.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Auditoria temporal: {payload['status']} | {rows_checked}/{len(df)} linhas | {checks} checks | {len(violations)} violações")
    if payload["status"] != "APROVADA":
        raise SystemExit("Vazamento temporal ou inconsistência cronológica detectada; pipeline interrompido.")


if __name__ == "__main__":
    main()
