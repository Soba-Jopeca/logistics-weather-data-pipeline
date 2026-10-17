# P09-P01 — Proposta de resiliência e política de agendamento

## 1. Identificação, autorização e estado

- Projeto: Logistics Weather Data Pipeline.
- Checkpoint: CP-2026-10-13 v2.
- Identificação: AF-CPv2-P09-P01-v0.2.
- Data desta versão documental: 17/10/2026, America/Sao_Paulo.
- Proposta inicialmente apresentada em chat: 16/10/2026.
- Destino: Planeamento central e João.
- Responsável pela proposta: Airflow — Seção 4.
- Baseline operacional analisada: `770a7a1f01440bb96443b8cde645b65b8164ea86`.
- Evidência de P08-R03: `docs/22-evidencias-p08-r03-execucao-manual.md`, commit `011d01b2283ac89573aa36b23d30b350b81a79c0`.
- Estado: **P09-P01 v0.2 — REVISÃO DOCUMENTAL SUBMETIDA; diff aprovado por João para publicação exclusivamente documental**.
- Base documental desta revisão: commit `0160d54e767b52cc3699c3fef109f7a6a729cadc` (v0.1).

O Planeamento central, com ratificação expressa de João, validou o passo 08 com limitações e liberou o passo 09 exclusivamente para planeamento, diagnóstico e proposta. João autorizou expressamente a criação deste documento. Essa autorização documental não libera implementação ou execução de testes.

Passos 01–02 e 05–07 validados; 03–04 validados com ressalvas; 08 validado com limitações. Passo 09 não validado. Passos 10–11 não liberados.

A v0.1 foi publicada após autorização documental. Em novo encaminhamento, o Planeamento informou que João aprovou priorizar uma coleta diária para apoiar a decisão logística das 14h30, excluindo a cadência de duas horas do MVP. A autorização desta v0.2 limita-se à consolidação documental e exige apresentar o diff a João antes da publicação.

### 1.1 Registro das decisões e hipóteses

| Classificação | Conteúdo | Consequência |
|---|---|---|
| Direção aprovada | Uma coleta principal diária para a decisão logística das 14h30 | MVP orientado a essa finalidade, sem atualização contínua |
| Regra arquitetural aprovada | D pela data local do slot nominal em America/Sao_Paulo; janela [D 16h, D+2 00h) preservada | Não selecionar D pelo relógio de cada task |
| Restrição aprovada | Não adotar `0 */2 * * *` no MVP | Atualizações extraordinárias ficam para evolução posterior |
| Hipóteses iniciais aceitas para desenho | Coleta 13h45, corte 14h15, disponibilização pretendida 14h30 | Não são agenda ativada, deadline implementado ou SLA comprovado |
| Ainda aberto | Timetable, atraso, unicidade de slot, reação no corte, frescor, fallback e autorização T01 | Nenhum mecanismo correspondente está implementado por esta revisão |

A aprovação de uma orientação de negócio não equivale à aprovação da implementação das hipóteses operacionais.

## 2. Limites desta entrega

Esta entrega altera somente documentação. Não altera DAG, núcleo Python, testes, Compose, imagem, dependências, PostgreSQL ou contratos Raw/run/batch.

Não executa novas DAG runs, tasks, coleta meteorológica, testes operacionais de falhas, replay, clear, dag.test, tasks test, despausa ou agendamento. As consultas realizadas para elaborar a proposta limitaram-se à leitura do código aprovado e da documentação técnica.

Nenhuma instrução deste documento constitui autorização para executar os cenários descritos. Métodos e resultados abaixo são propostas e critérios futuros, não evidências de testes realizados neste gate.

## 3. Evidência de partida

P08-R03 executou `manual_cp_v2_p08_20261017_03` com ciclo 2026-10-17:

- DAG e três tasks em success.
- Cinco localidades, 160 registros, zero nulos.
- Cobertura Raw exata de 32 horários por cidade naquela execução.
- Manifesto, relatórios, referências e hashes reconciliados.
- Três retornos XCom abaixo de 8 KiB.
- Runs anteriores 01 e 02 preservadas como failed.
- DAG novamente pausada e schedule=None.

Isso não valida retries, replay operacional, agendamento, publicação, warehouse ou SLA.

## 4. Diagnóstico do código existente

Fontes analisadas na baseline operacional: `dags/weather_extract.py`, `scripts/weather_interface.py`, `scripts/extract_weather.py` e `scripts/weather_window.py`. A identidade de contexto também foi conferida na preparação de P08-R03.

### 4.1 Comportamento existente

