# P08-R03 — Execução manual controlada e reconciliação

## Identificação, autorização e estado

- Projeto: Logistics Weather Data Pipeline.
- Checkpoint: CP-2026-10-13 v2.
- Identificação: AF-CPv2-P08-R03.
- Data da intervenção em São Paulo: 16/10/2026; registros UTC em 17/10/2026.
- Estado de entrega: **P08-R03 — EVIDÊNCIA SUBMETIDA**.
- Baseline executada: `770a7a1f01440bb96443b8cde645b65b8164ea86`.
- Correção Python incorporada: `dfd7820c6e55a2cce8ca70ef1bf92ffe72192057`.
- Branch de execução e de publicação documental: `main`.

O Planeamento central liberou expressamente uma única nova DAG run após validar P08-C02 com limitações. João confirmou neste chat os parâmetros e o procedimento antes do trigger. A autorização permitiu despausa temporária, coleta, inspeção dos artefatos e retorno à pausa, sem alterações de implementação ou infraestrutura.

Passos 01–07 permanecem validados, preservadas as ressalvas 03–04. P08-C01 e P08-C02 permanecem validados com limitações. P08-R02 permanece encerrado com falha documentada. **Passo 08 continua NÃO VALIDADO até revisão central e ratificação de João. Passos 09–11 NÃO LIBERADOS.** Nenhuma nova execução fica autorizada por esta entrega.

Referências históricas preservadas: documentos 15, 17, 18, 19, 20 e 21 em `docs/`. Os estados registrados nos documentos anteriores pertencem aos respectivos momentos; esta entrega não os reescreve.

## Origem das evidências e pré-requisitos

João executou os comandos no PowerShell do Windows, no repositório local, e forneceu saídas textuais. O assistente elaborou os procedimentos, analisou os resultados e consolidou este documento. O ambiente Docker local não foi operado diretamente pelo assistente.

Verificações iniciais e atualização às 22h54 de 16/10, São Paulo:

- `git status`: main limpa, sincronizada com origin/main.
- `git fetch origin`, `git rev-parse HEAD` e `git rev-parse origin/main`: baseline completa acima, igual nas duas referências.
- PostgreSQL, webserver e scheduler healthy.
- Airflow 2.9.2; Python 3.10.14, confirmados nos dois serviços Airflow.
- Imagem dos dois serviços: `jopecadata/logistics-weather-data-pipeline:1.0.0`.
- ID de imagem local dos dois serviços: `sha256:3aef1bab0449408e82325a554aaa882dfbd4077578d99923f10d857744888930`. Esta evidência é o campo Image do docker inspect, sem reinterpretá-lo como digest de manifesto do registry.
- PYTHONPATH efetivo: /opt/airflow.
- Imports iniciados em /tmp, com sys.path[0] simulando /home/airflow/.local/bin: scripts exclusivamente em /opt/airflow/scripts, e extract_weather, weather_interface, weather_manifest e weather_window resolvidos nesse diretório. Código 0 nos dois serviços.
- Arquivos DAG, quatro módulos Python e cadastro legíveis; diretório data acessível para leitura/escrita/travessia.
- DAG cadastrada, is_paused=True, schedule_interval=null, has_import_errors=False, max_active_runs=1, max_active_tasks=1.
- Histórico prévio: somente runs 01 e 02, ambas failed; nenhum run ativo.
- Consulta de processos Windows sem correspondências; consulta psutil no scheduler sem correspondências para extrator/interface/airflow tasks run, código 0. Verificação final de processos antes do trigger: lista vazia, código 0.
- Inventário imediatamente anterior: 31 arquivos de data com caminhos e SHA-256 mantidos na sessão PowerShell.

As verificações de processos são pontuais e limitadas aos contextos examinados. Não comprovam ausência de coletas em computadores externos.

Comandos de inventário dos serviços e configuração:

