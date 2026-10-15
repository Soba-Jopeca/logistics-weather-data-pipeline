# Airflow — Seção 4: especificação técnica v0.1

**Documento:** AF-S4-CPv2-P05-v0.1  
**Projeto:** Logistics Weather Data Pipeline / PHD-AL-2026-001  
**Data:** 15/10/2026 — America/Sao_Paulo  
**Checkpoint:** CP-2026-10-13 v2 | passo05  
**Estado:** Passo05 — EVIDÊNCIA SUBMETIDA; especificação aprovada por João neste chat, aguardando registro no Planeamento central.  
**Revisão editorial:** 15/10/2026; linguagem técnica do projeto autoral, conforme orientação de João.  
**Pré-requisitos:** 01–02 VALIDADOS; 03–04 VALIDADOS COM RESSALVAS; Gate Docker 01–04 ENCERRADO.  
**Autorização:** encaminhamento central apresentado por João em 15/10, restrito à especificação.  
**Bloqueio:** passos06–11 NÃO LIBERADOS. Este documento não autoriza implementação, trigger, unpause, agenda, testes que executam tasks ou carga SQL.

## 1. Base e limites da revisão

A liberação apresentada por João é a evidência de autorização vigente. O CPv2 original foi consultado como sequência normativa; seus estados históricos são superados somente pela liberação central atual. Não se atribui ao assistente atualização automática do chat Planeamento.

Foram consultados em leitura: CPv2; contrato R3 v0.1; matriz DQ v0.1; extrator, módulo temporal, README, Compose e evidência04 do repositório; referências oficiais Airflow 2.9.2. Commit de referência confirmado: 317fa7bd71604473329a9eebea19b04f2c76c309. Extrator/README/módulo temporal foram lidos pela main; antes da implementação, confirmar correspondência com a baseline e registrar qualquer diferença. A análise inicial não alterou o repositório. A publicação documental posterior foi autorizada por João; o commit desta especificação é distinto da referência consultada e deve ser identificado no histórico do arquivo e no relato de entrega.

A especificação apresenta decisões de engenharia do projeto autoral. Sua revisão usa o contrato de negócio, as evidências disponíveis e a documentação técnica oficial.

Ressalvas herdadas: reprodução Docker na mesma máquina e com cache, sem comprovação em outro host; suíte Python não repetida no contêiner no passo03; evidência03 em branch documental cuja integração precisa ser confirmada; bancos airflow/weather compartilham instância e volume, com administração pela role airflow superuser; testes pós-reinicialização04 parcialmente confirmados por João sem todas as saídas reenviadas; sem backup/restore validado. O encerramento central dos gates não elimina essas limitações.

Este passo produziu somente documentação e análise. Nenhum código do projeto foi importado ou executado; nenhuma requisição meteorológica, task, infraestrutura ou banco foi operado.

## 2. Decisão arquitetural recomendada

Identificador estável: **logistics_weather_extract**. Arquivo futuro proposto: dags/weather_extract.py. Não criar este arquivo no passo05.

DAG fina com wrappers TaskFlow @task. Núcleo Python permanece em scripts, com CLI existente preservada. Não mover para include sem benefício demonstrável. Núcleo não importa Airflow, não chama argparse/sys.exit por meio do callable e não realiza I/O ao ser importado.

Ambiente mantido: Airflow2.9.2, Python3.10, LocalExecutor, PostgreSQL16 para metadados. A DAG de extração não abre conexão weather. Scheduler e webserver devem enxergar os mesmos scripts/config; execução e reconciliação acessam o mesmo data/ persistente. Os mounts já documentados atendem ao desenho em princípio; importabilidade efetiva precisa de prova no06/07. Se exigir alteração Docker, retornar ao responsável e ao Planeamento.

### Granularidade

Uma DAG run representa uma rodada de cinco localidades, portanto um batch. Cada localidade tem seu run meteorológico e suas tentativas HTTP. **Airflow run_id e run_id meteorológico são identidades diferentes.**