- O contexto de orquestração usa a identidade dag_id + airflow_run_id.
- Repetir a preparação no mesmo contexto recupera as identidades persistidas e exige consistência com o manifesto.
- Outro Airflow run_id gera outro contexto e pode gerar outro batch, mesmo para o mesmo ciclo.
- execute_extraction verifica resultados finais íntegros e retorna mode=replay sem chamar collect_batch.
- started.json sem completed.json bloqueia coleta automática por estado ambíguo.
- Artefatos esperados existentes sem conclusão também bloqueiam nova coleta automática.
- A conclusão técnica pode persistir resultado partial_success ou failed quando os artefatos são consistentes.
- A reconciliação rejeita batch_status diferente de success.
- validated_with_nulls pode participar de batch_status=success. Isso não significa aptidão integral para publicação.
- Falhas de execução sem relatório individual preservam a causa no resumo e usam a categoria existente execution_error.
- Falha ao persistir o próprio incidente deve permanecer explícita; não se pode garantir arquivo de auditoria quando o armazenamento falha.

### 4.2 Limitações existentes

max_active_runs=1 limita concorrência dentro da DAG; não impede duas coletas sequenciais para o mesmo slot com run IDs diferentes, nem coleta externa pela CLI.

completed.json comprova resultado persistido e reconciliável, não aprovação analítica. Replay de uma conclusão parcial deve preservar a parcialidade.

A configuração HTTP é reconstruída em memória a partir do JSON. Os manifestos históricos não devem ser modificados para adequar timeouts ou futuras políticas.

Não existe nesta proposta uma garantia de execução exatamente uma vez no provedor externo. Após envio HTTP e interrupção anterior à persistência, o estado pode ser ambíguo. O comportamento conservador é bloquear e investigar.

## 5. Estratégia proposta de testes

### 5.1 Ambientes

- **E1 — Teste isolado Python:** fixtures sintéticas, relógio controlado e project_root temporário; sem Airflow operacional, sem banco e sem dados reais.
- **E2 — Subprocesso descartável:** mesmas restrições de E1, para interrupção de processo e validação posterior do estado deixado em disco.
- **E3 — Integração com Airflow:** somente em fase futura especificamente autorizada, após E1/E2. Ambiente, runs permitidas e método de teste deverão constar de novo plano.

Nenhum cenário da primeira fase usa os manifestos reais de R02/R03 como alvo mutável. Caso uma cópia histórica seja necessária, seu uso e destino deverão ser explícitos; a preferência é por fixtures sintéticas.

### 5.2 Barreiras comuns

- Rede externa bloqueada no ambiente e conexões socket interceptadas quando aplicável.
- Contador de chamadas ao transporte, inclusive nos caminhos de replay.
- Adaptador Requests real preservado nos testes de sua fronteira; não substituir sua validação por um mock que aceite qualquer argumento.
- Respostas HTTP fornecidas pelo transporte simulado.
- Esperas de retries simuladas, mantendo a verificação da sequência prevista.
- Escritas limitadas à raiz temporária de cada cenário.
- IDs, configuração, instante de coleta e ponto de injeção registrados.
- Manifestos, referências e arquivos históricos operacionais fora do alcance dos testes.
- Nenhum uso de execute_extraction com manifestos operacionais neste gate.

O isolamento deverá ser demonstrado, não presumido pela presença de mocks.

### 5.3 Evidências comuns obrigatórias

Para cada cenário: identificação, baseline, hipótese, risco, ambiente, fixture, ponto da falha, número de chamadas, IDs, estados, exceções/categorias, inventário e hashes anteriores/posteriores, código de saída e limitações.

Aprovação exige todos os resultados esperados. Código 0, contagem de arquivos ou presença de completed.json isoladamente não aprovam um cenário.

## 6. Matriz de cenários

Em todas as linhas, as barreiras da seção 5 são obrigatórias.

