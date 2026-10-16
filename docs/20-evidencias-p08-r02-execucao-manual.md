# P08-R02 — Segunda execução manual e falha de timeout

**Checkpoint:** CP-2026-10-13 v2
**Especificação:** AF-S4-CPv2-P05-v0.1
**Data:** 16/10/2026 — America/Sao_Paulo
**Estado:** P08-R02 — EVIDÊNCIA SUBMETIDA COM FALHA
**Passo08:** NÃO VALIDADO; integração completa ainda não comprovada.
**Baseline executada:** b7a94ce96ed94ade1038cd46a46def099f7d1bc9
**Run autorizada:** manual_cp_v2_p08_20261016_02

## Autorização e contenção

João apresentou a liberação central de P08-R02, após validação de P08-C01
com limitações documentadas. Autorização restrita a uma nova run manual.
O ciclo, o identificador e o procedimento foram apresentados e confirmados
explicitamente por João antes do trigger.

A primeira execução manual_cp_v2_p08_20261016_01 deveria permanecer failed.
Nenhuma run foi apagada ou recuperada por clear. Após a falha de R02,
o avanço foi interrompido, a pausa restaurada e o diagnóstico feito por
leitura de logs, arquivos e metadados. Não houve correção nem reexecução.
P08-R03, eventuais correções adicionais e passos09–11 não estão liberados.

## Pré-requisitos comprovados

- Branch main, HEADb7a94ce, sincronizada com origin/main, árvore limpa.
- Três serviços healthy; scheduler/webserver recriados na correção anterior;
  PostgreSQL preservado.
- Airflow2.9.2 e Python3.10.14, imagem existente1.0.0, sem alteração neste gate.
- PYTHONPATH=/opt/airflow nos dois serviços Airflow.
- Imports reais a partir de /tmp nos dois serviços, código0.
- scripts.__path__ exclusivamente /opt/airflow/scripts.
- Quatro módulos resolvidos sob /opt/airflow/scripts:
  extract_weather, weather_interface, weather_manifest e weather_window.
- DAG cadastrada, ativa, pausada, schedule_interval=null,
  timetable_description="Never, external triggers only", sem import errors.
- max_active_tasks=1 e max_active_runs=1.
- Histórico inicial contendo somente a run01 em failed; identificador02 disponível.
- Nenhum processo correspondente aos filtros de extração/execução encontrado
  no Windows ou scheduler. Verificação pontual, sem garantia de lock global.
- DAG, módulos e cadastro legíveis; data acessível para leitura/escrita segundo
  os testes de permissões no contêiner.
- Inventário anterior de27 arquivos em data com hashes SHA-256 guardados no
  PowerShell para comparação posterior.

As evidências foram fornecidas por João no terminal local. O assistente não
operou diretamente o Docker do usuário.

O primeiro envio do código de inspeção por argumento -c perdeu aspas internas
no PowerShell e produziu SyntaxError nos dois serviços. Esses comandos não
executaram o bloco de imports. O envio posterior via stdin executou e passou
nos dois serviços, ambos com código0. Isso não criou outra DAG run.

## Ciclo e execução

| Campo | Valor |
|---|---|
| dag_id | logistics_weather_extract |
| Airflow run_id | manual_cp_v2_p08_20261016_02 |
| cycle_date | 2026-10-16 |
| Janela local | [16/10/2026 16h,18/10/2026 00h), America/Sao_Paulo |
| Janela UTC correspondente | [16/10/2026 19h,18/10/2026 03h) |
| Horários inicialmente exigíveis |32 por cidade antes das16h locais |
| Horizonte da API | Janela dentro dos sete dias padrão documentados; sem coleta de teste adicional |
| Agenda | None durante todo o procedimento |

A quantidade recebida e a cobertura deveriam ser avaliadas com collected_at
real. Não se usou160 como prova universal de completude.

João executou uma vez o trigger previamente apresentado:

```powershell
docker compose -p logistics-weather exec airflow-scheduler python -c "import json, subprocess; subprocess.run(['airflow','dags','trigger','logistics_weather_extract','--run-id','manual_cp_v2_p08_20261016_02','--conf',json.dumps({'cycle_date':'2026-10-16'})], check=True)"
```

Resultado: queued, run_type=manual, external_trigger=True, conf.cycle_date
correto, código0. logical_date e data_interval_start/end:
2026-10-16T06:08:22+00:00. Esses instantes não representam a janela meteorológica.

Foi aplicada despausa temporária e consultado o histórico:

```powershell
docker compose -p logistics-weather exec airflow-scheduler airflow dags unpause logistics_weather_extract
docker compose -p logistics-weather exec airflow-scheduler airflow dags list-runs -d logistics_weather_extract --output json
```