Recomenda-se manter a coleta das cinco cidades sequencial dentro de uma task de rodada nesta primeira versão. Isso preserva o comportamento existente, a continuidade após falha local e o perfil de uso da API. max_active_runs=1 não transforma a coleta em paralela nem impede execução simultânea pela CLI ou por outro dag_id.

Alternativa futura: task mapeada por localidade. Só adotar com revisão de orçamento HTTP, persistência/reconciliação, concorrência e semântica de falhas. Não é necessária para o escopo inicial de orquestração da extração.

### Desenho e responsabilidades

| Task proposta | Entrada | Responsabilidade | Saída pequena / regra |
|---|---|---|---|
| prepare_extraction | Configuração da DAG run e contexto Airflow | Validar ciclo, ler endpoint/cadastro em runtime, congelar parâmetros e estabelecer manifesto persistente da rodada | Referência e hash do manifesto, batch_id e cycle_date |
| extract_batch | Referência do manifesto | Chamar núcleo Python, processar todas as localidades sequencialmente, persistir Raw/relatórios incrementalmente e resumo final | batch_id, caminho do resumo e contadores/estado |
| reconcile_extraction | Referências da rodada | Conferir manifesto, resumo, relatórios, vínculos, cobertura e hashes; classificar aceite técnico | Resumo pequeno de reconciliação; falha se parcial, incompleto, conflitante ou sem evidência |

Dependências explícitas: prepare_extraction precede extract_batch; extract_batch precede reconcile_extraction. Regra padrão all_success nas três. Não introduzir task final all_done que possa ocultar falha anterior.

extract_batch pode concluir tecnicamente sua tarefa de coleta/persistência e devolver batch_status=partial_success; reconcile_extraction então falha explicitamente após preservar a evidência. Falha inesperada ou impossibilidade de gravar resumo faz extract_batch falhar e reconcile_extraction ficar upstream_failed. Não existe publicação ou fallback neste fluxo.

## 3. Configuração declarativa da futura DAG

| Item | Recomendação para primeira implementação |
|---|---|
| dag_id | logistics_weather_extract |
| schedule | None |
| Estado inicial | Pausada; is_paused_upon_creation=True e configuração global já existente de criação pausada |
| start_date | 15/10/2026 00:00:00, aware, America/Sao_Paulo; constante, nunca now() |
| catchup | False |
| max_active_runs | 1 |
| max_active_tasks | 1 na DAG, compatível com o fluxo sequencial; sem alterar limites globais do Compose |
| depends_on_past | False |
| retries Airflow | 0 em todas as tasks inicialmente |
| execution_timeout | prepare:1min; extract:12min; reconcile:2min — limites de laboratório propostos, medir e rever no08/09 |
| dagrun_timeout | Proposta de 20min como proteção complementar; comprovar aplicabilidade no modo de execução usado; não assumir garantia para manual |
| Comunicação | Sem e-mail/callback externo nesta fase |

O parâmetro de criação pausada não altera automaticamente uma DAG já cadastrada. O07 deve verificar o estado real persistido. schedule=None impede agenda, mas não é autorização de execução manual. No08, eventual despausa operacional necessária ao processamento exige procedimento central explícito e retorno ao estado pausado; schedule permanece None.

As durações acima são escolhas de projeto propostas, não resultados medidos ou garantia do corte14h15. Qualquer revisão deve constar das evidências.

## 4. Contrato temporal

| Conceito | Significado neste projeto |
|---|---|
| cycle_date / D | Data local do contexto de planejamento; entrada de negócio |
| logical_date | Identidade temporal Airflow; no regime de intervalo cron normalmente representa seu início |
| data_interval | Intervalo de orquestração, distinto da janela meteorológica |
| scheduled_slot | Instante nominal da rodada, quando houver agenda |
| requested_at / collected_at | Instantes reais da solicitação/coleta; coletados pelo extrator, nunca substituídos pelo horário nominal |

### Manual, passos07/08

cycle_date deve ser fornecido como string ISO AAAA-MM-DD em dag_run.conf. Ausência, valor inválido ou chave de configuração desconhecida é erro antes de qualquer HTTP. Não existe default para hoje. O wrapper lê o contexto em runtime e passa um date ao núcleo.

