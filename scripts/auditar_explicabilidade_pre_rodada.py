#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "predictions" / "pre_round" / "2026"
REPORT = ROOT / "data" / "reports" / "auditoria-explicabilidade-pre-rodada.json"
TOL = 1e-4
PROIBIDOS = {"pontuacao_real", "pontuacao", "target", "scouts_reais", "resultado_real"}


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    manifests = sorted(ARCHIVE.glob("R??.explicabilidade.manifest.json"))
    if not manifests:
        payload = {
            "status": "AGUARDANDO_PRIMEIRO_SIDECAR",
            "aprovado": True,
            "sidecars_auditados": 0,
            "mensagem": "Locks antigos continuam válidos. A decomposição por scouts passa a ser exigida nos novos snapshots quando puder ser reproduzida exatamente sem informação pós-lock.",
        }
        REPORT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print("Auditoria de explicabilidade: aguardando primeiro sidecar; protocolo ativado.")
        return

    erros = []
    detalhes = []
    total_jogadores = 0
    for mp in manifests:
        m = load(mp)
        rodada = int(m.get("rodada") or 0)
        ep = ROOT / str(m.get("explicabilidade") or "")
        cp = ROOT / str(m.get("csv") or "")
        item = {"rodada": rodada, "manifest": str(mp.relative_to(ROOT)), "erros": []}
        if not ep.exists() or not cp.exists():
            item["erros"].append("arquivo_referenciado_ausente")
            detalhes.append(item)
            erros.extend([f"R{rodada:02d}:arquivo_referenciado_ausente"])
            continue
        if sha256(ep) != m.get("explicabilidade_sha256"):
            item["erros"].append("hash_explicabilidade_divergente")
        if sha256(cp) != m.get("csv_sha256"):
            item["erros"].append("hash_csv_divergente")
        e = load(ep)
        if e.get("origem_explicacao") != "decomposicao_matematica_da_v3s" or e.get("nao_e_causal") is not True:
            item["erros"].append("protocolo_explicacao_invalido")
        players = e.get("jogadores") or []
        total_jogadores += len(players)
        ids = []
        max_err = 0.0
        for p in players:
            ids.append(p.get("atleta_id"))
            if PROIBIDOS.intersection(p.keys()):
                item["erros"].append(f"campo_pos_rodada_proibido:{p.get('atleta_id')}")
            comps = p.get("scouts") or []
            for c in comps:
                if PROIBIDOS.intersection(c.keys()):
                    item["erros"].append(f"campo_scout_pos_rodada_proibido:{p.get('atleta_id')}")
            soma = sum(float(c.get("contribuicao_pontos") or 0) for c in comps)
            alvo = float(p.get("v3s_expected_scouts") or 0)
            max_err = max(max_err, abs(soma - alvo))
        if len(ids) != len(set(ids)):
            item["erros"].append("atleta_id_duplicado")
        if len(players) != int(m.get("jogadores") or -1):
            item["erros"].append("contagem_jogadores_divergente")
        if max_err > TOL:
            item["erros"].append(f"reconciliacao_acima_tolerancia:{max_err:.8f}")
        item["jogadores"] = len(players)
        item["erro_maximo_reconciliacao"] = max_err
        if item["erros"]:
            erros.extend([f"R{rodada:02d}:{x}" for x in item["erros"]])
        detalhes.append(item)

    payload = {
        "status": "APROVADO" if not erros else "REPROVADO",
        "aprovado": not erros,
        "sidecars_auditados": len(manifests),
        "jogadores_auditados": total_jogadores,
        "tolerancia_reconciliacao": TOL,
        "erros": erros,
        "rodadas": detalhes,
        "regra": "Explicação é somente decomposição matemática de scouts esperados × pesos oficiais, sem alvo real, scout real ou informação pós-rodada.",
    }
    REPORT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Auditoria de explicabilidade: {payload['status']} | sidecars={len(manifests)} | jogadores={total_jogadores} | erros={len(erros)}")
    if erros:
        raise SystemExit("Auditoria de explicabilidade reprovada")


if __name__ == "__main__":
    main()