```powershell
docker compose -p logistics-weather ps
docker inspect logistics-weather-airflow-scheduler-1 logistics-weather-airflow-webserver-1 --format '{{.Name}} | {{.Config.Image}} | {{.Image}}'
docker compose -p logistics-weather exec airflow-scheduler airflow dags details logistics_weather_extract --output json
docker compose -p logistics-weather exec airflow-scheduler airflow dags list-runs -d logistics_weather_extract --output json
```

## Ciclo, elegibilidade e identidade

- DAG: `logistics_weather_extract`.
- Airflow run_id: `manual_cp_v2_p08_20261017_03`.
- cycle_date: `2026-10-17`.
- Janela de negócio São Paulo: [17/10/2026 16h, 19/10/2026 00h).
- Janela UTC: [17/10/2026 19h, 19/10/2026 03h).
- Última amostra horária incluída: 19/10/2026 02h UTC, equivalente a 18/10 às 23h em São Paulo.
- Parâmetros persistidos: start_hour=2026-10-17T19:00, end_hour=2026-10-19T02:00, timezone=GMT, timeformat=unixtime.
- Cinco localidades; 32 horários por cidade exigíveis no instante da coleta, total esperado de 160 registros.

O ciclo candidato 16/10 foi substituído, antes do trigger e com confirmação expressa de João, porque a intervenção foi retomada às 22h52 locais. O ciclo 17/10 mantinha toda a janela futura, dentro do horizonte documentado da API de previsão. A cobertura foi posteriormente confirmada diretamente no Raw, sem coleta adicional para verificar elegibilidade.

Referência técnica: https://open-meteo.com/en/docs

logical_date e os dois limites do data_interval da run manual: `2026-10-17T02:00:42+00:00`. Esse instante corresponde a 16/10 às 23h00m42s locais; não seleciona o ciclo meteorológico. scheduled_slot=null. Não foi implementada seleção automática por agenda.

A leitura do código confirmou que o contexto persistente é identificado pelo SHA-256 da representação canônica de dag_id + airflow_run_id. O novo identificador não constava do histórico e gera contexto distinto de R02, preservando seu batch bloqueado.

## Procedimento efetivamente executado

Uma única criação, código de saída 0:

```powershell
docker compose -p logistics-weather exec airflow-scheduler python -c "import json, subprocess; subprocess.run(['airflow','dags','trigger','logistics_weather_extract','--run-id','manual_cp_v2_p08_20261017_03','--conf',json.dumps({'cycle_date':'2026-10-17'})], check=True)"
```

Retorno inicial queued, external_trigger=True. Despausa temporária, código 0:

```powershell
docker compose -p logistics-weather exec airflow-scheduler airflow dags unpause logistics_weather_extract
docker compose -p logistics-weather exec airflow-scheduler airflow dags list-runs -d logistics_weather_extract --output json
docker compose -p logistics-weather exec airflow-scheduler airflow tasks states-for-dag-run logistics_weather_extract manual_cp_v2_p08_20261017_03 --output json
```

Após término, pausa restaurada, código 0, seguida de consulta independente de details com código 0:

```powershell
docker compose -p logistics-weather exec airflow-scheduler airflow dags pause logistics_weather_extract
docker compose -p logistics-weather exec airflow-scheduler airflow dags details logistics_weather_extract --output json
```

A tabela imediata dos comandos pause/unpause exibiu o estado anterior. Consultas independentes confirmaram a pausa final. Não se repetiu o trigger por causa dessas tabelas.

## Estados, tempos e logs

Tempos abaixo em UTC:

| Elemento | Início | Fim | Estado |
|---|---|---|---|
| DAG run | 2026-10-17 02:01:39.979937 | 02:01:48.170237 | success |
| prepare_extraction | 02:01:41.489398 | 02:01:41.849827 | success |
| extract_batch | 02:01:42.187966 | 02:01:46.281255 | success |
| reconcile_extraction | 02:01:47.390685 | 02:01:47.802904 | success |

