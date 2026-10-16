# Passo08 — Primeira execução manual e incidente de importação

**Checkpoint:** CP-2026-10-13 v2
**Especificação:** AF-S4-CPv2-P05-v0.1
**Data:** 16/10/2026 — America/Sao_Paulo
**Responsável:** Airflow — Seção 4
**Estado:** Passo08 — EVIDÊNCIA SUBMETIDA COM FALHA; objetivo técnico não concluído.
**Gate:** autorização de uma única DAG run utilizada; nenhuma reexecução autorizada.
**Baseline executada:** 9fa3ff75339fe4862e16299f404aed9ce67b6003.
**Implementação da DAG:** 220014ba4f448349d4d4d49091f0eac3ec577841.

A liberação central apresentada por João validou01–02 e05–07,
preservou ressalvas03–04 e autorizou exclusivamente uma execução manual.
Passos09–11 permanecem NÃO LIBERADOS. Este registro não valida o passo08
nem autoriza correção de configuração, mudança de código ou nova execução.

## 1. Pré-requisitos e parâmetros

Evidências de terminal fornecidas por João:

- Branch main, HEAD9fa3ff7, sincronizada com origin/main e árvore limpa.
- PostgreSQL, webserver e scheduler healthy.
- Imagem declarada: jopecadata/logistics-weather-data-pipeline:1.0.0.
- Saída de docker inspect para .Image:
  sha256:3aef1bab0449408e82325a554aaa882dfbd4077578d99923f10d857744888930.
  Registrar como valor reportado pelo contêiner; não reinterpretar seu tipo.
- Airflow2.9.2, Python3.10.14.
- Interface visível em /opt/airflow/scripts/weather_interface.py.
- Arquivo DAG, cadastro e diretório data confirmados no scheduler.
- DAG cadastrada, ativa e pausada; schedule_interval=null,
  timetable_description="Never, external triggers only", sem import errors.
- max_active_tasks=1, max_active_runs=1, sem próximo disparo agendado.
- Lista de DAG runs inicial vazia.

Checagem pontual de concorrência: nenhum Python correspondente encontrado
no Windows e lista vazia de processos correspondentes no scheduler por psutil.
A primeira consulta por ps falhou porque o utilitário não existe na imagem;
não foi instalada dependência. Esses filtros não constituem lock global
nem inspeção de todos os possíveis processos de outros contêineres/hosts.

Parâmetros apresentados antes do trigger:

| Campo | Valor |
|---|---|
| dag_id | logistics_weather_extract |
| Airflow run_id | manual_cp_v2_p08_20261016_01 |
| cycle_date | 2026-10-16 |
| Janela local | [16/10/2026 16h,18/10/2026 00h), America/Sao_Paulo |
| Agenda | None durante todo o procedimento |

Elegibilidade proposta com base no horizonte documentado da API:
janela futura de aproximadamente dois dias, dentro dos sete dias padrão.
Não foi feita coleta live adicional para testar a cobertura.
A elegibilidade temporal não garante resposta, completude ou ausência de nulos.

## 2. Procedimento realizado

Foi criada uma única run, ainda com a DAG pausada, pelo comando previamente
apresentado a João:

```powershell
docker compose -p logistics-weather exec airflow-scheduler python -c "import json, subprocess; subprocess.run(['airflow','dags','trigger','logistics_weather_extract','--run-id','manual_cp_v2_p08_20261016_01','--conf',json.dumps({'cycle_date':'2026-10-16'})], check=True)"
```

A saída confirmou conf.cycle_date=2026-10-16, external_trigger=True,
run_type=manual, logical_date=2026-10-16T03:59:26+00:00 e estado queued.
data_interval_start e data_interval_end coincidiram com esse instante,
distintos da janela meteorológica do ciclo.

João executou a despausa temporária prevista:

```powershell
docker compose -p logistics-weather exec airflow-scheduler airflow dags unpause logistics_weather_extract
docker compose -p logistics-weather exec airflow-scheduler airflow dags list-runs -d logistics_weather_extract --output json
```

A listagem seguinte mostrou estado failed. Nenhum segundo trigger,
dag.test, tasks test, clear ou retry manual foi realizado.

## 3. Estados e log

