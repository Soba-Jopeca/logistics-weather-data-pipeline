# P09-P01 — Proposta de resiliência e política de agendamento

## 1. Identificação, autorização e estado

- Projeto: Logistics Weather Data Pipeline.
- Checkpoint: CP-2026-10-13 v2.
- Identificação: AF-CPv2-P09-P01-v0.1.
- Data desta versão documental: 17/10/2026, America/Sao_Paulo.
- Proposta inicialmente apresentada em chat: 16/10/2026.
- Destino: Planeamento central e João.
- Responsável pela proposta: Airflow — Seção 4.
- Baseline operacional analisada: `770a7a1f01440bb96443b8cde645b65b8164ea86`.
- Evidência de P08-R03: `docs/22-evidencias-p08-r03-execucao-manual.md`, commit `011d01b2283ac89573aa36b23d30b350b81a79c0`.
- Estado: **P09-P01 — PROPOSTA TÉCNICA SUBMETIDA; revisão e decisões arquiteturais pendentes**.

O Planeamento central, com ratificação expressa de João, validou o passo 08 com limitações e liberou o passo 09 exclusivamente para planeamento, diagnóstico e proposta. João autorizou expressamente a criação deste documento. Essa autorização documental não libera implementação ou execução de testes.

Passos 01–02 e 05–07 validados; 03–04 validados com ressalvas; 08 validado com limitações. Passo 09 não validado. Passos 10–11 não liberados.

O parecer preliminar central considerou a proposta alinhada ao escopo, mas apontou decisões arquiteturais pendentes. A revisão anterior utilizou a síntese disponível, sem auditoria integral de documento publicado. Esta versão fornece o texto consolidado para essa revisão, sem tratar as recomendações como decisões aprovadas.

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

## 8. Política temporal proposta

Esta seção descreve desenho futuro, não implementado.

### 8.1 Relação entre intervalo, slot e ciclo

Recomendação: usar o comportamento de cron baseado em intervalos, explicitamente validado no Airflow 2.9.2.

| Elemento | Semântica proposta |
|---|---|
| logical_date | Início do intervalo Airflow; não é o instante real da coleta |
| data_interval_start | Limite inicial do intervalo da orquestração |
| data_interval_end | Limite final do intervalo e referência do slot nominal |
| scheduled_slot | Instante nominal de data_interval_end, interpretado em America/Sao_Paulo |
| cycle_date D | Data local de scheduled_slot para runs agendadas |
| collected_at | Instante real da resposta; usado para cobertura e frescor |

O slot é um instante com timezone, não uma hora sem data. Persistir representação ISO com offset e normalizar a identidade por instante UTC evita ambiguidades. Não assumir offset -03 fixo como regra geral: usar America/Sao_Paulo.

Para run manual, cycle_date continua explícito. Não inferir seu ciclo a partir do data_interval manual. Runs manuais não devem assumir silenciosamente a identidade de um slot agendado.

### 8.2 Exemplos da política recomendada

| Intervalo local Airflow | Slot nominal | D proposto |
|---|---|---|
| 16/10 22h → 17/10 00h | 17/10 00h | 17/10 |
| 17/10 12h → 14h | 17/10 14h | 17/10 |
| Slot de 17/10 14h executado com atraso | Continua 17/10 14h | Continua 17/10 |

Atraso não muda ciclo silenciosamente. Se a run ultrapassar a tolerância aprovada, deverá ser rejeitada para nova coleta ou tratada pela política explicitamente autorizada.

A janela meteorológica permanece [D 16h, D+2 00h). Os intervalos de duas horas do Airflow não substituem essa janela.

O ciclo não é recalculado pelo relógio de cada task. A preparação resolve o contexto uma vez; tasks seguintes usam as referências persistidas.

### 8.3 Elegibilidade temporal

Antes de uma futura coleta agendada:

1. Resolver slot e D de modo determinístico.
2. Conferir janela dentro do horizonte documentado do endpoint.
3. Exigir pelo menos um horário futuro exigível no instante efetivo da coleta.
4. Verificar contexto/slot e ausência de conflito conhecido com coleta externa.
5. Conferir estado persistido compatível com nova execução ou replay.
6. Aplicar tolerância de atraso e regra de corte que venham a ser aprovadas.

A cobertura é medida novamente após a resposta. A requisição da janela completa não garante que todos os horários serão retornados.

