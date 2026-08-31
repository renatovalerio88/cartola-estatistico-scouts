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


def partidas_lista(path: Path):
    if not path.exists():
        return []
    raw = load(path)
    return raw.get("partidas", raw if isinstance(raw, list) else [])


def pontuados_map(path: Path):
    raw = load(path)
    atletas = raw.get("atletas", raw if isinstance(raw, dict) else {})
    return atletas if isinstance(atletas, dict) else {}


def rodada_resolvida(partidas, pontuados):
    if not pontuados or not partidas:
        return False
    validas = [p for p in partidas if isinstance(p, dict)]
    if not validas:
        return False
    return all(
        p.get("placar_oficial_mandante") is not None
        and p.get("placar_oficial_visitante") is not None
        for p in validas
    )


def main():
    df = pd.read_csv(DATA)
    por_rodada = []
    universo_total = 0
    entraram_total = 0
    pos_total = Counter()
    rodadas_nao_resolvidas = []

    for folder in sorted(RAW.glob("rodada-*")):
        jogadores_path = folder / "jogadores.json"
        pontuados_path = folder / "pontuados.json"
        if not jogadores_path.exists() or not pontuados_path.exists():
            continue
        rodada = int(folder.name.split("-")[-1])
        pontuados = pontuados_map(pontuados_path)
        partidas = partidas_lista(folder / "partidas.json")
        resolvida = rodada_resolvida(partidas, pontuados)
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
            if resolvida:
                p = pontuados.get(str(aid), pontuados.get(aid))
                if isinstance(p, dict) and bool(p.get("entrou_em_campo", p.get("entrouEmCampo", False))):
                    entraram += 1

        linhas = int((df.rodada == rodada).sum()) if len(df) else 0
        if resolvida:
            universo_total += len(universo)
            entraram_total += entraram
            pos_total.update(posicoes)
        else:
            rodadas_nao_resolvidas.append(rodada)

        por_rodada.append({
            "rodada": rodada,
            "resolvida": resolvida,
            "universo_jogadores": len(universo),
            "entraram_em_campo": entraram if resolvida else None,
            "nao_entraram": (len(universo) - entraram) if resolvida else None,
            "linhas_dataset": linhas,
            "por_posicao": dict(posicoes),
            "regra": None if resolvida else "fora do treino/validação até a rodada ter targets finais observáveis",
        })

    targets_zero = int((df["target_entrou"] == 0).sum()) if "target_entrou" in df else None
    targets_um = int((df["target_entrou"] == 1).sum()) if "target_entrou" in df else None
    cobertura_nao_entrantes = bool(targets_zero and targets_zero > 0)
    features_participacao = [c for c in ["historico_atuacoes", "entrou_media3", "entrou_media5", "entrou_ewma", "rodadas_desde_atuou"] if c in df.columns]
    unresolved_in_dataset = sorted(set(int(x) for x in df.rodada.unique()).intersection(rodadas_nao_resolvidas)) if len(df) else []

    aprovado = cobertura_nao_entrantes and len(features_participacao) == 5 and not unresolved_in_dataset
    payload = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "status": "APROVADA" if aprovado else "REPROVADA",
        "objetivo": "Garantir que treino/validação usem todos os jogadores válidos das rodadas resolvidas, não somente quem entrou em campo, sem fabricar zeros para rodadas futuras/em andamento.",
        "dataset_linhas": int(len(df)),
        "dataset_jogadores_unicos": int(df.atleta_id.nunique()) if len(df) else 0,
        "targets_entrou": targets_um,
        "targets_nao_entrou": targets_zero,
        "taxa_nao_entrou_pct": round(100 * targets_zero / len(df), 2) if len(df) and targets_zero is not None else None,
        "features_participacao_so_passado": features_participacao,
        "rodadas_nao_resolvidas_excluidas": rodadas_nao_resolvidas,
        "rodadas_nao_resolvidas_presentes_no_dataset": unresolved_in_dataset,
        "universo_total_observacoes_brutas_resolvidas": universo_total,
        "atuacoes_total_brutas_resolvidas": entraram_total,
        "por_posicao_bruto_resolvido": dict(pos_total),
        "por_rodada": por_rodada,
        "regra": "Universo de treino = GOL/LAT/ZAG/MEI/ATA presentes em jogadores.json de rodadas resolvidas. Jogador válido que não atuou em uma rodada resolvida recebe target_entrou=0 e target_pontos/scouts=0. Rodada futura/em andamento não gera target e não entra no dataset até possuir pontuados e placares finais.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"Universo amostral: {payload['status']} | {len(df)} linhas | "
        f"atuaram={targets_um} | não atuaram={targets_zero} | "
        f"não atuação={payload['taxa_nao_entrou_pct']}% | "
        f"rodadas abertas excluídas={rodadas_nao_resolvidas}"
    )
    if payload["status"] != "APROVADA":
        raise SystemExit("Dataset não cobre adequadamente o universo resolvido ou contém rodada não resolvida.")


if __name__ == "__main__":
    main()
