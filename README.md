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

## Roadmap concluído
1. Protocolo científico e auditoria dos scouts/regras 2026.
2. Dataset histórico anti-leakage.
3. Torneio modelo × scout × posição.
4. Campeões por scout e estabilidade.
5. Pontuação V3 Scouts e incerteza.
6. V2 × V3 Scouts × V3 híbrida.
7. Ablation tests contextuais e posicionais.
8. Site laboratório e previsto × real.
9. Automação pré/pós-rodada e locks imutáveis.
10. Estudo descritivo Top 25 Nacional reconstruído historicamente e isolado do treino.

## Consolidação científica
- Dataset validado com 6.023 observações, 597 jogadores e zero violações temporais detectadas nas auditorias.
- Reconstrução da pontuação oficial a partir dos scouts validada sem erro de regra.
- Campeonato amplo de modelos executado por scout e posição, incluindo baselines, EWMA, regressões, famílias de contagem, shrinkage/Bayes e árvores/boosting quando tecnicamente viáveis.
- A arquitetura híbrida V3 mostrou melhora consistente sobre a V3 Scouts pura no conjunto comparável, mas os challengers não apresentaram evidência estatística suficiente, após correção por múltiplas comparações, para justificar promoção automática sobre a V2 oficial.
- CatBoost nested apresentou a melhor MAE numérica entre os challengers comparados à V2, porém sem gate estatístico suficiente para promoção.
- Contexto de mando + força do adversário apresentou sinal favorável; demais fatores permanecem condicionados à evidência de ablação.
- Hipóteses posicionais foram testadas sem pesos manuais; somente sinais validados devem ser usados futuramente.
- Calendário externo, clima, mudança de técnico e demais fatores não são promovidos sem cobertura e evidência prospectiva suficientes.
- O estudo Top 25 Nacional foi fechado como camada descritiva/estratégica, sem contaminar treino, pesos ou validação.

## Decisão
O laboratório científico Scouts V3 está **encerrado como fase de pesquisa**. Nenhuma alteração foi promovida para `cartola-estatistico` V2 de produção.

O próximo passo é alinhar o **site V3 de produto**, escolhendo quais componentes cientificamente validados serão expostos na interface e como transformar previsão, risco, confiança, capitão, banco, Reserva de Luxo e orçamento em uma experiência simples para o usuário.