| ID | Hipótese e risco | Método / ambiente | Resultado esperado e critério de aprovação |
|---|---|---|---|
| F01 | Timeout/conexão falha antes da resposta; risco de multiplicar tentativas ou perder a causa | E1; transporte falha nas tentativas de uma cidade | No máximo três tentativas; mesmo run meteorológico, attempt IDs distintos; nenhum Raw da cidade sem resposta; relatório failed e batch sem sucesso integral |
| F02 | Falha transitória seguida de recuperação; risco de reexecutar o batch inteiro | E1; timeout, HTTP 503 e HTTP 200 válido | Três tentativas, parâmetros estáveis, um Raw final e histórico de tentativas preservado; nenhuma recolha das cidades já processadas por retry do batch |
| F03 | HTTP 200 incompleto; risco de sucesso enganoso | E1; remover um horário exigível e os valores correspondentes | Raw preservado, cidade incomplete, horário faltante identificado, batch parcial e reconciliação reprovada |
| F04 | Falha após Raw e antes do relatório; risco de sobrescrita ou categoria enganosa | E1; injetar erro na escrita do relatório | Raw preservado, falha de persistência/execução transparente conforme o ponto, sem falso sucesso; ausência de conclusão íntegra impede nova coleta automática |
| F05 | Interrupção entre início e conclusão; risco de repetir HTTP sem saber o que foi persistido | E2; encerrar subprocesso após started.json e antes de completed.json | Execução posterior bloqueada por estado ambíguo, zero transporte HTTP nessa tentativa e mesmas identidades históricas |
| F06 | Replay íntegro; risco de nova chamada HTTP desnecessária | E1; fixture concluída, seguida de nova chamada no mesmo contexto | mode=replay; zero chamadas HTTP adicionais, mesmos IDs e hashes, nenhum novo arquivo |
| F07 | Conclusão parcial íntegra; risco de promover parcialidade a sucesso | E1; fixture completed com partial_success | Replay sem HTTP, contadores e parcialidade preservados; reconciliação continua reprovada |
| F08 | Batch bloqueado/artefatos órfãos; risco de reconstrução destrutiva | E1; início sem conclusão ou artefatos sem conclusão | Bloqueio sem HTTP, incidente quando gravável; nenhum artefato anterior sobrescrito |
| F09 | Corrupção posterior; risco de replay aceitar bytes divergentes | E1; alterar um byte em cópia temporária de Raw, relatório ou conclusão | Integridade reprovada antes de qualquer coleta; sem reparo ou sobrescrita automática |
| F10 | Manifesto/hash divergente; risco de executar parâmetros sem identidade confiável | E1; manifesto alterado ou hash informado incorreto | Bloqueio anterior à coleta, categoria de integridade, sem marca de início de uma nova coleta |
| F11 | Reconciliação divergente; risco de resumo não representar arquivos | E1; alterar contador, ID ou referência na fixture | Reconciliação reprova, não coleta e não corrige arquivos; futura integração E3 deve comprovar o estado Airflow correspondente |
| F12 | Reprocessamento confunde identidades; risco de duplicação por outro run_id | E1; preparar duas vezes no mesmo contexto e depois em contexto distinto | Mesmo contexto conserva IDs; contexto distinto é reconhecido como nova rodada. O teste evidencia a lacuna de deduplicação por slot, sem alegar que ela já foi resolvida |

### 6.1 Efeitos colaterais, contenção e rollback por cenário

| Cenários | Efeitos temporários admitidos | Contenção e rollback propostos |
|---|---|---|
| F01–F03 | Attempts, Raw quando houver resposta, relatórios e resumo sintéticos | Parar diante de transporte externo, excesso de tentativas ou sucesso enganoso; recolher evidências e descartar somente a raiz temporária |
| F04 | Raw e conjunto parcial de arquivos, possível incidente | Não completar arquivos manualmente nem repetir coleta; inspecionar o estado e descartar a fixture após documentação |
| F05 | Subprocesso encerrado e marca/conjunto parcial deixado em disco | Encerrar apenas o processo do teste, confirmar ausência de processos residuais; inspecionar sem reparar e remover somente o ambiente temporário após evidências |
| F06 | Nenhuma escrita adicional esperada | Qualquer alteração ou chamada HTTP reprova; preservar diferenças e encerrar |
| F07 | Nenhuma escrita adicional esperada no replay do núcleo | Qualquer promoção de status ou coleta reprova; preservar resultado parcial da fixture |
| F08–F10 | Novo incidente sintético quando o armazenamento permitir | Não alterar os arquivos causadores do bloqueio durante a tentativa; preservar antes/depois e descartar só a fixture |
| F11 | Exceção de reconciliação; nenhuma escrita esperada pelo reconciliador | Qualquer coleta ou reparo reprova; capturar a divergência |
| F12 | Manifestos temporários em contextos distintos | Proibir uso de contextos reais e não interpretar novo contexto como autorização de operação |

Falha no bloqueio de rede ou escrita fora da raiz temporária interrompe o pacote inteiro. O rollback de fixtures não apaga a evidência do teste: primeiro registrar resultados e diferenças.

F05 simula interrupção de processo. Não comprova durabilidade diante de queda de energia, falha física de disco ou semântica de outro filesystem.

### 6.2 Detalhamento de replay e integridade

F06 deverá construir um resultado sintético final usando transporte simulado e a interface existente. Depois, registrar todos os caminhos, bytes/hashes, batch/run/attempt IDs e contagem de transporte. Invocar novamente execute_extraction com o mesmo manifesto e hash deve produzir mode=replay, metadados equivalentes e zero incremento no contador HTTP. Todos os arquivos devem permanecer idênticos, sem novo incidente.

F07 repete a conferência com resultado parcial tecnicamente concluído. A interface deve preservar partial_success; não preencher lacunas nem recolher cidades. O teste offline não declara um estado Airflow: a reprovação da task de reconciliação pertence a futura integração E3. Verifica-se aqui o status parcial e a coerência dos artefatos pelo núcleo.