A configuração manual não permite sobrescrever endpoint, caminhos, coordenadas, timezone, IDs, política HTTP ou quantidade de cidades. O conjunto admitido inicialmente contém somente cycle_date. A interface Params pode futuramente apresentar o formulário, mas não deve criar segunda fonte concorrente; a validação runtime continua obrigatória.

logical_date e data_interval são registrados para rastreabilidade; não determinam D numa execução manual. Datas históricas fora da cobertura live são testadas por fixtures; antes do08 escolher ciclo elegível e demonstrar cobertura disponível. start_date não força a data do ciclo nem garante disparo no instante escolhido.

### Janela meteorológica preservada

Ciclo D usa [D16h, D+2 00h), fim exclusivo, America/Sao_Paulo. Limites convertidos para UTC com regras IANA. São normalmente32 horários por localidade, não quantidade fixa em qualquer regra futura de fuso.

collected_at real e imutável por run determina a cobertura exigida: primeira hora cheia igual ou posterior à coleta, limitada pelo início da janela. Coleta18:07 exige a partir19h; coleta18:00:00 exata inclui18h, enquanto fração de segundo posterior já muda o limite. O fim exclusivo ou posterior não produz cobertura completa.

O extrator atual pede a janela inteira e avalia cobertura elegível. Assim, redução da quantidade exigida não obriga a resposta a conter somente horas futuras: 160 linhas podem ainda ser recebidas numa coleta tardia. Distinguir contagem recebida, contagem exigida e contagem faltante, por cidade; não inferir completude apenas do total.

### Proposta para agenda, apenas no09 após autorização específica

Cron candidato: 0 */2 * * *, com timezone da DAG America/Sao_Paulo e sem timetable personalizado inicialmente. Para o comportamento de intervalo cron, o instante nominal é data_interval_end e logical_date corresponde ao início. Contrato recomendado: D = data local de data_interval_end; congelar D na preparação. Exemplo: intervalo local [12h,14h) produz rodada nominal14h para o ciclo daquela data.

Na virada, intervalo [22h da véspera,00h) associa D à nova data. Isso seleciona um único ciclo, mesmo havendo sobreposição das janelas meteorológicas. **Esta é uma decisão de negócio proposta, ainda a ratificar pelo Planeamento antes da agenda.** Não atualizar automaticamente vários ciclos.

Exigir fixtures para virada do dia, rodada14h, atraso do scheduler, fuso e recuperação após computador desligado. Disparo atrasado mantém o slot/ciclo original; não recalcula D usando o relógio da task. catchup=False não promete recuperar todas as rodadas perdidas. Agenda não será habilitada enquanto o contrato temporal e limites do ensaio não forem aceitos.

## 5. Identidades, persistência e retomada

### Invariante central

batch_id identifica a rodada; run_id uma solicitação lógica por cidade; attempt_id cada chamada HTTP; attempt_no a ordem dentro daquele run. HTTP retry mantém batch/run, cria nova tentativa real e não reescreve tentativas passadas. O try_number do Airflow é registrado separadamente e não substitui attempt_no.

Uma nova coleta live representa nova rodada/solicitação e gera novos IDs. Replay significa ler os mesmos arquivos, sem HTTP, preservando IDs, collected_at, bytes e hash. Não chamar uma nova consulta live de replay.

### Lacuna verificada e interface requerida ao06

collect_batch hoje gera UUIDs internamente e o resumo só é gravado ao final pela CLI. Reinvocá-la pode criar uma rodada nova. save_raw_bytes, save_run_report e save_batch_report bloqueiam conteúdo conflitante, mas isso não garante recuperação de processo interrompido.

Propõe-se um manifesto de orquestração separado, sob data/orchestration/, sem mudar schemas Raw/run/batch existentes. Deve conter contexto congelado, batch_id, mapa localidade→run_id e associação ao dag_id/Airflow run_id; nunca segredos. Sua criação em runtime é exclusiva, validada por conteúdo e hash, com gravação atômica para metadados novos. O diretório/protocolo são **adição proposta**, dependente de revisão central, não contrato já implementado.

