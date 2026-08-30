#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "reports" / "backtest-v3s-catboost-nested.json"
OUT = ROOT / "data" / "reports" / "resumo-catboost-nested.json"


def main():
    data = json.loads(SRC.read_text(encoding="utf-8"))
    geral = data.get("geral", {})
    cat = geral.get("v3s_catboost_nested", {})
    core = geral.get("v3s_nested_core", {})
    v3h = geral.get("v3h_atual", {})
    boot_core = data.get("bootstrap_catboost_vs_core", {})
    boot_v3h = data.get("bootstrap_catboost_vs_v3h_atual", {})

    cat_mae = float(cat.get("mae", 999))
    cat_rmse = float(cat.get("rmse", 999))
    cat_bias = float(cat.get("bias", 999))
    v3h_mae = float(v3h.get("mae", 999))
    v3h_rmse = float(v3h.get("rmse", 999))

    guardrails = {
        "mae_melhor_que_v3h": cat_mae < v3h_mae,
        "rmse_nao_piora_mais_5pct": cat_rmse <= v3h_rmse * 1.05,
        "bias_absoluto_ate_0_50": abs(cat_bias) <= 0.50,
    }
    guardrails["aprovado_para_integracao"] = all(guardrails.values())

    por_posicao = {}
    for pos, vals in data.get("por_posicao", {}).items():
        c = vals.get("v3s_catboost_nested", {})
        h = vals.get("v3h_atual", {})
        por_posicao[pos] = {
            "catboost_mae": c.get("mae"),
            "catboost_rmse": c.get("rmse"),
            "catboost_bias": c.get("bias"),
            "v3h_mae": h.get("mae"),
            "delta_mae_catboost_menos_v3h": round(float(c.get("mae", 0)) - float(h.get("mae", 0)), 6),
        }

    payload = {
        "protocolo": data.get("protocolo"),
        "linhas": data.get("linhas"),
        "rodadas": data.get("rodadas"),
        "geral": geral,
        "delta_vs_v3h": {
            "mae": round(cat_mae - v3h_mae, 6),
            "rmse": round(cat_rmse - v3h_rmse, 6),
        },
        "bootstrap_vs_core": boot_core,
        "bootstrap_vs_v3h": boot_v3h,
        "selecoes_modelos": data.get("selecoes_modelos", {}),
        "por_posicao": por_posicao,
        "guardrails": guardrails,
        "decisao": (
            "NAO_INTEGRAR_AINDA" if not guardrails["aprovado_para_integracao"]
            else "ELEGIVEL_PARA_TESTE_DE_INTEGRACAO"
        ),
        "motivo": (
            "MAE melhor, mas RMSE/bias violam guardrails; investigar calibração e caudas antes de qualquer promoção."
            if not guardrails["aprovado_para_integracao"] else
            "Passou guardrails básicos; ainda requer validação prospectiva."
        ),
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