## Estados reais

| Elemento | Estado | Início UTC | Fim UTC |
|---|---|---|---|
| DAG run02 | failed | 2026-10-16T06:09:01.947595+00:00 | 2026-10-16T06:09:05.523241+00:00 |
| prepare_extraction | success | 2026-10-16T06:09:03.000759+00:00 | 2026-10-16T06:09:03.353211+00:00 |
| extract_batch | failed | 2026-10-16T06:09:04.184057+00:00 | 2026-10-16T06:09:04.650130+00:00 |
| reconcile_extraction | upstream_failed | 2026-10-16T06:09:04.729377+00:00 | mesmo instante |

O log de extract_batch registra tentativa Airflow1 de1 e uma
AirflowFailException com mensagem genérica de extração bloqueada,
em dags/weather_extract.py. A causa detalhada foi identificada nos
artefatos, não nessa mensagem sanitizada.

Isso comprova avanço em relação ao incidente de imports: a preparação
executou com sucesso após P08-C01. Não comprova conclusão da extração.

## Artefatos, identidades e hashes

Batch:92d9ed15-488d-45b0-8b06-9feb01185229.

| Arquivo novo, relativo ao projeto | SHA-256 calculado no Windows |
|---|---|
| data/orchestration/contexts/6856d96a0879c62ad60ed8cb5991d0902abc6673614bb8aac501614eae5419da/manifest.json | fc91b83c62df5d8a6de990ab00ff102ca3d6d133db2c9cede425324cd57a5ebd |
| data/orchestration/executions/92d9ed15-488d-45b0-8b06-9feb01185229/started.json | 57c581f46b51031744a59a3df2351c640ebb3b710e4f5a5d4cc4fdece0481fcd |
| data/orchestration/incidents/a0d65cc2-cf73-45ac-ba1a-7dce2dff9f4f.json | b11197f2038c1c58fbe9dceb46dc4e01a9754429afc36a244033038ad2e0e24c |
| data/raw/batches/92d9ed15-488d-45b0-8b06-9feb01185229.json | 989b550657fc30882649205c67d8870dcf84e3fb4d86dec5cf193ebe2fa7ca85 |

Manifesto:6322 bytes segundo a listagem recebida. Marca de início:266 bytes.
Incidente:252 bytes, recorded_at=2026-10-16T06:09:04.596761+00:00,
category=artifact_integrity e automatic_collection_blocked=true.

Comparação de inventários por Path/Hash:27 arquivos antes,31 depois,
exatamente quatro entradas novas com SideIndicator=>. Não houve entradas
de remoção ou mudança dos27 anteriores. Portanto, todos os arquivos
preexistentes do inventário foram preservados pelos hashes observados.

Não surgiram Raw individuais, relatórios individuais ou completed.json.
O batch foi iniciado em06:09:04.555318Z e encerrado em06:09:04.566540Z,
com batch_status=failed, location_count=5 e successful_location_count=0.

| Localidade | run_id meteorológico | Estado / report_path |
|---|---|---|
| br_sp_campinas |07972e58-5c6d-4dd5-b307-691894266b38| failed / null |
| br_sp_sao_paulo |021004fb-7675-4b94-b866-c7e5f899d3dd| failed / null |
| br_sp_sorocaba |c3c8ad89-ddf6-47aa-97cc-4828349c65e2| failed / null |
| br_sp_jundiai |7033d239-df32-43aa-bcf0-61f1e109d93f| failed / null |
| br_sp_ribeirao_preto |b32f1c85-0f3f-458f-9408-256af5ed364c| failed / null |

Os cinco resultados contêm error_category=run_execution_error e a mesma causa:

```text
Timeout value connect was [10, 30], but it must be an int, float or None.
```

Não existem respostas meteorológicas persistidas ou contagens de registros
válidos observadas para esta run. Cobertura exigida:32 horários por cidade
naquele instante; cobertura recebida, horários faltantes e nulidade não podem
ser avaliados sem payload. Não preencher essas medidas como zero artificial.
Nenhum attempt_id HTTP foi exposto nos resultados disponíveis; a tentativa
Airflow1 não é um identificador de tentativa HTTP.

## XCom observado no Airflow real

Consulta somente de leitura por ORM do Airflow, para a run02.
O tamanho foi medido sobre a coluna persistida por octet_length(XCom.value).

- task_id:prepare_extraction
- key:return_value
- bytes persistidos:294, abaixo do limite8192
- somente uma entrada retornada para a run na consulta