O06 deverá permitir que o callable receba identidades e snapshots preestabelecidos, mantendo defaults compatíveis com a CLI. Uma fachada Python pura persiste e retorna somente referências; records normalizados podem continuar internos à execução. A implementação deve propor assinatura exata e demonstrar compatibilidade com os73 testes.

Em retomada/reexecução da mesma DAG run:

- Manifesto íntegro existente: reutilizar IDs e snapshots, sem recriar contexto.
- Resumo/relatórios finais íntegros: reutilizar e reconciliar sem nova rede.
- Rodada parcial finalizada: preservar o resultado; nova coleta exige nova DAG run autorizada, novos IDs e vínculo de origem na auditoria de orquestração.
- Execução interrompida com estado ambíguo: bloquear nova coleta automática; inventariar arquivos e devolver incidente ao Planeamento. Não completar silenciosamente o mesmo run após possível resposta já recebida.
- Raw ou relatório conflitante/corrompido: falhar, preservar original e registrar incidente sanitizado. Não sobrescrever nem regenerar com novos timestamps.

Não se promete exactly-once HTTP ou recuperação automática de toda interrupção. Reutilização de IDs não autoriza substituir um relatório imutável para acrescentar nova coleta. Retomada seletiva avançada exigiria novo contrato revisado; fica fora da primeira DAG.

XCom não é armazenamento durável desse estado: uma falha pode ocorrer antes de sua gravação. O vínculo persistente deve sobreviver sem XCom. Concorrência entre CLI e DAG não é bloqueada por max_active_runs; durante validações, impedir operação concorrente por procedimento e tratar colisão de identidade por criação exclusiva. Um lock global cross-CLI seria evolução específica, não garantia existente.

## 6. Retries, timeouts e erros

### Política inicial

| Camada | Política |
|---|---|
| HTTP por cidade | Até3 tentativas no total, timeout conexão10s/leitura30s, esperas1s e2s |
| Erros HTTP repetíveis | Timeout, ConnectionError, HTTP500/502/503/504 |
| Sem repetição automática | HTTP400/429 e demais erros não previstos; validação, conflito e persistência |
| Airflow | retries=0; não repetir a rodada inteira por falha HTTP individual |
| Reexecução manual | Execução de task/clear conta como execução e depende do gate vigente; mesma DAG run não faz nova rede após resultado final |

Teto nominal inicial: cinco cidades × três chamadas =15 chamadas HTTP explícitas por rodada, sem retries adicionais em adapters/wrappers. Confirmar no06/09 por mocks; redirects de transporte devem ser considerados separadamente se observados. Não alterar a política de429 ou adicionar backoff Airflow sem revisão.

Airflow retries=0 é uma decisão técnica recomendada, não ausência de testes de resiliência. O09 comprova os retries HTTP e que reexecução controlada não refaz rede. Se for exigido retry automático do Airflow sobre a task coletora, revisar desenho antes: necessita orçamento global e recuperação persistente que impeça multiplicar coletas/IDs. Alternativa segura futura: retry apenas da reconciliação sem rede.

Timeout de leitura mede espera de leitura, não deadline absoluto. execution_timeout é duração da execução da task; fila, atraso do scheduler e início tardio precisam de análise própria. SLA de notificação não cancela tarefas. Não usar esses mecanismos isoladamente para declarar corte14h15.

### Corte operacional ainda a comprovar

Para rodada nominal14h, deadline é14h15 local daquele slot, convertido em UTC. Antes de cada chamada/espera, a solução futura precisa calcular orçamento restante e impedir início após o corte; chamada já em andamento exige encerramento/cancelamento comprovado. Reduzir timeout ao tempo restante, sozinho, não garante término absoluto.

Esta versão de laboratório não afirma implementar esse controle. No09, ensaio curto pode testar agenda sem prometer atendimento do produto, com essa limitação expressa e autorização central. Aceite operacional de14h15 requer teste de processo/HTTP pendente, atraso de fila e relógio; publicação14h30, frescor e fallback continuam em gates posteriores, sem task placeholder.