F08 possui duas variantes separadas: started sem completed; artefato esperado existente sem started/completed. A tentativa de execução deve bloquear antes do transporte. Permite-se somente novo incidente de auditoria quando gravável; nenhum arquivo preexistente pode ser alterado.

F09 possui três variantes: Raw, relatório individual e completed alterados separadamente em fixtures. Comparar antes/depois da tentativa, tomando como referência de preservação o estado já adulterado pela simulação. O código não deve restaurar automaticamente a fixture nem substituir o resultado por nova coleta.

F10 separa hash informado incorreto de bytes do manifesto alterados mantendo o hash antigo. Em ambos, exigir zero HTTP e ausência de nova marca de início. O incidente pode não conhecer batch_id quando a integridade falha antes de confiar no manifesto.

F11, em E1, usa somente verificadores Python existentes para comprovar rejeição de resumo, relatório ou conclusão inconsistentes. Não extrair nem executar o corpo da task para ampliar artificialmente essa evidência. O estado real da task permanece fora de T01.

### 6.3 Detalhamento de interrupção e persistência

F04 injeta falha de persistência após a gravação do Raw e antes do relatório. Conferir a causa primária, os arquivos que efetivamente chegaram ao disco e a ausência de conclusão íntegra. Uma nova tentativa na mesma fixture não deve iniciar outra coleta.

F05 terá dois pontos de interrupção determinísticos em subprocesso descartável:

1. Depois de persistir started.json e antes do primeiro acesso ao transporte.
2. Depois de persistir o Raw de uma cidade e antes de completed.json.

Usar sinalização de prontidão entre processo filho e controlador, com espera máxima definida no teste; não depender de sleep arbitrário para adivinhar a posição da falha. O ponto de parada será instrumentado apenas no processo de teste, sem hook permanente no código de produção.

O controlador encerra somente o filho identificado, aguarda sua saída e verifica que não sobrou processo. Um novo processo de inspeção usa a mesma raiz temporária e barreira de rede: execute_extraction deve bloquear por estado ambíguo, preservando IDs e arquivos existentes; novo incidente é permitido. O contador externo ao processo ou registro de teste deve demonstrar zero transporte adicional nessa tentativa.

A fixture deve ter raiz própria e não herdar credenciais/configuração operacional. Se não for possível estabelecer essas barreiras com os recursos existentes, interromper e devolver uma proposta de ajuste; não mudar Compose ou instalar dependências silenciosamente.

### 6.4 Baseline observada versus mecanismos futuros

| Aspecto | Aceite da baseline no teste offline | Fora do aceite T01 |
|---|---|---|
| Replay | Mesmo manifesto/contexto íntegro não coleta de novo | Reutilização entre novos Airflow run IDs |
| Ambiguidade | Início sem conclusão bloqueia | Recuperação automática, retomada de cidade ou exclusão de marca |
| Identidades F12 | Mesmo contexto conserva IDs; contexto distinto cria outra identidade | Unicidade global do slot, inclusive contra CLI |
| Integridade | Verificadores rejeitam inconsistências e preservam artefatos | Reparo, migração ou mudança de contrato |
| Reconciliação | Núcleo rejeita artefatos incoerentes; parcialidade permanece visível | Estado de task/DAG, cancelamento ou retries Airflow |
| Temporalidade | Janela e cobertura atuais podem ser testadas com datas sintéticas | Novo resolvedor de agenda, bloqueio 14h15 e política de retomada |

F12 passa quando caracteriza corretamente a identidade existente, mesmo evidenciando que dois contextos distintos podem representar o mesmo slot nominal. Isso não aprova a lacuna para ativação da agenda: o mecanismo de unicidade continua bloqueador arquitetural separado.

## 7. Retries HTTP e retries Airflow

### 7.1 Estado existente

O extrator admite até três tentativas HTTP por cidade. Entre tentativas aplicáveis, as esperas são de 1 e 2 segundos.

São retentáveis: timeout, conexão e HTTP 500, 502, 503 e 504. HTTP 429 não integra atualmente essa seleção; isso é limitação a documentar, sem alteração automática neste pacote.

Cada tentativa HTTP possui attempt_id próprio, attempt_no e vínculo ao run_id meteorológico. Batch e run IDs não devem mudar devido à tentativa HTTP.

As três tasks Airflow possuem retries=0. Reexecutar uma task significa executar novamente sua função, não apenas retentar a última solicitação.

### 7.2 Recomendação pendente

Manter retries Airflow em zero. Não multiplicar o limite HTTP pela repetição automática de toda a task.

O núcleo deve retornar replay quando houver conclusão íntegra e bloquear estados ambíguos. Qualquer proposta de retry Airflow posterior depende dos resultados de persistência e replay, e de aprovação específica.

Não prometer recuperação automática de batches parciais. Se uma recolha for necessária, deverá ser uma nova rodada autorizada, preservando a origem e os resultados anteriores.

