# Protocolo científico V3

## Unidade de validação
A previsão da rodada R é gerada exclusivamente com observações das rodadas anteriores a R. O alvo real da rodada R só é anexado após a materialização das features. A divisão de treino/teste é temporal por rodada, nunca aleatória.

## Universo
Todos os atletas que entraram em campo e possuem histórico anterior válido participam do dataset. O painel é apenas uma visualização; não limita treino/validação.

## Métricas
MAE é a métrica primária para scouts e pontos. RMSE, viés, cobertura e estabilidade por rodada são secundárias. Para eventos raros serão adicionadas métricas probabilísticas e de calibração no estágio seguinte.

## Campeonato
Cada combinação scout × posição é uma competição independente. Um modelo só vence com desempenho out-of-sample. Empates práticos favorecem o modelo mais simples e estável.

## Ablation
Fatores contextuais entram um bloco por vez: mando/adversário; titularidade/minutos; força de ataque/defesa; descanso e calendário paralelo; mudança de técnico; clima. Um bloco permanece somente se melhorar validação temporal de forma consistente.

## Arquiteturas finais
- V2 direta: referência externa, sem qualquer escrita no repositório V2.
- V3 Scouts: soma das expectativas de scouts conforme pesos auditados.
- V3 híbrida: combinação calibrada entre projeção direta e V3 Scouts.

## Imutabilidade
Snapshots pré-rodada futuros serão gravados em diretório separado e nunca sobrescritos após o fechamento do mercado. Correções posteriores devem gerar nova versão/auditoria, não reescrever a previsão original.
