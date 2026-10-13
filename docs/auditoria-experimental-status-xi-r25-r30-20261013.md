# Auditoria experimental R25-R30 (13/10/2026)

Leitura independente de 18 arquivos de previsoes e pontuacoes versionados na main 4593f535. Sem mudancas no site ou motor.

R25-R29: 3006 previsoes pareadas; 1011 provaveis, dos quais 889 pontuaram (87,93%); entre 1995 nao provaveis, 630 pontuaram (31,58%). Probabilidades uniformes 95%/45% nao estao calibradas.

Baseline progressivo Beta(1,1) por status, treinado apenas com resultados anteriores: Brier R26-R29 caiu de 0,198883 para 0,186882 (6,03%); R30 de 0,193648 para 0,185343 (4,29%). Nenhum dado da rodada-alvo foi usado no ajuste.

Comparacao exploratoria de XI fixo 4-3-3, status 7, ate 3 por clube, capitao 1,5x, sem tecnico, banco ou orcamento: media real R25-R29 V3S 67,85; V3H 68,13; CatBoost 59,86; mistura 50/50 67,77. Na R30: 57,45; 51,25; 64,55; 46,75, respectivamente. Nao sao times oficiais e nao provam superioridade.

MAE geral R25-R29: V3S 3,0147; V3H 3,0372; CatBoost 2,2429. MAE apenas status provavel: V3S 3,4316; V3H 3,3041; CatBoost 3,4128.

Pendencias: snapshots historicos pre-mercado, precos, tecnico, banco, Reserva de Luxo, comparacao prospectiva de times completos e V2. R1 nao projetavel sem baseline. Nenhuma promocao cientifica autorizada.