## 8. Política temporal diária

Esta seção distingue regra de negócio aprovada de mecanismos ainda propostos. A DAG existente continua manual, pausada e com schedule=None.

### 8.1 Slot, intervalo e ciclo

Slot principal hipotético: D às 13h45 em America/Sao_Paulo. D é a data local do slot nominal, conforme direção aprovada. A janela meteorológica continua [D 16h, D+2 00h), normalmente 32 horas; não confundir duração do intervalo Airflow com janela de previsão.

| Elemento | Semântica no desenho |
|---|---|
| logical_date | Determinada pela timetable; não é o relógio da coleta |
| data_interval_start/end | Intervalo Airflow da timetable escolhida |
| scheduled_slot | Instante nominal D 13h45, com timezone, normalizável em UTC |
| cycle_date D | Data local desse slot |
| collected_at | Instante real de cada resposta; usado na cobertura e no frescor |

O instante hipotético da coleta é 2h15 antes do início da janela; a disponibilização pretendida é 1h30 antes. Isso dá finalidade à previsão, sem garantir que os dados chegarão completos.

Para runs manuais, cycle_date continua explícito e não deve ser inferido do intervalo manual. Elas não consomem silenciosamente um slot agendado.

### 8.2 Alternativas de timetable — decisão pendente

| Alternativa | Semântica | Retomada |
|---|---|---|
| CronDataIntervalTimetable diária | Intervalo entre duas ocorrências de 13h45; logical_date no início, slot no fim | Pode haver run do último intervalo ao reativar com catchup=False |
| CronTriggerTimetable diária, sem intervalo adicional | Disparo no instante nominal, intervalo pontual | Tende a aguardar o próximo disparo; pode perder o slot do dia se o scheduler voltar depois dele |

Recomendação para revisão: explicitar CronDataIntervalTimetable diária e usar data_interval_end como slot, combinada com elegibilidade de atraso/corte antes de permitir HTTP. É uma recomendação, não escolha ratificada. Não ativar agenda sem esse controle e sem unicidade por slot.

Expressão diária candidata para o horário hipotético: `45 13 * * *`. É apenas especificação documental, não alteração do schedule.

### 8.3 Virada do dia

Exemplo com timetable de intervalo: [16/10 13h45, 17/10 13h45) tem slot em 17/10 e D=17/10, embora logical_date pertença ao dia 16.

Se esse slot só chegar à preparação após a meia-noite, ele continua sendo do dia 17; não recalcular D para o dia 18. A elegibilidade deve rejeitar a coleta atrasada para a finalidade diária e registrar indisponibilidade/tardio conforme política futura, sem criar outro ciclo automaticamente.

Usar America/Sao_Paulo, sem codificar offset fixo. Persistir instantes com timezone e preservar os campos dos manifestos históricos.

### 8.4 Elegibilidade futura

Antes de HTTP, resolver e congelar slot/D; validar atraso/corte, unicidade, estado persistido, horizonte da fonte e conflito conhecido com CLI. Revalidar elegibilidade junto ao início efetivo do transporte: aprovação na preparação não elimina atraso posterior em fila. O controle exato é implementação futura sujeita a aprovação.

A janela deve estar dentro do horizonte do endpoint e ter horários exigíveis. Após a resposta, medir novamente cobertura e qualidade. Uma resposta recebida após o corte deve ser classificada pela política de resultado tardio, sem reescrever os bytes Raw.

O código atual exige horários da janela maiores ou iguais a collected_at; às 18h07, a exigência começa às 19h. Isso não habilita uso de uma coleta tardia para a decisão das 14h30.

A documentação da Open-Meteo consultada na v0.1 indica sete dias por padrão e extensão até 16 dias. Confirmar a elegibilidade do ciclo na data do futuro ensaio. Não usar o endpoint de previsão como backfill irrestrito.

## 9. Cadência do MVP e retomada do scheduler

### 9.1 Decisão de negócio

Uma coleta principal diária para a decisão das 14h30. Não adotar `0 */2 * * *` no MVP. Atualizações extraordinárias pertencem a evolução posterior e exigem autorização própria.

Estimativa de uma rodada diária: cinco tentativas iniciais, até 15 tentativas HTTP se todas as cidades consumirem três tentativas. Não inclui qualquer execução manual extraordinária e não constitui garantia de quota ou prazo.

Manter, enquanto não houver decisão específica, retries Airflow=0, catchup=False, max_active_runs=1 e max_active_tasks=1. Nenhum desses controles implementa corte ou unicidade de negócio.

### 9.2 Casos de retomada a decidir antes da agenda