O código atual exige horários da janela que sejam maiores ou iguais ao instante collected_at. Assim, uma coleta às 18h07 passa a exigir a hora das 19h em diante. Quantidade recebida e quantidade exigível são medidas distintas.

A Open-Meteo documenta horizonte padrão de sete dias e extensão até 16 dias. Horizonte documentado não equivale a garantia de disponibilidade, completude ou aptidão de cada resposta. Eventual recuperação histórica exige verificar produto e contrato de fonte; não tratar o endpoint de previsão como backfill irrestrito.

## 9. Cadência candidata e catchup

### 9.1 Avaliação de 0 */2 * * *

No timezone da DAG, a cadência representa 12 slots diários, às 00h, 02h, ..., 22h.

Com cinco solicitações individuais por rodada: até 60 tentativas iniciais por dia; até 180 tentativas HTTP se todas consumirem três tentativas em cada slot. São estimativas do desenho atual, não medição ou garantia de quota. Nenhuma coleta adicional CLI está incluída nesses números.

Dois objetivos precisam ser distinguidos:

- Atualização durante todo o dia: 12 slots; após as 16h a cobertura futura exigível diminui.
- Preparação de decisão diária às 14h30: slots de 16h a 22h não contribuem para essa decisão do mesmo dia. Uma janela de slots restrita pode ser mais coerente e econômica.

Recomendação: decidir primeiro a finalidade da cadência. Não ativar o cron candidato apenas para demonstrar agendamento.

### 9.2 catchup e concorrência

Manter catchup=False, max_active_runs=1 e max_active_tasks=1.

catchup=False não elimina toda possibilidade de run imediata ao reativar uma DAG baseada em intervalos. O cron convencional utiliza CronDataIntervalTimetable; CronTriggerTimetable tem semântica distinta de intervalo e retomada. Não trocar timetables sem revisar a política de slot.

max_active_runs=1 serializa esta DAG, mas não garante frescor nem unicidade entre coletas sequenciais ou processos externos. Atrasos em fila devem passar pela elegibilidade temporal.

Proposta para discussão: tolerância inicial de 15 minutos após o slot nominal. Não aprovada. Na finalidade diária, o corte deve prevalecer: um slot das 14h não ganha permissão para começar às 14h15 por causa dessa tolerância.

## 10. Duplicação, replay e controle de slot

### 10.1 Distinções

- Mesmo contexto concluído e íntegro: replay.
- Mesmo contexto iniciado sem conclusão: bloqueio.
- Slot diferente do mesmo ciclo: possível atualização intencional, com novo batch.
- Outro Airflow run_id para slot já utilizado: não deve iniciar nova coleta automaticamente.
- Nova rodada manual: exige autorização e vínculo de origem quando aplicável; não é replay apenas por usar o mesmo D.

### 10.2 Lacuna e decisão arquitetural

O último controle de slot não está garantido pela identidade atual dag_id + airflow_run_id.

Será necessário especificar uma identidade persistente de slot e mecanismo de reivindicação atômica. Uma chave candidata deve distinguir DAG/finalidade e instante nominal do slot, com política de versão claramente definida.

Pesquisar arquivos e depois gravar não basta: existe janela de corrida. Deve-se avaliar o mecanismo de criação exclusiva já usado no projeto, suas garantias reais no volume Windows/Docker e a recuperação após interrupção.

Não se escolhe nesta versão um novo schema, caminho de índice, migração ou banco. A implementação depende de decisão central. max_active_runs e o agendador não substituem a política para runs manuais ou coleta CLI.

## 11. Corte, publicação, frescor e fallback

Requisitos a analisar, ainda não implementados:

- Corte operacional às 14h15 de São Paulo.
- Eventual publicação às 14h30.
- Elegibilidade de batches atrasados, incompletos ou com nulos.
- Frescor máximo aceitável.
- Fallback e sua rastreabilidade.

Recomendação preliminar para a finalidade diária: nenhuma nova coleta começa em ou após 14h15. É necessário decidir o que ocorre com uma execução já iniciada quando o corte chega: cancelamento controlado, conclusão apenas para diagnóstico ou preservação do resultado como tardio. Não assumir que pause interrompe uma task em andamento.

A publicação exigirá selecionar batch íntegro, elegível, fresco e com qualidade aprovada. Não existe implementação de publicação nesta fase; não será adicionada task placeholder.

Fallback requer idade máxima, cobertura mínima, política de nulos, finalidade permitida e identificação explícita do batch de origem. Sem critérios aprovados, registrar indisponibilidade; não substituir dados silenciosamente.

