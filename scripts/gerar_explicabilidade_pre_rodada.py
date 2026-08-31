#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.backtest_v3s_nested import POSITIONS, SCOUT_WEIGHTS, choose_model, fit_predict
from scripts.gerar_previsao_pre_rodada import montar_frame_atual

RAW = ROOT / "data" / "raw"
DATA = ROOT / "data" / "derived" / "dataset-walk-forward.csv"
ARCHIVE = ROOT / "predictions" / "pre_round" / "2026"
REPORT = ROOT / "data" / "reports" / "explicabilidade-pre-rodada.json"

SCOUT_LABELS = {
    "G": "gol",
    "A": "assistência",
    "FT": "finalização na trave",
    "FD": "finalização defendida",
    "FF": "finalização para fora",
    "FS": "falta sofrida",
    "DS": "desarme",
    "SG": "saldo de gol",
    "DE": "defesa",
    "DP": "defesa de pênalti",
    "PS": "pênalti sofrido",
    "FC": "falta cometida",
    "GC": "gol contra",
    "CA": "cartão amarelo",
    "CV": "cartão vermelho",
    "PC": "pênalti cometido",
    "PP": "pênalti perdido",
    "GS": "gol sofrido",
    "I": "impedimento",
}


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_bytes(data: bytes):
    return hashlib.sha256(data).hexdigest()


def sha256(path: Path):
    return sha256_bytes(path.read_bytes())


def detectar_lock_atual():
    locks = []
    for p in ARCHIVE.glob("R??.manifest.json"):
        if ".explicabilidade." in p.name:
            continue
        try:
            rodada = int(p.name[1:3])
        except ValueError:
            continue
        csv = ARCHIVE / f"R{rodada:02d}.csv"
        if csv.exists():
            locks.append((rodada, csv, p))
    return max(locks, default=None, key=lambda x: x[0])


def fontes_originais_intactas(manifest):
    divergencias = []
    for rel, esperado in (manifest.get("fontes_sha256") or {}).items():
        path = ROOT / rel
        if not path.exists():
            divergencias.append({"arquivo": rel, "motivo": "ausente"})
            continue
        atual = sha256(path)
        if atual != esperado:
            divergencias.append(
                {"arquivo": rel, "motivo": "hash_divergente", "esperado": esperado, "atual": atual}
            )
    return divergencias


def reason(top_pos, top_neg):
    positivos = [SCOUT_LABELS.get(x["scout"], x["scout"]) for x in top_pos if x["contribuicao_pontos"] > 0.04]
    negativos = [SCOUT_LABELS.get(x["scout"], x["scout"]) for x in top_neg if x["contribuicao_pontos"] < -0.04]
    if positivos:
        txt = "Projeção sustentada principalmente por " + ", ".join(positivos[:2])
    else:
        txt = "Projeção sem um scout positivo dominante"
    if negativos:
        txt += "; principal desconto esperado: " + negativos[0]
    return txt + "."


