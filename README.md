# Cartola Estatístico Scouts — V3

Laboratório científico independente da V2 de produção para previsão explicável do Cartola FC por scouts esperados.

## Objetivo
Modelar scouts esperados antes da rodada, reconstruir a pontuação pelas regras oficiais do Cartola e comparar em walk-forward sem vazamento de futuro: V2 direta, V3 Scouts e V3 híbrida.

## Regras científicas
- V2 de produção permanece intocada.
- Toda previsão usa somente informação disponível antes da rodada.
- Snapshots pré-rodada são imutáveis.
- Todos os jogadores historicamente elegíveis entram em treino e validação.
- Modelos competem por scout e posição; vencedores não são escolhidos antecipadamente.
- Titularidade/minutos, adversário, mando, calendário/desgaste, técnico, clima e demais fatores entram um de cada vez e precisam provar ganho por ablação.
- Nenhum scout é inventado para justificar projeção.
- Promoção depende de evidência out-of-sample.

## Roadmap
1. Protocolo científico e auditoria dos scouts/regras 2026.
2. Dataset histórico anti-leakage.
3. Torneio modelo × scout × posição.
4. Campeões por scout e estabilidade.
5. Pontuação V3 Scouts e incerteza.
6. V2 × V3 Scouts × V3 híbrida.
7. Ablation tests contextuais.
8. Site laboratório e previsto × real.
9. Automação pré/pós-rodada.

Status: laboratório iniciado. Nenhum resultado científico será declarado antes da validação correspondente.