| Situação | Comportamento futuro recomendado |
|---|---|
| Scheduler disponível antes de 13h45 | Aguardar o slot e criar a run nominal |
| Retorno após 13h45, antes do corte | Admitir no máximo o slot vigente, somente se tolerância aprovada, unicidade e tempo disponível permitirem |
| Retorno em ou após 14h15 | Não iniciar coleta para a decisão diária desse slot |
| Retorno no dia seguinte | Não recolher automaticamente o slot perdido nem transformar o ciclo antigo no atual |
| Batch do slot já concluído | Verificar/reutilizar resultado conforme mecanismo aprovado, sem novo HTTP |
| Batch iniciado sem conclusão | Bloquear e investigar; não apagar marca nem gerar outra identidade para contornar bloqueio |

catchup=False evita recuperar toda a série, mas não basta para decidir se uma run criada na retomada ainda é útil ao negócio. A timetable e a elegibilidade deverão ser verificadas por simulação estática antes de qualquer ensaio de scheduler.

O comportamento desejado da tabela é requisito futuro. A baseline não possui esses controles e não poderá recebê-los como consequência implícita de T01.

## 10. Duplicação, replay e controle de slot

### 10.1 Distinções

- Mesmo contexto concluído e íntegro: replay.
- Mesmo contexto iniciado sem conclusão: bloqueio.
- No MVP diário, apenas o slot principal é previsto. Atualização extraordinária não é autorizada por representar outro slot; pertence à evolução posterior.
- Outro Airflow run_id para slot já utilizado: não deve iniciar nova coleta automaticamente.
- Nova rodada manual: exige autorização e vínculo de origem quando aplicável; não é replay apenas por usar o mesmo D.

### 10.2 Lacuna e decisão arquitetural

O último controle de slot não está garantido pela identidade atual dag_id + airflow_run_id.

Será necessário especificar uma identidade persistente de slot e mecanismo de reivindicação atômica. Uma chave candidata deve distinguir DAG/finalidade e instante nominal do slot, com política de versão claramente definida.

Pesquisar arquivos e depois gravar não basta: existe janela de corrida. Deve-se avaliar o mecanismo de criação exclusiva já usado no projeto, suas garantias reais no volume Windows/Docker e a recuperação após interrupção.

Não se escolhe nesta versão um novo schema, caminho de índice, migração ou banco. A implementação depende de decisão central. max_active_runs e o agendador não substituem a política para runs manuais ou coleta CLI.

## 11. Atrasos, corte, frescor e fallback

Os horários 13h45, 14h15 e 14h30 são hipóteses iniciais para desenho. Não representam execução ativada, publicação implementada ou SLA comprovado.

### 11.1 Alternativas para atraso

| Alternativa | Vantagem | Limite |
|---|---|---|
| A — Tolerância de 15 minutos, até 14h00 inclusive, e corte prevalente | Reserva margem antes de 14h15; recomendação inicial | Pode recusar uma execução ainda útil; não garante conclusão |
| B — Iniciar enquanto houver orçamento calculado antes de 14h15 | Maior flexibilidade | Exige orçamento fim a fim demonstrado; timeout de leitura não basta |
| C — Perdeu 13h45, não coletar automaticamente | Regra simples e previsível | Menor disponibilidade após falha breve do scheduler |

Recomendação para ratificação: A, sem tentar medir sucesso apenas pelo tempo observado em R03. Em todos os casos, não iniciar em ou após 14h15. Tolerância e fronteiras exatas ainda dependem de João.

### 11.2 Execução em andamento no corte

| Alternativa | Implicação |
|---|---|
| Cancelar no corte | Pode deixar started sem completed; exige controle real de processos e tratamento da ambiguidade |
| Deixar concluir, marcando resultado como tardio e inelegível à decisão diária | Preserva rastreabilidade; não garante interrupção do consumo de recursos |
| Aceitar conclusão até outro limite | Muda o significado de 14h15 e exige nova decisão explícita |

Recomenda-se, para o desenho inicial, a segunda alternativa: preservar o resultado e excluí-lo do aceite da decisão diária quando tardio. Não afirmar que isso está implementado nem que atende a um requisito de parada absoluta. Se o negócio exigir interrupção às 14h15, será necessário outro desenho aprovado. Pause da DAG não deve ser tratado como cancelamento de tasks em andamento.

### 11.3 Frescor e qualidade

Frescor mede idade da coleta; não comprova idade da rodada do modelo meteorológico. Proposta para discussão: avaliar a idade mais antiga entre as cinco cidades no instante de decisão, mantendo também todas as idades individuais.

Limite de 45 minutos às 14h30 é uma hipótese candidata coerente com coleta às 13h45, mas sujeito a latência e confirmação do negócio. Alternativa: limite maior explicitamente aprovado. Não transformar essa hipótese em regra de teste ou implementação antes da ratificação.

Elegibilidade analítica deverá exigir ciclo/janela corretos, cinco localidades, integridade, cobertura e política de nulos aprovada. success/validated_with_nulls não bastam. Incomplete ou dados fora do prazo não devem ser promovidos por um resumo positivo.