def escrever_relatorio(payload):
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    lock = detectar_lock_atual()
    if not lock:
        escrever_relatorio({"status": "AGUARDANDO_LOCK", "aprovado": True, "mensagem": "Nenhuma previsão pré-rodada arquivada."})
        print("Explicabilidade: aguardando primeiro lock pré-rodada.")
        return

    rodada, csv_path, manifest_path = lock
    manifest = load(manifest_path)
    csv_hash = sha256(csv_path)
    if csv_hash != manifest.get("csv_sha256"):
        raise SystemExit(f"R{rodada:02d}: CSV imutável não confere com o manifesto original")

    explain_path = ARCHIVE / f"R{rodada:02d}.explicabilidade.json"
    explain_manifest_path = ARCHIVE / f"R{rodada:02d}.explicabilidade.manifest.json"
    if explain_path.exists() or explain_manifest_path.exists():
        if not explain_path.exists() or not explain_manifest_path.exists():
            raise SystemExit(f"R{rodada:02d}: sidecar de explicabilidade inconsistente")
        em = load(explain_manifest_path)
        atual = sha256(explain_path)
        if atual != em.get("explicabilidade_sha256") or em.get("csv_sha256") != csv_hash:
            raise SystemExit(f"R{rodada:02d}: sidecar imutável de explicabilidade corrompido")
        escrever_relatorio(
            {
                "status": "APROVADO",
                "aprovado": True,
                "rodada": rodada,
                "jogadores": em.get("jogadores"),
                "csv_sha256": csv_hash,
                "explicabilidade_sha256": atual,
                "mensagem": "Sidecar existente validado; nenhuma recomputação ou sobrescrita foi feita.",
            }
        )
        print(f"Explicabilidade R{rodada:02d}: sidecar imutável já existe e foi validado.")
        return

    divergencias = fontes_originais_intactas(manifest)
    if divergencias:
        escrever_relatorio(
            {
                "status": "LEGADO_SEM_DECOMPOSICAO",
                "aprovado": True,
                "rodada": rodada,
                "csv_sha256": csv_hash,
                "divergencias_fontes": divergencias,
                "mensagem": "O lock é válido, mas as fontes já mudaram. A decomposição não será reconstruída retroativamente para evitar explicação pós-hoc.",
            }
        )
        print(f"Explicabilidade R{rodada:02d}: lock legado preservado; fontes mudaram e não haverá reconstrução pós-hoc.")
        return

    folder = RAW / f"rodada-{rodada:02d}"
    current, meta = montar_frame_atual(rodada, folder)
    if current.empty:
        raise SystemExit(f"R{rodada:02d}: sem frame pré-rodada para explicabilidade")

    dataset = pd.read_csv(DATA)
    dataset = dataset[(dataset.rodada < rodada) & dataset.posicao.isin(POSITIONS)].copy()
    n = len(current)
    scout_predictions = {s: np.zeros(n, float) for s in SCOUT_WEIGHTS}
    scout_models = {}

    for pos in POSITIONS:
        mask = current.posicao.eq(pos)
        idx = np.flatnonzero(mask.to_numpy())
        test = current[mask]
        history = dataset[dataset.posicao.eq(pos)]
        if test.empty:
            continue
        for scout in SCOUT_WEIGHTS:
            if f"target_{scout}" not in history.columns:
                continue
            winner, inner_scores = choose_model(history, scout, rodada)
            try:
                values = np.asarray(fit_predict(winner, history, test, scout), dtype=float)
            except Exception:
                values = test[f"{scout}_ewma"].fillna(0).to_numpy(float)
                winner = "ewma_fallback"
            scout_predictions[scout][idx] = values
            scout_models[f"{pos}:{scout}"] = {
                "modelo": winner,
                "mae_validacao_passada": inner_scores.get(winner),
            }

    locked = pd.read_csv(csv_path)
    by_id = locked.set_index("atleta_id")
    players = []
    max_reconciliation_error = 0.0
    max_lock_error = 0.0

    for i, m in meta.reset_index(drop=True).iterrows():
        aid = int(m.atleta_id)
        if aid not in by_id.index:
            continue
        comps = []
        total = 0.0
        for scout, weight in SCOUT_WEIGHTS.items():
            esperado = float(scout_predictions[scout][i])
            contrib = esperado * float(weight)
            total += contrib
            comps.append(
                {
                    "scout": scout,
                    "nome": SCOUT_LABELS.get(scout, scout),
                    "esperado": round(esperado, 6),
                    "peso_cartola": float(weight),
                    "contribuicao_pontos": round(contrib, 6),
                    "modelo": scout_models.get(f"{m.posicao}:{scout}", {}).get("modelo"),
                }
            )
        row = by_id.loc[aid]
        locked_v3s = float(row["v3s_expected_scouts"])
        max_lock_error = max(max_lock_error, abs(total - locked_v3s))
        reconciled = sum(float(x["contribuicao_pontos"]) for x in comps)
        max_reconciliation_error = max(max_reconciliation_error, abs(reconciled - locked_v3s))
        pos_sorted = sorted(comps, key=lambda x: x["contribuicao_pontos"], reverse=True)[:3]
        neg_sorted = sorted(comps, key=lambda x: x["contribuicao_pontos"])[:2]
        players.append(
            {
                "atleta_id": aid,
                "apelido": m.apelido,
                "posicao": m.posicao,
                "sigla_clube": m.sigla_clube,
                "sigla_adversario": m.sigla_adversario,
                "mando": m.mando,
                "v3s_expected_scouts": round(locked_v3s, 6),
                "v3h_hibrido": round(float(row["v3h_hibrido"]), 6),
                "alpha_v3s": round(float(row["alpha_v3s"]), 6),
                "scouts": comps,
                "principais_contribuicoes_positivas": pos_sorted,
                "principais_contribuicoes_negativas": neg_sorted,
                "justificativa": reason(pos_sorted, neg_sorted),
            }
        )

    if max_lock_error > 1e-4:
        raise SystemExit(
            f"R{rodada:02d}: recomputação de scouts não reproduz o lock V3-S; erro máximo={max_lock_error:.8f}. Sidecar recusado."
        )

    payload = {
        "schema": 1,
        "temporada": 2026,
        "rodada": rodada,
        "gerado_em_utc": datetime.now(timezone.utc).isoformat(),
        "origem_explicacao": "decomposicao_matematica_da_v3s",
        "nao_e_causal": True,
        "protocolo": "Cada contribuição é scout esperado × peso oficial. A explicação descreve a projeção V3-S e nunca entra como feature, target ou critério de seleção de modelo.",
        "csv_pre_rodada": str(csv_path.relative_to(ROOT)),
        "csv_sha256": csv_hash,
        "jogadores": players,
        "auditoria_reconciliacao": {
            "jogadores": len(players),
            "erro_maximo_recomputado_vs_lock": max_lock_error,
            "erro_maximo_soma_componentes_vs_lock": max_reconciliation_error,
            "tolerancia": 1e-4,
        },
    }
    data = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    explain_path.write_bytes(data)
    eh = sha256_bytes(data)
    em = {
        "schema": 1,
        "temporada": 2026,
        "rodada": rodada,
        "gerado_em_utc": datetime.now(timezone.utc).isoformat(),
        "csv": str(csv_path.relative_to(ROOT)),
        "csv_sha256": csv_hash,
        "explicabilidade": str(explain_path.relative_to(ROOT)),
        "explicabilidade_sha256": eh,
        "jogadores": len(players),
        "fontes_sha256": manifest.get("fontes_sha256", {}),
    }
    explain_manifest_path.write_text(json.dumps(em, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    escrever_relatorio(
        {
            "status": "APROVADO",
            "aprovado": True,
            "rodada": rodada,
            "jogadores": len(players),
            "csv_sha256": csv_hash,
            "explicabilidade_sha256": eh,
            "erro_maximo_recomputado_vs_lock": max_lock_error,
            "erro_maximo_reconciliacao": max_reconciliation_error,
        }
    )
    print(f"Explicabilidade R{rodada:02d}: {len(players)} jogadores; sidecar imutável criado e reconciliado com o lock.")


if __name__ == "__main__":
    main()