```json
{
  "manifest_path": "data/orchestration/contexts/6856d96a0879c62ad60ed8cb5991d0902abc6673614bb8aac501614eae5419da/manifest.json",
  "manifest_sha256": "fc91b83c62df5d8a6de990ab00ff102ca3d6d133db2c9cede425324cd57a5ebd",
  "batch_id": "92d9ed15-488d-45b0-8b06-9feb01185229",
  "cycle_date": "2026-10-16"
}
```

O hash coincide com o calculado no Windows; batch/ciclo e caminho coincidem
com os artefatos identificados. Conteúdo restrito a metadados, sem payload
meteorológico ou segredos. As tasks posteriores não produziram retorno
de sucesso observado. Não há comprovação de todos os XComs de uma execução
completa, pois a extração falhou.

O snapshot completo de configuração/cadastro do manifesto não foi reproduzido
nesta análise. Sua existência, hash e vínculos foram conferidos; a validação
integral não terminou e não deve ser declarada aprovada.

## Diagnóstico confirmado e proposta — NÃO APLICADA

Na baselineb7a94ce:

- weather_manifest.build_manifest_document persiste config.timeout como
  list(timeout), representação adequada ao JSON.
- weather_interface.execute_extraction passa manifest["config"] diretamente
  para collect_batch, sem restaurar o tipo esperado pela biblioteca HTTP.
- Requests aceita um número ou tupla(connect,read) como timeout. A lista
  [10,30] chega como valor de conexão inválido e causa ValueError local.
- collect_batch registra os cinco erros em resultados mínimos, sem relatório
  individual. A verificação posterior tenta conferir os artefatos ausentes,
  gerando o incidente artifact_integrity e bloqueando a conclusão.

A causa primária é a incompatibilidade de tipo na passagem da configuração
serializada para execução. Não é diagnóstico de lentidão da Open-Meteo.
Não houve resposta HTTP observada; não foi feita captura de tráfego de rede.

Proposta para autorização central específica de correção, sugerida P08-C02:

1. Validar e reconstruir uma configuração de execução separada, restaurando
   timeout para tupla(10,30) na fronteira JSON→biblioteca HTTP.
2. Preservar bytes/hashes do manifesto, identidades e evidências das duas runs.
   Não editar o JSON persistido como atalho.
3. Acrescentar teste de serialização/leitura até o transporte real Requests,
   com barreira de rede no nível adequado. Mocks de alto nível não devem
   ocultar a validação dos argumentos pelo adapter.
4. Revisar a observabilidade da causa primária e o tratamento de falha antes
   da geração de relatório, preservando o contrato de auditoria.
   Qualquer mudança de schema/status exige revisão central específica.
5. Regressão afetada e parsing sem execução operacional; nenhuma alteração
   Docker requerida a priori para esta incompatibilidade de tipo.
6. Após aceite da correção, eventual nova run exige autorização separada,
   sem clear/replay operacional da execução falha.

Nenhum item da proposta foi implementado neste gate.
Não chamar execute_extraction em diagnóstico: poderia iniciar coleta.

## Estado final e devolução ao Planeamento

A pausa foi restaurada por airflow dags pause, seguida de consulta independente
airflow dags list confirmando is_paused=True. schedule=None não foi alterado.
O histórico mostrou exatamente run02 failed e run01 failed, com os horários
originais da primeira preservados. Nenhum trigger adicional ou clear realizado.

Comandos de evidência utilizados: dags list/details/list-runs,
tasks states-for-dag-run, leitura de log/JSON, inventários Get-FileHash,
inspeção de imports por stdin e consulta ORM de XCom somente em leitura.

**P08-R02 — EVIDÊNCIA SUBMETIDA COM FALHA**

- Falha preservada, contenção executada, causa e limites documentados.
- Passo08 permanece NÃO VALIDADO.
- Solicitação: avaliar proposta P08-C02 com foco na interface Python e
  teste da fronteira com Requests; definir responsáveis e gate de aprovação.
- Nenhuma correção aplicada, nenhuma terceira run autorizada.
- Passos09–11 NÃO LIBERADOS.
- Somente este documento é acrescentado à entrega atual; commit de registro
  identificado externamente após publicação.
- Baseline executadab7a94ce não é o commit deste documento.

## Referências

- [Código da interface na baseline](https://github.com/Soba-Jopeca/logistics-weather-data-pipeline/blob/b7a94ce/scripts/weather_interface.py)
- [Código do manifesto na baseline](https://github.com/Soba-Jopeca/logistics-weather-data-pipeline/blob/b7a94ce/scripts/weather_manifest.py)
- [Requests — API de timeout](https://requests.readthedocs.io/en/latest/api/#requests.request)
- Falha original:docs/18-evidencias-passo08-execucao-manual.md.
- Correção de importação:docs/19-evidencias-p08-c01-imports.md.
