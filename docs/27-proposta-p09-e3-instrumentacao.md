# P09-E3-P03 — Implementação submetida; validação offline BLOQUEADA

Baseline: `70b02b044e36adaa0a29612da87cf8bf688567c9`.
Branch exclusiva: `feat/p09-e3-isolated-harness`.
Data: 25/10/2026 (America/Sao_Paulo).

## Parecer

Não emitir “harness implementado e validado offline”: a regressão não aprovou.
Implementação aditiva dos 13 arquivos do mandato, sem alteração operacional.
A atividade dependente de Airflow fica interrompida por ambiente incompatível.
Nenhuma dependência/intérprete foi instalada para contornar a restrição.
E3, passo 09 e blocos A/B/C continuam NÃO VALIDADOS/NÃO EXECUTADOS.

## Resultados reais

| Conjunto | Aprovados | Falhas | Erros | Skips |
|---|---:|---:|---:|---:|
| Harness (42 casos) | 40 | 2 | 0 | 0 |
| Baseline (295 casos preservados) | 275 | 12 | 8 | 0 |
| Total (337 casos) | 315 | 14 | 8 | 0 |

Regressão final: exit code **1**, duração reportada pelo pytest **5.14 s**.
Nenhum teste foi removido, marcado skip ou teve expectativa reduzida.
As falhas de import são falhas reais da validação, não aprovações condicionais.

## Ambiente e comando

Disponível: CPython 3.12.14. O caminho previamente usado de CPython 3.10.14
não existe mais; os symlinks dos venvs anteriores estão quebrados.
Pacotes preexistentes foram apenas referenciados por PYTHONPATH; nenhuma instalação.
pytest 9.1.1; distribuição Airflow 2.9.2 existente, mas não importável neste runtime.

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=.:../p09-offline-venv/lib/python3.10/site-packages:../airflow-p07-venv/lib/python3.10/site-packages \
AIRFLOW_HOME=/workspace/scratch/5bbc9498ddbd/p09-airflow-synthetic \
AIRFLOW__CORE__LOAD_EXAMPLES=False AIRFLOW__CORE__UNIT_TEST_MODE=True \
python -m pytest -q -p no:cacheprovider tests \
  --junitxml=/workspace/scratch/5bbc9498ddbd/e3-regression-final.xml
