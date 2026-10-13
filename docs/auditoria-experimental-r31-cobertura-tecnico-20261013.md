# Auditoria experimental R31 — cobertura, técnico e titularidade (13/10/2026, 16h BRT)

**Escopo:** somente `renatovalerio88/cartola-estatistico-scouts`. Análise independente de arquivos já versionados na `main` em `4593f5355c9e1c2fb7db877d7eb25980bf98d208`. Nenhuma alteração no motor V2, no `site/optimizer.js` ou no site público.

## Entradas e método
- `data/raw/rodada-31/jogadores.json`: universo do mercado armazenado, 787 registros.
- `predictions/pre_round/2026/R31.csv`: 613 previsões, identificadas por `atleta_id`.
- `predictions/pre_round/2026/R31.time-sugerido.json`: 11 titulares e cinco reservas.
- Junção por identificador do atleta; `statusId=7` define *provável* segundo o snapshot do mercado. Não equivale a titular confirmado.
- Comparação de preço, status, posição e projeção entre arquivos, sem consultar resultados da própria R31.

## Cobertura e consistência verificadas
| Indicador | Resultado |
|---|---:|
| Atletas no mercado R31 | 787 |
| Previsões no CSV | 613 |
| Atletas do mercado com status 7 | 209 |
| Prováveis de campo (excluindo TEC) | 192 |
| Prováveis de campo presentes no CSV | **192/192 (100%)** |
| Técnicos prováveis | 17 |
| Técnicos com previsão no CSV | **0/17** |
| Prováveis de campo sem previsão | **0** |
| Titulares no snapshot | 11 |
| Reservas no snapshot | 5 |
| Divergências de preço, status ou posição nos 16 atletas | **0** |
| Projeções dos 16 atletas iguais à coluna `v3h_hibrido` | **16/16** |

**Interpretação:** nesta rodada prospectiva, a cobertura dos atletas de campo com status provável é integral; a lacuna do CSV para técnicos é de 17/17. Isso **não valida** cobertura pré-rodada das rodadas históricas, nem prova que os 192 jogarão.

## Titularidade e minutos não são estimativas individuais
Todos os **209 atletas com status 7** têm `titularidade=95` e `minutosEsperados=85`. Os outros **578** atletas (status 2, 3, 5 ou 6) têm `titularidade=45` e `minutosEsperados=45`.

Essa correspondência perfeita entre status e valores evidencia um mapeamento uniforme por status no snapshot, **não uma probabilidade individual calibrada**. Não usar esses números como prova de acerto na escalação.

## Pontuação do capitão e técnico
- O XI da R31 tem projeção-base **76,923531** e capitão Viveros projetado em **9,750071**.
- O campo armazenado `projecao_time_com_capitao=86,673602` soma 100% extra do capitão (2x).
- Com o bônus oficial de **50% extra** (1,5x), o XI projetado corretamente é **81,798567** (arredondado a seis casas). Diferença: **4,875035** pontos projetados.
- O snapshot não inclui técnico; portanto, não é uma escalação oficial de 12 atletas.
- Entre os 17 técnicos prováveis, **16** são compatíveis com o XI congelado sob limite de três por clube; Leonardo Jardim (FLA) excederia esse limite porque o XI já tem três atletas do FLA.
- **Exemplo puramente experimental, não previsão certificada:** incluir Marcão (FLU), média pré-rodada 7,40 em oito jogos e preço C$12,04, elevaria o custo de C$115,85 a **C$127,89** (orçamento C$200), e o total ilustrativo do XI+TEC a **89,198567**. A média histórica do técnico não foi validada como preditor e não deve ser exibida como previsão oficial.

## Certificação temporal
O snapshot declara mercado aberto e contém SHA-256 do resumo oficial, mas o campo `prova_prospectiva.coleta_oficial_em` está vazio. O resumo tem captura em 13/10/2026 às 16:58:36 UTC e o snapshot foi gerado às 17:26:39 UTC, aproximadamente 28 minutos depois. **Não certificar como prova de mercado aberto no instante do congelamento; não editar o snapshot imutável retroativamente.**

## Próxima validação
1. Construir baseline prospectivo de técnico com apenas informação pré-rodada e avaliar após o fechamento real.
2. Substituir valores uniformes de minutos/titularidade apenas após calibração temporal e prova de ganho.
3. Comparar XI+TEC+capitão+Reserva de Luxo com V2 e alternativas quando houver snapshots válidos e resultados finais.
4. Manter `optimizer.js`, V2 e motor científico protegidos até autorização e evidência quantitativa.

**Status:** auditoria de consistência do snapshot R31; **não** é backtest de pontos reais nem promoção de modelo.