### Resultado parcial

| Evidência persistida | Resultado Airflow recomendado |
|---|---|
| Todas cidades validated ou validated_with_nulls e integridade reconciliada | DAG success de extração; alertar nulos explicitamente |
| batch partial_success, cidade incomplete ou failed | DAG failed na reconciliação, preservando resultados disponíveis |
| batch failed | DAG failed |
| Relatório/Raw esperado ausente, hash divergente ou snapshot incoerente | DAG failed; integridade não comprovada |
| Falha de processo/persistência antes de resumo | Task extract failed e downstream upstream_failed; incidente incompleto |

Uma cidade sem resposta HTTP pode legitimamente não ter Raw, mas deve ter falha/tentativas registradas quando a persistência estiver disponível. Se houver resposta, inclusive erroHTTP, conferir referência/hash conforme comportamento existente. Não exigir Raw fictício.

Não tratar validated_with_nulls como publicação, agregado integral ou aptidão universal. Nenhuma task altera disponibilidade analítica.

## 7. XCom, configuração, segurança e observabilidade

XCom JSON pequeno: referências relativas ao projeto, batch_id, cycle_date, estado e contadores. Meta de projeto: até8KiB por retorno serializado; validar no07/08. Sem response.content, hourly, records normalizados, coleção completa de relatórios ou credenciais. O manifesto e resumos ficam nos arquivos.

Referências devem ser resolvidas sob a raiz autorizada, recusando caminhos externos/path traversal. Conferir existência e hash antes de consumo. Não confiar apenas no conteúdo do XCom.

Configuração runtime: WEATHER_ENDPOINT já fornecido pelo Compose; cadastro config/locations.json read-only; timeout/política/campos/unidades continuam os do contrato. Ler dotenv/cadastro somente quando a task executar; não duplicar WEATHER_ENDPOINT em Variable. Não acessar rede, arquivos de cadastro, mkdir, banco, Variable.get ou Connection durante import da DAG/módulos do núcleo.

Nenhuma Variable nova é necessária inicialmente. AIRFLOW_VAR_* fica como alternativa caso surja configuração específica de orquestração; documentar nome/tipo/precedência e ler em runtime. Variables por ambiente não aparecem na UI e prevalecem sobre entradas da UI; ausência na UI não prova ausência de configuração.

Open-Meteo permanece sem API key. WEATHER_DB_* não é usado nesta DAG; não criar Connection weather apenas para simular necessidade. Credenciais/chaves existentes continuam locais. Logs sanitizados por lista permitida, sem despejar .env, ambiente completo, URI de banco, headers ou traceback com valores sensíveis.

Eventos de observabilidade recomendados: preparo, início/fim da rodada, início/fim por cidade, HTTP attempt, persistência confirmada, replay sem rede, conflito, reconciliação e falha parcial. Correlacionar dag_id, Airflow run_id/task_id/try_number, batch/run/attempt, ciclo, slot/intervalo, timestampsUTC, duração, status, contagens exigidas/recebidas/faltantes, nulos, caminhos e hashes. Usar logs locais e relatórios; não configurar notificações externas.

Numa interrupção, logs/artefatos de incidente são melhor esforço. Se o disco não permite gravação, não alegar auditoria persistida: registrar a lacuna e bloquear aceite.

## 8. Critérios de aceite futuros por gate