### 11.4 Fallback

Recomendação MVP: registrar indisponibilidade explícita quando não houver batch elegível; sem substituição automática.

Alternativa futura: batch anterior somente se cobrir integralmente a janela do ciclo atual, respeitar idade e qualidade aprovadas e indicar claramente sua origem. Um batch de D-1 normalmente não cobre a janela completa de D; não pode ser fallback apenas por ser o mais recente.

Disponibilização pretendida às 14h30 continua requisito de negócio, sem task de publicação, warehouse ou placeholder nesta fase. Timeout (10,30), execution_timeout e dagrun_timeout não são deadline absoluto. Nenhuma garantia de publicação, frescor ou fallback é declarada como implementada.

## 12. Impactos e alterações potenciais

| Componente | Estado / alteração potencial |
|---|---|
| DAG | Hoje manual, schedule=None e pausada. Futuramente distinguir execução manual/agendada e fornecer contexto temporal estável |
| Python puro | Futuro resolvedor de ciclo/slot e elegibilidade, sem imports Airflow |
| Manifestos | scheduled_slot já permitido; preservar bytes históricos. Novos campos exigem revisão de contrato |
| Deduplicação | Novo desenho de reivindicação atômica por slot, ainda não escolhido nem implementado |
| Testes | Fixtures sintéticas, barreiras de rede/escrita e cenários faltantes; evitar duplicar testes existentes |
| Infraestrutura | Nenhuma mudança recomendada para E1/E2; qualquer necessidade posterior regressa ao Planeamento |
| Qualidade/publicação | Preservar estados existentes; não confundir success ou validated_with_nulls com aptidão integral |

Não se propõe alterar silenciosamente R3/DQ, Raw/run/batch, assinaturas existentes ou snapshots. Qualquer necessidade identificada pelos testes exige diff e nova avaliação.

## 13. Proposta fechada para P09-T01 — offline

**Estado: proposta de escopo; P09-T01 NÃO LIBERADO.** A aprovação da v0.2 não libera automaticamente sua execução.

### 13.1 Objetivo e fronteira

Caracterizar e verificar a baseline operacional 770a7a1 usando F01–F12 no núcleo Python, respeitando as limitações da seção 6.4. Não desenvolver mecanismos futuros para fazer um teste passar.

Arquivos candidatos, sujeitos à autorização específica:

- tests/test_weather_resilience_offline.py: cenários E1.
- tests/test_weather_interruption.py: controlador e cenários E2.
- tests/helpers/weather_resilience.py e eventual __init__.py: fixtures e barreiras locais, se necessários.
- docs/24-evidencias-p09-t01-offline.md: matriz de resultados e limitações.

Reutilizar fixtures/testes existentes quando adequados; alterações em outros arquivos de teste precisam constar do diff proposto ao Planeamento. Código de produção, DAG, Compose e dependências ficam fora do pacote.

Não incluir novo resolvedor temporal, índice/claim por slot, política de corte, implementação de fallback, alteração de retries ou semântica de contrato.

### 13.2 Ambiente e isolamento

E1/E2 sem serviços Airflow operacionais e sem banco. Preferir contêiner descartável com a imagem existente, rede desativada, scripts/config/testes somente para leitura, sem .env, sem data/logs reais, sem socket Docker montado. Fixture e evidências de teste ficam em diretório temporário próprio.

Usar Python 3.10.14 como alvo de compatibilidade; execução Windows pode complementar, mas não substitui esse alvo. Usar dependências já disponíveis ou procedimento offline previamente aprovado. Ausência de dependência interrompe a execução para revisão, sem instalar ou mudar imagem por iniciativa própria.

Não reconstruir a imagem nem recriar os serviços. O encerramento F05 atinge somente subprocessos do contêiner descartável, nunca scheduler/webserver.

### 13.3 Casos incluídos e ordem

1. Inventário de testes existentes e mapeamento para F01–F12.
2. F06 íntegro; F08 nas duas variantes; F09 nos três tipos de artefato; F10 nas duas variantes; F12 nos dois contextos.
3. F01 timeout e conexão; F02 sequência transitória; F03 horário exigível removido; F07 parcial concluído.
4. F04 falha entre Raw e relatório; F05 nos dois pontos de interrupção definidos.
5. F11 pelos verificadores puros; sem executar a task Airflow.
6. Regressão Python afetada com rede bloqueada; sem suíte estrutural que inicialize Airflow/metadados operacionalmente.

Datas sintéticas podem comprovar build_cycle_window/evaluate_coverage existentes. Simulação de timetable, retomada de scheduler, resolvedor D/slot, tolerância e deadline ficam para pacote temporal separado; não testar como implementada uma política ausente.

### 13.4 Aceite e evidências

