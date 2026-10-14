# Auditoria temporal independente — rodadas 2 a 8 (14/10/2026, 01h45 BRT)

**Escopo:** somente diagnóstico. `main`, `site/optimizer.js`, V2 e motor científico não foram modificados. Relacionado à issue #2.

## Evidência reproduzida diretamente do GitHub

Foram lidos **16 arquivos JSON reais** de `data/raw/rodada-01` a `rodada-08` (partidas e jogadores), no commit-base `4593f5355c9e1c2fb7db877d7eb25980bf98d208`. O cálculo replica as features de clube do `scripts/construir_dataset.py`: últimos 20 placares, média dos últimos 5, EWMA com alpha 0,45, clube e adversário. Reconstrói a elegibilidade pelo histórico prévio do atleta. Compara (A) histórico em ordem numérica das rodadas, conforme código atual, e (B) histórico que ignora placares de jogos ocorridos após o início do primeiro jogo **válido** da rodada-alvo.

| Rodada | Linhas elegíveis | Linhas com diferença em features de clube/adversário | Candidatos com diferença |
|---|---:|---:|---:|
| R2 | 231 | 0 | 0 |
| R3 | 248 | 51 | 63 |
| R4 | 182 | 0 | 0 |
| R5 | 227 | 81 | 96 |
| **R6** | **290** | **170** | **189** |
| **R7** | **304** | **211** | **221** |
| **R8** | **305** | **182** | **189** |
| **Total R2–R8** | **1.787** | **695 (38,89%)** | — |

A auditoria anterior de R3–R5 (132 linhas alteradas) foi reproduzida exatamente. O avanço desta execução são **563 linhas adicionais com diferenças efetivas em R6–R8**, em **899 linhas elegíveis**. As contagens de elegíveis coincidem com o `data/derived/dataset-meta.json` para todas as sete rodadas.

**Cinco partidas históricas com placar conhecido no arquivo, mas data posterior ao corte de alguma rodada projetada:** R2/346262 (19/02), R4/346349 (17/07), R4/346337 (23/07), R4/346335 (02/09) e R5/346408 (29/03). Esses resultados são incorporados pelo construtor original ao avançar por número de rodada, mesmo quando o jogo ainda não havia acontecido na data-alvo. A diferença persiste em rodadas posteriores.

## Testes e limites

Também foram reexecutadas **32 verificações unitárias sintéticas**, 32 aprovadas (quatro suítes locais: contaminação acumulada, partidas inválidas, coorte e status walk-forward). Os 16 arquivos reais foram auditados separadamente; os testes sintéticos não substituem benchmarks de modelos.

O corte adotado (início do primeiro jogo válido) é **permissivo**: o mercado normalmente fecha antes. Portanto, esta auditoria identifica diferenças sob um corte temporal tardio, **não certifica** a disponibilidade real dos dados no fechamento do mercado. A coorte histórica de jogadores R2–R8 ainda não possui snapshots pré-mercado comprovados. Os 695 casos são **linhas cujas features diferem**, não 695 previsões comprovadamente erradas nem um impacto já medido no MAE.

R1 continua não projetável sem baseline pré-temporada comprovado. R21 e R30 não são promovidas à certificação. Nenhum treino novo, benchmark V2, escalação completa, workflow ou deploy foi executado nesta atualização.

## Próximos passos

1. Estender a reconstrução de features até R29, mantendo registro de disponibilidade temporal de cada placar e a integridade dos IDs.
2. Gerar dataset experimental isolado, sem sobrescrever o dataset ou motor em produção.
3. Retreinar e selecionar modelos exclusivamente com informações anteriores à rodada avaliada; repetir baselines versus V2 e alternativas.
4. Certificar universo pré-mercado e pontuação real de escalações completas (orçamento, formação, técnico, capitão 1,5x, banco e Reserva de Luxo). Não promover modelo sem ganho reproduzível fora da amostra.

**GitHub:** documento em branch experimental, sem alteração em `main`.