| Passo | Pré-requisito e verificações | Evidência requerida / limite |
|---|---|---|
| 06 — núcleo/CLI | 05 validado e06 liberado. Callable sem Airflow/argparse/sys.exit, import sem I/O, IDs/snapshots e manifesto revisados; resultados incrementais; CLI preservada;73 testes de regressão e testes novos de identidade/replay/conflito | Output, ambientePython3.10, assinatura, diff/commit e limites. Fixtures/mocks sem API live; mudanças de contrato retornam ao Planeamento |
| 07 — parsing | 06 validado e07 liberado. Um dag_id, exatamente3 tasks e arestas previstas; config/tz/start_date/retries/timeouts; DagBag sem erros; nenhuma rede/SQL/Variable.get/cadastro no import; XCom sem payload; Graph e estado pausado reais | Testes estruturais com I/O do projeto bloqueado ou instrumentado; separar I/O interno do Airflow do efeito do código autoral. Nenhuma DAG run/task executada, nenhuma coleta; schedule=None |
| 08 — manual | 01–07 validados e08 liberado. Confirmar código/imagem/mounts, ciclo elegível, serviços, ausência de conflito e plano de pausa. Uma rodada autorizada, logs e vínculo de IDs, Raw/run/batch/hash reconciliados | JSON/config sanitizado, estado tasks/DAG, contagens porcidade, nulos/cobertura e hashes host/contêiner. Comparar semântica CLI por fixtures; duas consultas live não precisam ter bytes/hashes iguais.160 é referência para janela inicial completa, não aceite universal. Sem SQL e sem agenda |
| 09a — falhas/replay | 08 validado e09 liberado. Fixtures timeout/5xx/400/429, limite de3, falha local não bloqueia outras, nulos, incomplete, disco/conflito, morte antes/depois deRaw/relatório/resumo, replay | Contagem de chamadas, identidades estáveis, zero rede no replay, hashes e arquivos preservados; parcial jamais DAG verde. Provar ausência de reexecução silenciosa com retry0 |
| 09b — agenda | 09a aprovado e autorização separada para ensaio. Ratificar D/data_interval_end e meia-noite; cron/fuso/slot14h/atraso/desligamento; orçamento e critério de parada | Janela limitada, logs scheduler/intervalos/ciclos; sem recuperação histórica live. Encerrar pausada, salvo autorização explícita diferente. Corte14h15 segue aberto se cancelamento não comprovado |
| 10 — Seção4 | Gates anteriores aceitos; runbook, matriz de aceite técnico, README e evidências versionadas | Aceite de extração orquestrada, sem declarar warehouse/publicação. Só Planeamento pode liberar11 |

A matriz de aceite técnico cobre orquestração, TaskFlow, dependências, configuração em runtime, contrato temporal, execução rastreável, logs, separação do núcleo Python, timezone e controle de agenda.

## 9. Decisões submetidas e impactos

| Decisão | Recomendação | Situação |
|---|---|---|
| Granularidade | 3 tasks, coleta sequencial por rodada | Proposta para aceite05 |
| Retry Airflow | 0; HTTP mantém até3 tentativas | Proposta para aceite05 |
| Resultado parcial | Preservar batch parcial; falhar reconciliação | Proposta para aceite05 |
| Identidades/retomada | Manifesto separado e parâmetros opcionais no callable; bloquear estado ambíguo | Proposta com impacto de interface no06 |
| Configuração | conf.cycle_date obrigatório; endpoint por ambiente existente | Proposta para aceite05 |
| Timeout laboratório | 1/12/2min por task, proteção complementar20min | Proposta sujeita a medição08/09 |
| Ciclo agendado | Data local de data_interval_end, incluindo meia-noite | Decisão de negócio pendente antes09b |
| Corte/publicação | Não declarar implementados; comprovar cancelamento antes de aceite operacional | Requisito aberto |

Não há alteração autorizada do contrato R3/DQ. O manifesto é extensão de auditoria de orquestração proposta, não mudança silenciosa dos relatórios existentes. Caso sua adoção implique novos campos obrigatórios nos relatórios ou alterar a semântica de run/attempt, submeter revisão central antes06.

Não há decisão obrigatória em aberto que exija implementar antes de revisar05. O Planeamento pode aceitar a arquitetura proposta ou pedir revisão.06 só inicia com liberação explícita e resolução das decisões que afetam sua interface. Agendamento e requisitos operacionais podem permanecer pendentes até seus gates, com limites explícitos.

## 10. Pacote de devolução ao Planeamento

**CP-2026-10-13 v2 | Passo05 | Airflow — Seção4**  
**Estado:** Passo05 — EVIDÊNCIA SUBMETIDA.