- Casos mapeados individualmente, sem skips silenciosos.
- Zero chamadas HTTP reais; chamadas simuladas contadas.
- Replay íntegro sem qualquer arquivo novo ou mutação.
- Bloqueio de estados ambíguos sem novo HTTP; incidentes permitidos conforme cenário.
- IDs e bytes históricos da fixture preservados.
- Interrupção determinística, processo filho encerrado e ausência de processos residuais.
- Resultados de parcialidade não promovidos.
- Limitação F11 claramente registrada: não prova estado de task/DAG.
- Limitação F12 claramente registrada: não prova unicidade de slot.
- Diff restrito aos arquivos autorizados; git diff --check e revisão documental.
- Comandos efetivos, versões, códigos de saída, contagens por cenário, hashes/inventários e falhas apresentados.
- Falha inesperada interrompe avanço: documentar e devolver ao Planeamento, sem corrigir produção ou ampliar cenários silenciosamente.

Ao término, submeter P09-T01 — EVIDÊNCIA SUBMETIDA para avaliação central. Não declarar passo 09 validado nem avançar a integração/agenda.

### 13.5 Etapas posteriores, fora de T01

Após T01: resolver questões arquiteturais, especificar mecanismo de slot e temporalidade, aprovar diff de implementação e testes temporais. Só depois, propor E3 com ambiente, quantidade exata de runs, contenção e gate próprio. Ensaio de agenda permanece dependente de autorização separada e dos pré-requisitos de resiliência.

## 14. Rollback e preservação

Para E1/E2: recolher evidências antes de descartar fixtures; encerrar subprocessos do teste, sem tocar serviços operacionais.

Para futuras alterações versionadas: rollback por reversão dos commits específicos autorizados, após avaliação central. Não usar reset destrutivo, apagar runs, excluir started.json/completed.json históricos ou clear como atalho de recuperação.

Para futuro ensaio de agenda: plano próprio deve prever pausa final, conferência de ausência de novas runs e tratamento de task já em execução. Esses procedimentos não estão liberados por este documento.

Qualquer falha fora dos critérios previstos interrompe o avanço e retorna ao Planeamento.

## 15. Decisões ainda pendentes

A finalidade diária, D pela data local do slot, janela contratual e exclusão do cron de duas horas do MVP foram aprovados conforme o encaminhamento central. Não reapresentá-los como questões de negócio em aberto.

| ID | Decisão pendente | Recomendação documental |
|---|---|---|
| D03 | Timetable diária e retomada | Intervalo diário explícito com elegibilidade antes de HTTP; revisar antes de ativar |
| D04 | Tolerância e fronteiras | Alternativa A: até 14h00 inclusive para slot 13h45; ainda não ratificada |
| D05 | Unicidade de slot | Definir chave, claim atômico, persistência e ambiguidade; fora de T01 |
| D06 | Corte com coleta em andamento | Concluir como tardio/inelegível; confirmar se negócio exige parada absoluta |
| D07 | Frescor e nulos | Avaliar pior idade entre cidades; 45 minutos é hipótese candidata, não limite aprovado |
| D08 | Fallback | Indisponibilidade explícita no MVP; nenhuma substituição automática |
| D09 | Gate T01 | Aprovar ou ajustar o escopo fechado da seção 13 antes de implementar/executar |
| D10 | Integração e agenda | Novo gate posterior, com contagem de runs e contenção |

Os horários 13h45/14h15/14h30 permanecem hipóteses iniciais de operação; sua implementação e aceitação como garantias não foram liberadas.

## 16. Referências

Código aprovado:

- https://github.com/Soba-Jopeca/logistics-weather-data-pipeline/tree/770a7a1f01440bb96443b8cde645b65b8164ea86
- docs/15-especificacao-airflow-secao04-v0.1.md
- docs/21-evidencias-p08-c02-timeout.md
- docs/22-evidencias-p08-r03-execucao-manual.md

Documentação oficial consultada durante o diagnóstico de 16/10/2026:

- https://airflow.apache.org/docs/apache-airflow/2.9.2/core-concepts/dag-run.html
- https://airflow.apache.org/docs/apache-airflow/2.9.2/authoring-and-scheduling/timetable.html
- https://open-meteo.com/en/docs

## 17. Devolução e controle da revisão

**P09-P01 v0.2 — REVISÃO DOCUMENTAL SUBMETIDA.**

Esta revisão incorpora a direção diária aprovada, preserva integralmente as linhas F01–F12 e detalha seus limites, a interrupção de processo e o escopo proposto para T01.

Diff contra v0.1 apresentado a João antes da publicação e expressamente aprovado em 17/10/2026 para publicação exclusivamente documental. O commit desta revisão será identificado no encaminhamento central, sem confundi-lo com a baseline operacional. Essa aprovação não libera P09-T01.

Nenhum teste foi executado nesta revisão. Passo 09 não validado. P09-T01, implementação temporal, ensaio de agenda e passos 10–11 permanecem não liberados.