Frescor de collected_at mede tempo desde a coleta por cidade. Não comprova a idade da previsão do modelo meteorológico. A regra de agregação entre cidades também precisa ser aprovada.

Timeout HTTP (10,30), execution_timeout e dagrun_timeout não são garantia de deadline absoluto das 14h15. A run de cerca de oito segundos de P08-R03 não comprova SLA. Nenhuma garantia de corte, publicação ou fallback é declarada nesta proposta.

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

## 13. Plano de validação e ordem recomendada

1. Revisar esta versão integral e ratificar as decisões arquiteturais necessárias.
2. Emitir autorização específica de implementação dos testes isolados, com arquivos e ambientes permitidos.
3. Inventariar testes existentes e mapear cobertura para evitar duplicação.
4. Executar inicialmente F06, F08–F10 e F12: replay, bloqueios, integridade e identidades.
5. Executar F01–F03 e F07: transporte, retries HTTP, incompletude e parcialidade.
6. Executar F04–F05: persistência e interrupção.
7. Executar F11 e testes temporais sintéticos, sem task execution.
8. Repetir regressão afetada e validação estrutural apropriada, sob o gate autorizado.
9. Submeter resultados, diferenças, incidentes e limitações ao Planeamento.
10. Somente após aprovação, propor E3 com número exato de runs, fixtures, contenção e autorização operacional própria.
11. Ensaiar agenda somente depois dos testes de falhas/replay e mediante autorização separada.

Testes temporais propostos: meia-noite, conversão UTC/IANA, atraso que cruza o dia, limite da tolerância, 14h14m59s/14h15/14h15m01s, coleta antes/depois das 16h, janela sem horários exigíveis, slot duplicado, pausa/reativação e histórico sem catchup.

Esses testes verificam a política aprovada; não devem implementar decisões ainda abertas apenas para obter aprovação na suíte.

## 14. Rollback e preservação

Para E1/E2: recolher evidências antes de descartar fixtures; encerrar subprocessos do teste, sem tocar serviços operacionais.

Para futuras alterações versionadas: rollback por reversão dos commits específicos autorizados, após avaliação central. Não usar reset destrutivo, apagar runs, excluir started.json/completed.json históricos ou clear como atalho de recuperação.

Para futuro ensaio de agenda: plano próprio deve prever pausa final, conferência de ausência de novas runs e tratamento de task já em execução. Esses procedimentos não estão liberados por este documento.

Qualquer falha fora dos critérios previstos interrompe o avanço e retorna ao Planeamento.

## 15. Decisões pendentes

| ID | Decisão | Recomendação ou questão aberta |
|---|---|---|
| D01 | Finalidade da cadência | Atualização contínua ou preparação diária para 14h30? |
| D02 | Ciclo agendado | Recomenda-se D = data local do slot nominal |
| D03 | Timetable | Recomenda-se avaliar cron por intervalo; validar retomada antes de ativar |
| D04 | Tolerância de atraso | 15 minutos propostos, sujeitos ao corte; valor não ratificado |
| D05 | Unicidade de slot | Definir identidade, reivindicação atômica e estado ambíguo |
| D06 | Corte com coleta em andamento | Definir interrupção ou conclusão tardia, sem declarar SLA |
| D07 | Frescor e qualidade | Definir limites por finalidade/cidade e tratamento de nulos |
| D08 | Fallback | Definir idade, cobertura, origem e comunicação de indisponibilidade |
| D09 | Próximo gate de testes | Delimitar arquivos, E1/E2, cenários e critérios autorizados |
| D10 | Validação Airflow posterior | Definir ambiente e quantidade de runs em autorização separada |

A aprovação documental desta proposta não aprova automaticamente todos os valores recomendados nem libera testes, implementação ou agenda.

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

## 17. Devolução

**P09-P01 — PROPOSTA TÉCNICA SUBMETIDA.**

Esta versão consolida a proposta apresentada no chat e explicita decisões que o parecer preliminar central considerou pendentes. Nenhum teste proposto foi executado por esta entrega.

Submeter à revisão integral de João e do Planeamento central. Passo 09 permanece não validado. Novos testes, alterações e ensaios dependem de decisão explícita específica. Passos 10–11 permanecem não liberados.

O commit desta entrega é documental e distinto das baselines operacional e de evidência P08 citadas acima; seu identificador acompanha o encaminhamento de publicação.