Duração observada da DAG run: aproximadamente 8,19 segundos, sem generalização para SLA.

Logs das três tasks: Starting attempt 1 of 1, Marking task as SUCCESS e Task exited with return code 0. Jobs Airflow 10, 11 e 12, respectivamente. Retornos das funções ocultos nos logs pela configuração existente. Reconciliação registrou batch, ciclo, status=success, localidades=5/5, registros=160 e nulos=0.

Os comandos airflow tasks run presentes nos logs foram emitidos internamente pelo executor durante a run autorizada; não foram invocados como testes ou execuções adicionais pelo operador.

Leitura dos logs:

```powershell
$p08R03LogRoot = '.\logs\dag_id=logistics_weather_extract\run_id=manual_cp_v2_p08_20261017_03'
foreach ($task in @('prepare_extraction', 'extract_batch', 'reconcile_extraction')) {
    Get-Content -LiteralPath "$p08R03LogRoot\task_id=$task\attempt=1.log" -Encoding UTF8 -Tail 35
}
```

## XComs observados

Consulta ORM somente de leitura ao XCom real, com create_session, XCom.get_many filtrado por DAG/run/key e octet_length(XCom.value). Código 0, três retornos.

| Task / return_value | Bytes persistidos | Conteúdo |
|---|---:|---|
| prepare_extraction | 294 | manifesto, SHA-256, batch_id, cycle_date |
| extract_batch | 625 | referências, identidades, status/contadores, completion_path, mode=new_collection |
| reconcile_extraction | 281 | batch/ciclo, status/contadores e referência do relatório |

Todos menores que 8192 bytes. Sem payload meteorológico completo ou segredos visíveis. Contadores de extração/reconciliação: location_count=5, successful_location_count=5, record_count=160, null_count=0, batch_status=success. IDs e hash do manifesto coincidem entre retornos e arquivos.

## Manifesto e persistência

Batch: `21a17b01-e987-4711-9195-351e87fed9a9`.

Manifesto: `data/orchestration/contexts/2d71854063cdb529defdc4839dcfd4f84f80fdfc3a646f896760eb48ff8d30c9/manifest.json`.

SHA-256: `ef4c0e1291933876f256b8a916bd472a01c6435709f9717be1ea070f28cb912f`.

Snapshots conferidos: cinco localidades, suas coordenadas e timezone America/Sao_Paulo; endpoint https://api.open-meteo.com/v1/forecast; timeout JSON [10,30]; ciclo, parâmetros de cada solicitação, IDs por localidade e contexto Airflow. O timeout permanece array JSON no manifesto. A reconstrução como tupla em memória é objeto da correção e dos testes C02; nesta execução não se instrumentou o argumento HTTP para imprimir seu tipo.

Marca started.json em `data/orchestration/executions/21a17b01-e987-4711-9195-351e87fed9a9/`: started_at=2026-10-17T02:01:42.564472+00:00, vinculada ao manifesto. completed.json contém o mesmo manifest_sha256 e claim_sha256 igual ao hash de started.json, além do resultado e de 11 hashes de artefatos.

O hash final do manifesto coincide com o recebido em XCom pela preparação, permitindo conferir sua preservação até a inspeção final.

## Localidades, IDs e qualidade

| Localidade | run_id meteorológico | attempt_id HTTP |
|---|---|---|
| Campinas | 2df8b63d-6428-4d71-bee2-7d52dba53695 | c42d0013-d839-4215-b4d8-131af83b4e93 |
| São Paulo | 5e15151f-4683-421d-9df6-c38ff4eb7989 | 7c7c226b-0474-4710-81d5-205d6461b410 |
| Sorocaba | 9c7e30ff-a387-4823-86eb-da751e69ae6d | 3e13aab3-6d80-408e-809d-d2e937346331 |
| Jundiaí | f66d71ce-6856-4195-b1ee-14b1251949fa | e0dc4917-fd26-40a7-ba26-023a25b549af |
| Ribeirão Preto | 4c84098c-07da-4f4b-b505-29de3d603e7a | a2259153-6fd9-4b82-b2f9-bc366e1c4dff |

