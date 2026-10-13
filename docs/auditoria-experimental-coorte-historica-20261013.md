# Auditoria experimental da coorte histórica — 13/10/2026

**P0 — Risco de viés de seleção na lista de atletas do walk-forward.** Somente leitura dos dados de produção; V2, `site/optimizer.js` e o motor científico permanecem intocados.

## Resultados reproduzidos

Fonte: `data/reports/auditoria-universo-jogadores.json`, commit de referência `4593f5355c`.

| Coorte de jogadores de campo | Rodadas resolvidas | Atletas-rodada | Entraram | Não entraram | % não entrou |
|---|---:|---:|---:|---:|---:|
| R1–R29, exceto R21 | 28 | 8.462 | 8.434 | 28 | **0,33%** |
| R30 | 1 | 767 | 320 | 447 | **58,28%** |

Verificação independente por IDs em `data/raw/rodada-XX/{jogadores,pontuados}.json`:

| Rodada | Atletas de campo em jogadores.json | Também em pontuados.json | Preço presente | Status presente |
|---|---:|---:|---:|---:|
| R25 | 312 | 312 | 0 | 0 |
| R29 | 314 | 314 | 0 | 0 |
| R30 | 767 | 320 | 767 | 767 |

Os dados R25/R29 parecem conter essencialmente os atletas apurados depois dos jogos; R30 contém também atletas que não pontuaram. A diferença **não prova a origem exata dos dados**, mas torna inadequado chamar a coorte antiga de mercado elegível completo.

## Risco metodológico

`scripts/construir_dataset.py` forma os candidatos de R usando o próprio `jogadores.json` de R. Se esse arquivo foi construído depois da rodada, a inclusão do jogador já pode revelar quem participou — **vazamento por seleção da amostra**, mesmo quando os valores das features foram construídos exclusivamente com dados de rodadas anteriores.

O relatório `auditoria-vazamento-temporal.json` registra 770.316 verificações e zero violações, mas isso não certifica a data de formação do universo. O selo `APROVADA` em `scripts/auditar_universo_jogadores.py` verifica apenas presença de algum não participante, features e exclusão de rodadas abertas; **não verifica cobertura do mercado nem proveniência temporal**.

Os 8.373 registros do dataset incluem 314 não participantes no total; isso não demonstra representatividade dos ausentes nas rodadas antigas. Resultados de calibração de participação e de XI anteriores à R30 são **exploratórios**, não evidência suficiente para promoção de modelo.

## Critérios antes de monetizar ou promover modelo

1. Recuperar snapshots de atletas elegíveis **pré-fechamento**, com preço, status, fonte, timestamp e hash por rodada.
2. Separar explicitamente coorte de mercado comprovado, coorte pós-jogo e cobertura desconhecida. Não treinar ou validar probabilidade de participação como se fossem equivalentes.
3. Refazer comparações walk-forward sem vazamento também na escolha de candidatos, pesos e modelos. R1 é não projetável sem baseline pré-temporada. R21 segue excluída pelo pipeline atual; R30 tem resultados, mas ainda exige comprovação de snapshot pré-rodada.
4. Só certificar times completos quando for possível auditar orçamento, técnico, formação, capitão 1,5x, banco e Reserva de Luxo contra o universo elegível da época.

**Execução desta nota:** leitura e cruzamento aritmético dos JSONs reais, sem executar o pipeline integral nem novos workflows. Nenhum teste de navegador, deploy ou alteração científica foi feito.
