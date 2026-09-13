#!/usr/bin/env python3
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'site'/'dados.json'
DST=ROOT/'site'/'dados-lite.json'

CORE={
    'produto',
    'explicabilidade_pre_rodada',
    'avaliacao_prospectiva_imutavel',
    'backtest_time_sugerido_walk_forward',
}
MAX_SMALL=350_000


def encoded_size(value):
    return len(json.dumps(value,ensure_ascii=False,separators=(',',':')).encode('utf-8'))


def main():
    data=json.loads(SRC.read_text(encoding='utf-8'))
    out={}
    kept=[]
    dropped=[]
    for key,value in data.items():
        size=encoded_size(value)
        if key in CORE or size<=MAX_SMALL:
            out[key]=value
            kept.append((key,size))
        else:
            dropped.append((key,size))
    DST.write_text(json.dumps(out,ensure_ascii=False,separators=(',',':'),allow_nan=False),encoding='utf-8')
    print('Payload original:',SRC.stat().st_size,'bytes')
    print('Payload leve:',DST.stat().st_size,'bytes')
    print('Mantidos:',', '.join(k for k,_ in kept))
    print('Omitidos do frontend:',', '.join(k for k,_ in dropped))
    if 'produto' not in out or not out.get('produto',{}).get('jogadores'):
        raise SystemExit('Payload leve invalido: produto.jogadores ausente')

if __name__=='__main__':
    main()