Cada localidade: uma tentativa HTTP, attempt_no=1, HTTP 200, run_status=validated; 32 recebidos e 32 exigidos; coverage_complete=true; missing_times_utc e outside_window_times_utc vazios. Zero nulos em temperature_2m, precipitation e wind_speed_10m.

Coletas entre 2026-10-17T02:01:43.352817+00:00 e 02:01:46.049940+00:00, anteriores ao início da janela de previsão. Tentativa HTTP e tentativa da task Airflow são identificadores diferentes.

Raw por localidade: `data/raw/weather_<run_id meteorológico>.json`.
Relatório individual: `data/raw/runs/<run_id meteorológico>.json`.
Batch: `data/raw/batches/21a17b01-e987-4711-9195-351e87fed9a9.json`.

## Conferência independente e hashes

Leitor diagnóstico via Python -B e entrada padrão no scheduler, sem invocar funções de extração, tasks ou HTTP:

- Recalculou os 11 SHA-256 declarados em completed.json.
- Abriu os cinco relatórios individuais e comparou seu conteúdo integral com as respectivas entradas do batch.
- Conferiu batch_id, run_status e o conjunto exato das cinco localidades.
- Abriu os cinco Raw e acessou raw["hourly"].
- Comparou a lista de timestamps, em ordem, com as 32 horas UTC previstas.
- Conferiu comprimentos das três séries e ausência de valores None.

Resultado final: **PASS: hashes, cinco localidades, relatórios e cobertura Raw**, código 0.

Hashes dos 14 arquivos novos (prefixos abaixo relativos a data/):

| Arquivo | SHA-256 |
|---|---|
| orchestration/contexts/2d71854063cdb529defdc4839dcfd4f84f80fdfc3a646f896760eb48ff8d30c9/manifest.json | ef4c0e1291933876f256b8a916bd472a01c6435709f9717be1ea070f28cb912f |
| orchestration/executions/21a17b01-e987-4711-9195-351e87fed9a9/started.json | bdc23d14ed7be9594a8f1decda1bf22dfe52d6845ef6bf4d5065fc9e8d078d98 |
| orchestration/executions/21a17b01-e987-4711-9195-351e87fed9a9/completed.json | e09e6048c8bf2dca24a2205909b086099664e33b3d0820d9b4d4b5565fac7b8a |
| raw/batches/21a17b01-e987-4711-9195-351e87fed9a9.json | 7d8b8e6be8ba154749966db2e94d847a13e00595c01b6adf0fdc7656106ab86d |
| raw/weather_2df8b63d-6428-4d71-bee2-7d52dba53695.json | 1e2e415f50328b42ee733f93a1cb72b51d971851252b5d57bf673da1cf1a6eea |
| raw/weather_5e15151f-4683-421d-9df6-c38ff4eb7989.json | f9cf89c12baa39879b167dcb57713609ed3580792eaad3f225391fb783691748 |
| raw/weather_9c7e30ff-a387-4823-86eb-da751e69ae6d.json | 57694ba81205814ab453ff63277fad73799f7493b02d26db56ca82d68c0ecde1 |
| raw/weather_f66d71ce-6856-4195-b1ee-14b1251949fa.json | 98023882e7d746a6f318f679860afc3f2432df0c36f20f114c1f187d9780ca42 |
| raw/weather_4c84098c-07da-4f4b-b505-29de3d603e7a.json | 0c58d711eda648b96f334a779d1270d9e2966ccf0030f3a55884cc8d809e6e81 |
| raw/runs/2df8b63d-6428-4d71-bee2-7d52dba53695.json | a3eca4c9b32e78f02d72c001da1884ae90bb3f5be7c3a73eb7b564efbc377a64 |
| raw/runs/5e15151f-4683-421d-9df6-c38ff4eb7989.json | 367fa29bfbed81deb6d5f03f285bfc0a9c45643cc8374e66d2ed63c826c9dfc9 |
| raw/runs/9c7e30ff-a387-4823-86eb-da751e69ae6d.json | b2a400f49d35c78bdd5bde7060e7d3c1f543787331c176a60d8540a2e00789f3 |
| raw/runs/f66d71ce-6856-4195-b1ee-14b1251949fa.json | 11b3dca49835f313f56ac7e428ad8378080d0b7970f3cfa383cbe2d23b9b108f |
| raw/runs/4c84098c-07da-4f4b-b505-29de3d603e7a.json | ac7516a945c447950602a29a5ada873ad8a7a1b5d0e6b467f5c0109baf805bbd |

