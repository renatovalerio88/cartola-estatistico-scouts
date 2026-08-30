#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
DATA = ROOT / "data" / "derived" / "dataset-walk-forward.csv"
OUT = ROOT / "data" / "reports" / "auditoria-universo-jogadores.json"
POS = {1: "GOL", 2: "LAT", 3: "ZAG", 4: "MEI", 5: "ATA"}


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


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
    return atletas if isinstance(atletas, dict) else {}


def main():
    df = pd.read_csv(DATA)
    por_rodada = []
    universo_total = 0
    entraram_total = 0
    pos_total = Counter()

    for folder in sorted(RAW.glob("rodada-*")):
        jogadores_path = folder / "jogadores.json"
        pontuados_path = folder / "pontuados.json"
        if not jogadores_path.exists() or not pontuados_path.exists():
            continue
        rodada = int(folder.name.split("-")[-1])
        pontuados = pontuados_map(pontuados_path)
        universo = []
        posicoes = Counter()
        entraram = 0

        for j in jogadores_lista(jogadores_path):
            if not isinstance(j, dict):
                continue
            try:
                aid = int(j.get("id", j.get("atleta_id")))
                pos_id = int(j.get("posicaoId", j.get("posicao_id", 0)) or 0)
            except (TypeError, ValueError):
                continue
            if pos_id not in POS:
                continue
            universo.append(aid)
            posicoes[POS[pos_id]] += 1
            p = pontuados.get(str(aid), pontuados.get(aid))
            if isinstance(p, dict) and bool(p.get("entrou_em_campo", p.get("entrouEmCampo", False))):
                entraram += 1

        linhas = int((df.rodada == rodada).sum()) if len(df) else 0
        universo_total += len(universo)
        entraram_total += entraram
        pos_total.update(posicoes)
        por_rodada.append({
            "rodada": rodada,
            "universo_jogadores": len(universo),
            "entraram_em_campo": entraram,
            "nao_entraram": len(universo) - entraram,
            "linhas_dataset": linhas,
            "por_posicao": dict(posicoes),
        })

    targets_zero = int((df["target_entrou"] == 0).sum()) if "target_entrou" in df else None
    targets_um = int((df["target_entrou"] == 1).sum()) if "target_entrou" in df else None
    cobertura_nao_entrantes = bool(targets_zero and targets_zero > 0)
    features_participacao = [c for c in ["historico_atuacoes", "entrou_media3", "entrou_media5", "entrou_ewma", "rodadas_desde_atuou"] if c in df.columns]

    payload = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "status": "APROVADA" if cobertura_nao_entrantes and len(features_participacao) == 5 else "REPROVADA",
        "objetivo": "Garantir que treino/validação não usem somente quem entrou em campo, evitando viés de seleção e permitindo aprender risco de não participação.",
        "dataset_linhas": int(len(df)),
        "dataset_jogadores_unicos": int(df.atleta_id.nunique()) if len(df) else 0,
        "targets_entrou": targets_um,
        "targets_nao_entrou": targets_zero,
        "taxa_nao_entrou_pct": round(100 * targets_zero / len(df), 2) if len(df) and targets_zero is not None else None,
        "features_participacao_so_passado": features_participacao,
        "universo_total_observacoes_brutas": universo_total,
        "atuacoes_total_brutas": entraram_total,
        "por_posicao_bruto": dict(pos_total),
        "por_rodada": por_rodada,
        "regra": "Universo = GOL/LAT/ZAG/MEI/ATA presentes em jogadores.json. Jogador válido que não atuou recebe target_entrou=0 e target_pontos/scouts=0. A informação de atuação da própria rodada nunca entra nas features.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"Universo amostral: {payload['status']} | {len(df)} linhas | "
        f"atuaram={targets_um} | não atuaram={targets_zero} | "
        f"não atuação={payload['taxa_nao_entrou_pct']}%"
    )
    if payload["status"] != "APROVADA":
        raise SystemExit("Dataset não cobre adequadamente jogadores válidos que não entraram em campo.")


if __name__ == "__main__":
    main()