```

O autoload de plugins pytest foi desabilitado porque um plugin incidental
(time_machine) exige extensão CPython 3.10. Nenhum teste depende desse plugin;
a suite inteira permaneceu selecionada. Airflow não foi simulado/substituído.

## Ocorrências e correções

- ENV-01: falta do executável CPython 3.10.14. As extensões `_re2` disponíveis
  são CPython 3.10 e não carregam em 3.12. Isso bloqueia 12 testes e causa 8 erros
  de setup Airflow. Sem instalação ou alteração das dependências.
- ENV-02: dois subprocessos dos testes históricos usam ambiente deliberadamente
  reduzido e o sys.executable atual, que não tem requests instalado. O PYTHONPATH
  suplementar do pai é substituído pelo teste. Teste anterior mantido intacto.
- Durante revisão: identidade de slot agendado normalizada para UTC para não
  divergir entre a data aprovada com -03:00 e o data_interval_end em UTC.
- Durante revisão: mount do checkout inteiro substituído por scripts/dags/cadastro
  somente leitura para não carregar .env ou dados operacionais inadvertidamente.
- Durante revisão: timetable tornou-se classe de módulo registrável como plugin;
  serialização ainda depende de aprovação dos testes Airflow bloqueados.
- Durante revisão: guardas de escrita Python restringem cenário e ledger, sem
  autorizar escrita em outros cenários; não substituem ACL/mounts do SO.
- Durante revisão: PostgreSQL recebeu gate de checksum e profile opt-in; scheduler
  usa preflight que verifica e encerra, sem inicialização automática.

## Matriz de cobertura e limites

| Mecanismo | Evidência offline | Limite aberto |
|---|---|---|
| Baseline | hashes fixos de todos scripts, DAG e cadastro; hash alterado rejeitado | Não inspeciona Windows remoto |
| Configuração | campos, raízes disjuntas, gate desabilitado/incompleto, JSON duplicado | Atestação externa não é prova do SO |
| Instrumentação | funções reais de coordenação, qualidade e elegibilidade; sucesso/nulo/replay | Tasks Airflow não executadas |
| Transporte | guarda original chamada; response/timeout sintéticos; destino/fixture inválidos bloqueados | Rede Docker/Windows não ensaiada |
| Replay | batch preservado e contador sem aumento nos testes unitários | Não é E3-B01 operacional |
| Claim interrompido | claim real persistido antes do erro injetado, sem manifesto | Não simula queda de energia |
| Ledger | disputa entre dois processos spawn, orçamento 15/37 e CLI, falha de publicação, lock preservado | Atomicidade Windows/Docker não provada |
| DAG | teste de parsing/graph sem callables preparado | Falha ao importar Airflow |
| Timetable | classe de módulo/plugin e teste de dois slots preparado | Falha ao importar Airflow; scheduler não observado |
| CLI Windows | bloqueio sem evidência ACL/firewall | Confinamento Windows não comprovado |
| Contenção | ledger congelado e evidência retornada | Processo ativo exige intervenção específica autorizada |

Os testes de política chamam funções meteorológicas diretamente com fixtures e
raízes temporárias; não executam tasks, operadores, DAG runs ou CLI operacional.
As tentativas sintéticas unitárias não utilizam o ledger futuro de campanha.
A barreira de rede Python bloqueia sockets no harness e Session.request em toda
suite pelo conftest existente; subprocessos usam controles offline próprios.
Não houve chamada meteorológica real, serviço, banco ou container iniciado.

## Preparação operacional que ainda exige autorização

Os arquivos definem componentes, fontes runtime geradas em memória e interfaces
para adapters de disparo. Não há conexão automática a Docker ou Airflow REST.
Após aprovação offline, ainda será necessário materializar diretórios/segredos,
inspecionar controles reais, inicializar o schema exclusivo sob autorização,
registrar plugin, verificar XCom/serialização e conectar adapter ao ambiente isolado.
O preflight não transforma booleans de evidência em prova de rede/ACL: o operador
não pode inventar atestações para liberar operação. SHA-256 não é assinatura.
A função metadata_gate_contents exige autorização específica para inicialização.
O Compose não é para ser executado nesta fase, nem combinado com o operacional.

## Compatibilidade e rollback

Nenhum dos arquivos de dags/, scripts/, config/, Compose operacional, dependências,
testes antigos e documentação histórica foi alterado. Sem mudança Raw/run/batch.
A branch parte diretamente da baseline; a main não foi movida.
Rollback conservador: não integrar esta branch enquanto bloqueada. Em campanha
futura, congelar e conter apenas produtores identificados, preservar lock/reservas,
artefatos e metadados. Sem down/prune/clear/refund/apagamento de claim.

## Decisão central necessária

Disponibilizar um ambiente offline já compatível (preferência Python 3.10.14 e
Airflow 2.9.2), ou autorizar expressamente restauração desse runtime e reutilização
das dependências existentes. Reexecutar TODOS os testes sem alterar expectativas.
Não autorizar A/B/C com base nos 315 aprovados: os gates Airflow permanecem abertos.

## Inventário e hashes

São 13 novos arquivos: os 12 abaixo e este documento. O hash deste documento
é fornecido no pacote Git, evitando autorreferência.

| Arquivo | SHA-256 |
|---|---|
| `tests/test_e3_harness.py` | `debc9250b8710f0ae8b94f64d9f9268e791dcab7d656a3eb3748301383429ebc` |
| `tools/e3/README.md` | `d16f281a67cd2df47c860a36f95743a66edf553d02690e233c29a257491d2fd4` |
| `tools/e3/campaign.example.json` | `97763b7b3e22336d8d234df84c9a94a2031dd388625b868b0eb7e0d72847455e` |
| `tools/e3/campaign.schema.json` | `1915befd56c4a5105b8c73c340f6d3352c8468be93b7757bb7edd3ac0b2f3a8d` |
| `tools/e3/cli_runner.py` | `68212290d0d1913b4fc7f113e332d2fbedef83acedd45472f8d0bdc97d0fcfb1` |
| `tools/e3/compose.e3.yaml` | `6fdb77e22676c110a00567aa4898c9cf728115c5461be9aa00671439c0c74387` |
| `tools/e3/controller.py` | `4163d292868a6d2f76d3e40d9db13e12c44021602d3f0d02c6fdf96884525b11` |
| `tools/e3/dag_loader.py` | `0be640abd47bda062071eef4c32682b9022d72f6f20eca1abb4c4bb7ed0d1b72` |
| `tools/e3/fixtures.py` | `b42dbbd0f558d18aa719c0d51b812fcaf6bbede65192c679987e115c2c895964` |
| `tools/e3/ledger.py` | `f76115fe7b58c73e606ab7244f16675729b95a410690eff983682d8655270ef4` |
| `tools/e3/preflight.py` | `9d6f1de8ea7217a035adc5d2b1c2aff3e6c71e99f3b44f7b000791484faba8d1` |
| `tools/e3/runtime.py` | `d244d1e2b2f2483326ade6f9fa64600ae1182e6216794ab28934ce81585ac112` |

## Casos não aprovados

| Caso | Estado |
|---|---|
| `tests.test_e3_harness.test_original_dag_parse_only` | failed |
| `tests.test_e3_harness.test_finite_timetable_only_two_slots` | failed |
| `tests.test_weather_dag_structure.WeatherDagStructureTests.test_dag_id_and_exact_task_ids` | error |
| `tests.test_weather_dag_structure.WeatherDagStructureTests.test_dependencies_and_leaf` | error |
| `tests.test_weather_dag_structure.WeatherDagStructureTests.test_no_authorial_import_at_module_top_level` | error |
| `tests.test_weather_dag_structure.WeatherDagStructureTests.test_no_schedule_and_paused_on_creation` | error |
| `tests.test_weather_dag_structure.WeatherDagStructureTests.test_reconciliation_has_no_collection_call` | error |
| `tests.test_weather_dag_structure.WeatherDagStructureTests.test_serialization_without_execution` | error |
| `tests.test_weather_dag_structure.WeatherDagStructureTests.test_taskflow_retries_trigger_rules_and_timeouts` | error |
| `tests.test_weather_dag_structure.WeatherDagStructureTests.test_temporal_and_concurrency_properties` | error |
| `tests.test_weather_interruption.test_f05_interruption_blocks_new_collection_in_fresh_process[after_started-0]` | failed |
| `tests.test_weather_interruption.test_f05_interruption_blocks_new_collection_in_fresh_process[after_raw-1]` | failed |
| `tests.test_weather_timetables.test_t01_timetable_semantics` | failed |
| `tests.test_weather_timetables.test_t02_scheduler_resume_candidates[False-13-44-12-False]` | failed |
| `tests.test_weather_timetables.test_t02_scheduler_resume_candidates[False-13-45-13-True]` | failed |
| `tests.test_weather_timetables.test_t02_scheduler_resume_candidates[False-14-0-13-True]` | failed |
| `tests.test_weather_timetables.test_t02_scheduler_resume_candidates[False-14-1-13-False]` | failed |
| `tests.test_weather_timetables.test_t02_scheduler_resume_candidates[True-13-44-12-False]` | failed |
| `tests.test_weather_timetables.test_t02_scheduler_resume_candidates[True-13-45-13-True]` | failed |
| `tests.test_weather_timetables.test_t02_scheduler_resume_candidates[True-14-0-13-True]` | failed |
| `tests.test_weather_timetables.test_t02_scheduler_resume_candidates[True-14-1-13-False]` | failed |
| `tests.test_weather_timetables.test_t02_previous_completed_interval_prevents_same_candidate` | failed |

## Evidência JUnit reproduzível

SHA-256 XML original: `24880279f71c5194d43d98c0c5912072f8200b63c580498520461e5864d8d928`.
XML integral compactado gzip/base64; contém resultados, não segredos operacionais.
Decodificar base64, descompactar gzip e conferir o hash. A inclusão no documento
preserva evidências sem acrescentar arquivos além dos 13 autorizados.

```text
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
```