| Elemento | Estado | Início UTC | Fim UTC |
|---|---|---|---|
| DAG run | failed | 2026-10-16T04:00:06.481928+00:00 | 2026-10-16T04:00:09.747903+00:00 |
| prepare_extraction | failed | 2026-10-16T04:00:08.114524+00:00 | 2026-10-16T04:00:08.344535+00:00 |
| extract_batch | upstream_failed | 2026-10-16T04:00:08.422169+00:00 | mesmo instante |
| reconcile_extraction | upstream_failed | 2026-10-16T04:00:08.693810+00:00 | mesmo instante |

Estados obtidos por:

```powershell
docker compose -p logistics-weather exec airflow-scheduler airflow tasks states-for-dag-run logistics_weather_extract manual_cp_v2_p08_20261016_01 --output json
```

O log foi lido no bind mount do Windows:

```powershell
Get-Content -LiteralPath 'logs/dag_id=logistics_weather_extract/run_id=manual_cp_v2_p08_20261016_01/task_id=prepare_extraction/attempt=1.log' -Tail 100
```

Trecho relevante fornecido por João:

```text
Starting attempt 1 of 1
File "/opt/airflow/dags/weather_extract.py", line 48, in prepare_extraction
    from scripts.extract_weather import load_api_config, load_locations
ModuleNotFoundError: No module named 'scripts.extract_weather'
Task exited with return code 1
```

A falha ocorreu no import, antes da leitura de conf pela task e antes da
chamada à interface prepare_extraction. A task extract_batch não executou.
O log disponível não mostra execução da coleta meteorológica por esta run.

## 4. Contenção e pausa final

Após a falha foi aplicado o retorno à pausa:

```powershell
docker compose -p logistics-weather exec airflow-scheduler airflow dags pause logistics_weather_extract
docker compose -p logistics-weather exec airflow-scheduler airflow dags list --output json
```

As tabelas imediatas de unpause/pause exibiram respectivamente True/False,
por isso não foram usadas isoladamente para afirmar o estado persistido.
A consulta independente posterior confirmou:

```json
[{"dag_id":"logistics_weather_extract","fileloc":"/opt/airflow/dags/weather_extract.py","owners":["airflow"],"is_paused":"True"}]
```

Estado final comprovado: DAG pausada, run failed e schedule mantido None.
Não houve alteração de código, imagem, Compose ou PostgreSQL como tentativa
de recuperação.

## 5. Diagnóstico de importação

Foi realizada somente comparação de resolução de módulos, sem task:

```powershell
docker compose -p logistics-weather exec airflow-scheduler python -c "import importlib.util as u, sys; import airflow; print('Contexto python-c:', u.find_spec('scripts')); sys.path[0]='/home/airflow/.local/bin'; print('Contexto console simulado:', u.find_spec('scripts')); print('Caminhos simulados:', sys.path)"
```

Resultado recebido:

```text
Contexto python-c:
NamespacePath(['/opt/airflow/scripts',
'/home/airflow/.local/lib/python3.10/site-packages/scripts'])

Contexto console simulado:
NamespacePath(['/home/airflow/.local/lib/python3.10/site-packages/scripts'])

Caminhos simulados:
['/home/airflow/.local/bin', '/usr/local/lib/python310.zip',
'/usr/local/lib/python3.10', '/usr/local/lib/python3.10/lib-dynload',
'/home/airflow/.local/lib/python3.10/site-packages',
'/opt/airflow/dags', '/opt/airflow/config', '/opt/airflow/plugins']
```

**Conclusão sustentada:** a substituição do caminho inicial faz desaparecer
/opt/airflow/scripts da resolução do namespace. O console simulado encontra
somente scripts em site-packages. Isso é coerente com o ModuleNotFoundError
comprovado no processo real da task.

**Limite:** o sys.path do processo real já encerrado não foi capturado.
A comparação é uma simulação explicativa, não leitura retrospectiva desse
processo. A existência de outro namespace scripts é comprovada; não se
atribui toda a falha a uma colisão de pacote sem evidência adicional.

Na configuração versionada, working_dir=/opt/airflow e o bind mount de
scripts não são acompanhados de PYTHONPATH explícito. A pasta scripts
não contém __init__.py versionado. Airflow inclui dags/config/plugins em
seu caminho; não garante incluir a raiz do projeto só por ela ser working_dir.