Inventário PowerShell antes/depois via Get-ChildItem -Recurse -File, Get-FileHash SHA256 e Compare-Object -Property Path,Hash: **31 → 45**, somente 14 entradas =>, nenhuma <=. Portanto, os 31 arquivos anteriores mantêm caminho e conteúdo. As 14 adições correspondem a manifesto, início, conclusão, cinco Raw, cinco relatórios individuais e um batch. Nenhum novo arquivo de incidente foi observado nessa comparação.

## Ocorrência no diagnóstico

A primeira versão do leitor independente procurava recursivamente um dicionário com as chaves time e as três variáveis. Encontrou tanto hourly_units quanto hourly e terminou com AssertionError após conferir os 11 hashes, código 1.

Inspeção somente de leitura confirmou que hourly_units contém unidades e hourly contém listas de 32 valores. O leitor foi corrigido para acessar explicitamente raw["hourly"] e então passou, código 0. Esta ocorrência pertence ao diagnóstico elaborado pelo assistente; não constitui falha da DAG, coleta repetida ou mudança de código do projeto.

## Contenção final e limites

Consultas finais, códigos 0:

```powershell
docker compose -p logistics-weather exec airflow-scheduler airflow dags list --output json
docker compose -p logistics-weather exec airflow-scheduler airflow dags list-runs -d logistics_weather_extract --output json
git status --short
```

DAG pausada. details após pausa confirmou schedule_interval=null e has_import_errors=False. Histórico final contém exatamente três runs: 01 failed, 02 failed e R03 success. Nenhuma run anterior foi apagada, reiniciada ou alterada. git status --short final sem entradas, antes da nova entrega documental.

Não foram alterados DAG, núcleo Python, Compose, imagem, dependências ou PostgreSQL nesta intervenção. Não houve clear, dag.test, tasks test, ensaio deliberado de falhas/retries, agenda, SQL, carga ou publicação. Os artefatos meteorológicos permanecem no volume local; este commit publica documentação, não os dados Raw nem os logs completos.

A compatibilidade com a semântica da CLI foi confrontada pelos contratos e artefatos existentes, sem executar uma segunda coleta CLI em paralelo. Não se afirmou equivalência byte a byte com respostas obtidas em outro instante. Replay e retries não foram ensaiados operacionalmente nesta run.

Esta evidência comprova a extração e a reconciliação desta rodada. Não comprova publicação analítica, disponibilidade em warehouse, SLA, corte das 14h15, publicação às 14h30, fallback ou conclusão integral do pipeline.

## Versionamento e devolução ao Planeamento

Único arquivo desta entrega: `docs/22-evidencias-p08-r03-execucao-manual.md`. O commit documental é distinto da baseline de execução 770a7a1; seu hash será informado no encaminhamento após publicação. Sincronização da cópia Windows com esse commit deverá ser confirmada separadamente.

**P08-R03 — EVIDÊNCIA SUBMETIDA.** A recomendação de validação do passo 08 pertence ao Planeamento central; a ratificação final pertence a João. Não avançar para o passo 09 sem nova liberação.