- Artefato: AF-S4-CPv2-P05-v0.1 — este documento.
- Pré-requisitos/autorização: liberação central apresentada por João em15/10;01–02 validados,03–04 com ressalvas; gate Docker encerrado.
- Realizado: análise documental, revisão de código em leitura, desenho das3 tasks, contratos temporal/identidade/XCom, política de falhas/retries, segurança e critérios06–09.
- Verificação: coerência documental com R3/DQ/CPv2 e fontesAirflow2.9.2; sem testes de runtime ou infraestrutura.
- Arquivos: somente docs/15-especificacao-airflow-secao04-v0.1.md, caminho de versionamento confirmado por João.
- Commit desta entrega: consultar o histórico deste arquivo e o relato de publicação. O SHA é gerado na gravação do commit e registrado externamente, evitando autorreferência. 317fa7b é somente a referência consultada e não identifica a entrega deste documento.
- Limitações: propostas não implementadas; ressalvas03/04 preservadas; cancelamento14h15/publicação14h30/frescor/fallback/carga/CI ainda não comprovados.
- Aprovação local: João aprovou a especificação neste chat em15/10/2026 e solicitou a revisão editorial aplicada neste documento.
- Solicitação central: registrar a aprovação, confirmar o alcance das decisões da seção9 e emitir o encaminhamento do06 ao responsável, quando cabível. Não se emite liberação06 neste chat.
- Próxima condição: somente após Planeamento registrar05 VALIDADO e06 LIBERADO, com confirmação de João, encaminhar interface ao chat Custos e APIs.06–11 permanecem NÃO LIBERADOS até essa decisão.

## 11. Referências consultadas

Fontes do projeto, em leitura, não evidência de nova execução:
- CP-2026-10-13 v2, arquivo Texto colado(6).txt.
- Liberação central do passo05 apresentada nesta conversa,15/10/2026.
- [Contrato R3 v0.1](https://github.com/Soba-Jopeca/logistics-weather-data-pipeline/blob/317fa7b/docs/08-contrato-dados-weather-v0.1.md).
- [Matriz DQ v0.1](https://github.com/Soba-Jopeca/logistics-weather-data-pipeline/blob/317fa7b/docs/09-matriz-qualidade-weather-v0.1.md).
- [Extrator](https://github.com/Soba-Jopeca/logistics-weather-data-pipeline/blob/main/scripts/extract_weather.py), [módulo temporal](https://github.com/Soba-Jopeca/logistics-weather-data-pipeline/blob/main/scripts/weather_window.py), [README](https://github.com/Soba-Jopeca/logistics-weather-data-pipeline/blob/main/README.md).
- [Compose baseline](https://github.com/Soba-Jopeca/logistics-weather-data-pipeline/blob/317fa7b/compose.yaml) e [evidência04](https://github.com/Soba-Jopeca/logistics-weather-data-pipeline/blob/317fa7b/docs/14-evidencias-passo04-provisionamento-weather.md).
- Texto colado(8).txt: trecho complementar de logs do ambiente isolado; não substitui a decisão central nem demonstra sozinho reprodução integral.

Referências primárias Airflow2.9.2 usadas como fundamento das escolhas; os valores e políticas deste documento são propostas do projeto:
- [Best practices](https://airflow.apache.org/docs/apache-airflow/2.9.2/best-practices.html): separação de lógica, import sem I/O autoral e dados pequenos entre tasks.
- [DAG Runs](https://airflow.apache.org/docs/apache-airflow/2.9.2/core-concepts/dag-run.html): intervalo/data lógica, catchup e atenção aos estados finais.
- [Variables](https://airflow.apache.org/docs/apache-airflow/2.9.2/howto/variable.html): resolução por ambiente e UI.
- [Tasks](https://airflow.apache.org/docs/apache-airflow/2.9.2/core-concepts/tasks.html): execução, timeouts e limites de SLA.
- [API DAG](https://airflow.apache.org/docs/apache-airflow/2.9.2/_api/airflow/models/dag/index.html): parâmetros declarativos da DAG.