Os testes do07 comprovaram parsing sem I/O, e deliberadamente não importaram
o núcleo em runtime. O import por python -c também dependeu do contexto.
Portanto, o aceite07 não comprovou importabilidade pelo processo de execução
da task. Essa lacuna fica registrada sem invalidar silenciosamente o histórico
ou declarar teste de runtime anterior inexistente.

## 6. Evidências não produzidas e limitações

- Não há batch/run meteorológico/attempt HTTP observado nesta execução:
  a preparação falhou antes de chamar a interface.
- Contagens, cobertura das cinco cidades e hashes de novos Raw não foram
  produzidos nem reconciliados por esta DAG run.
- Manifesto, relatórios de run/batch e conclusão não foram observados como
  resultado desta run. Não foi feito inventário exaustivo do diretório data;
  artefatos históricos não devem ser atribuídos a esta execução.
- Nenhum retorno XCom de sucesso foi observado; o conteúdo do metastore XCom
  não foi inspecionado neste diagnóstico.
- Não houve comprovação da integração Airflow→extrator, publicação, SLA,
  frescor ou fallback.
- Ressalvas herdadas de03–04 e demais limitações anteriores permanecem.

O fracasso de integração é o resultado real da execução autorizada.
Não é evidência de sucesso técnico ou conclusão do passo08.

## 7. Proposta de correção para revisão central — NÃO EXECUTAR

Recomenda-se que o Planeamento defina uma correção controlada de
empacotamento/caminho de imports, sem mover a lógica para dags:

1. Revisar a inclusão explícita de /opt/airflow no PYTHONPATH dos serviços
   Airflow por configuração compartilhada, preservando eventuais valores
   necessários existentes. Isso altera Compose e exige encaminhamento ao
   responsável Docker e autorização central para aplicar/recriar os serviços.
2. Revisar scripts/__init__.py como pacote explícito, evitando a fusão
   implícita com scripts de site-packages. Isoladamente, esse arquivo não
   resolve ausência da raiz no caminho.
3. Verificar os quatro imports a partir de diretório externo à raiz,
   na configuração de console efetiva e em cada serviço necessário,
   sem executar funções de coleta ou tasks.
4. Repetir somente as verificações estruturais afetadas e preservar CLI,
   contratos, manifests, IDs e janela meteorológica.
5. Após evidências da correção e nova ratificação central, autorizar
   separadamente outra run identificada como nova execução.
   Não reutilizar a run falha por clear ou ocultar seu resultado.

As decisões1–2 são propostas concretas, não implementação aprovada.
Alternativa de longo prazo: pacote instalável com nome exclusivo do projeto;
mudaria distribuição/imagem e precisa de avaliação de escopo própria.
Não adicionar correção ad hoc de sys.path no topo da DAG neste passo.

## 8. Devolução ao Planeamento

**CP-2026-10-13 v2 | Passo08 — EVIDÊNCIA SUBMETIDA COM FALHA**

- Uma run autorizada criada e encerrada em failed.
- Causa imediata: ModuleNotFoundError na preparação; demais tasks upstream_failed.
- Pausa restaurada e confirmada; schedule=None preservado.
- Somente documentação acrescentada após o diagnóstico.
- Nenhuma correção operacional ou reexecução realizada.
- Registro: docs/18-evidencias-passo08-execucao-manual.md.
- Commit documental identificado externamente após publicação, distinto
  da baseline9fa3ff7 e da implementação220014b.
- Solicitação: registrar bloqueio de conclusão08, avaliar a proposta de correção,
  definir responsáveis/escopo e emitir liberação específica de correção e,
  posteriormente, nova autorização de execução.
- Passos09–11 NÃO LIBERADOS.

## Referências técnicas

- [Airflow2.9.2 — Modules Management](https://airflow.apache.org/docs/apache-airflow/2.9.2/administration-and-deployment/modules_management.html):
  sys.path, pastas adicionadas por Airflow, PYTHONPATH e pacotes explícitos.
- [Open-Meteo — Forecast API](https://open-meteo.com/en/docs):
  horizonte e limites horários; não substitui validação da resposta efetiva.
