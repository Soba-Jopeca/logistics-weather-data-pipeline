# Passo07 — DAG de extração e validação estrutural

**Checkpoint:** CP-2026-10-13 v2
**Especificação:** AF-S4-CPv2-P05-v0.1
**Baseline:** 109544ebb30542bc8fb4fbba460a0dca7e55c613
**Liberação central:** apresentada por João em 15/10/2026, restrita à
implementação e validação sem executar tasks.
**Estado:** evidências técnicas consolidadas; conferência Git local final pendente antes da submissão ao Planeamento.
**Atualização:** 16/10/2026 — America/Sao_Paulo.

Passos01–02 e05–06 validados;03–04 com ressalvas;07 liberado;
08–11 NÃO LIBERADOS. Nenhuma execução é autorizada por este documento.

## Arquivos e comportamento

- dags/weather_extract.py: três wrappers TaskFlow sobre o núcleo aprovado.
- tests/test_weather_dag_structure.py: parsing, propriedades e bloqueio de efeitos
  autorais, sem chamar callables das tasks.
- Este documento: comandos e evidências, com pendências explícitas.

Fluxo: prepare_extraction → extract_batch → reconcile_extraction.
Preparação valida conf.cycle_date em runtime e congela contexto temporal.
Extração delega à interface aprovada; reconciliação apenas lê e verifica
artefatos/conclusão e falha se batch_status não for success.
Sucesso técnico não representa publicação analítica ou aptidão integral.

Configuração: schedule=None; criação pausada; start_date=15/10/2026 00h
America/Sao_Paulo; catchup=False; max_active_runs=1; max_active_tasks=1;
depends_on_past=False; retries=0; timeouts1/12/2min e dagrun_timeout20min.
Não são garantias do corte14h15 ou da publicação14h30.

O núcleo Python, os contratos Raw/run/batch, Compose, imagens e PostgreSQL
permanecem sem alterações neste passo. Não foram criadas Variables/Connections.
Os módulos autorais e configurações são carregados somente em runtime.
Retornos XCom são documentos pequenos, com limite explícito de8KiB,
sem payload meteorológico e sem impressão automática dos retornos nos logs.
A eficácia em runtime permanece para08/09; não foi testada executando tasks.

## Comandos documentados antes da validação

### Ambiente isolado do assistente

Sem Docker disponível. Preparação de um venv descartável externo ao repositório,
com Python3.10 e Airflow2.9.2, sem serviços nem migração de metadados.
Instalar dependências nesse venv não altera a imagem de João.
Registrar a versão efetivamente obtida e limitações da comparação.

Sequência de verificações, a partir da raiz do repositório e com o Python
do venv isolado no lugar de python:

```bash
python -m py_compile dags/weather_extract.py tests/test_weather_dag_structure.py
python -m unittest discover -s tests -p test_weather_dag_structure.py -v
git diff --check
```

O teste usa DagBag(read_dags_from_db=False, include_examples=False),
bloqueia execute de operadores e callables, HTTP, Variables, Connections,
conexões SQLAlchemy e I/O de dados do projeto durante parsing.
Bibliotecas Airflow podem ler sua própria configuração/código; isso não
equivale a I/O autoral. Não criar DagRun, TaskInstance ou banco para os testes.
Não executar suíte de comportamento HTTP/replay ou chamar funções de task
neste gate. Testes existentes não são repetidos sem justificativa.

### Procedimento no computador de João

Os comandos foram documentados antes das validações, realizadas após a
sincronização local. As saídas recebidas e a confirmação visual estão
registradas na seção de resultados abaixo. O procedimento não executa tasks.

```powershell
git status
git rev-parse HEAD
docker compose -p logistics-weather ps
docker compose -p logistics-weather exec airflow-scheduler python -c "import airflow, sys; print(airflow.__version__); print(sys.version)"
```

Imports/runtime dos módulos e mounts, sem invocar a extração:

```powershell
docker compose -p logistics-weather exec airflow-scheduler python -c "from pathlib import Path; import scripts.weather_interface as w; print(w.__file__); print('DAG:', Path('/opt/airflow/dags/weather_extract.py').is_file()); print('Cadastro:', Path('/opt/airflow/config/locations.json').is_file()); print('Dados:', Path('/opt/airflow/data').is_dir())"
```

O teste usa somente unittest da biblioteca padrão. Pode ser fornecido por stdin
ao Python do scheduler, sem instalar dependências de teste ou mudar mounts:

```powershell
Get-Content -Raw -Encoding UTF8 tests/test_weather_dag_structure.py | docker compose -p logistics-weather exec -T airflow-scheduler python -c "import sys; filename='/opt/airflow/tests/test_weather_dag_structure.py'; globals()['__file__']=filename; exec(compile(sys.stdin.read(), filename, 'exec'), globals())"
```

O nome de arquivo informado ao compilador resolve a raiz para /opt/airflow;
o teste continua lendo a DAG real montada em dags/, sem criar arquivo em tests/.
Nenhum callable de task será invocado.

Estado real, somente leitura de metadados Airflow, sem SQL autoral:

```powershell
docker compose -p logistics-weather exec airflow-scheduler airflow dags list --output json
```

Confirmar is_paused=true e ausência de agenda para logistics_weather_extract.
Se a DAG já existir despausada, interromper: parâmetro de criação não altera
automaticamente registro existente. Não despausar para inspecionar Graph.

Na UI existente em localhost:8080, abrir a DAG e Graph; confirmar três nós,
arestas sequenciais, schedule=None e pausa. Não usar Trigger/Test/Run/Clear
nem ligar o botão de execução. Se serviços não estiverem ativos ou houver
import error/mount ausente, registrar e avaliar dentro do escopo; não iniciar
infraestrutura ou alterar Compose por iniciativa deste passo.

## Evidências e limitações

### Resultado isolado

Compilação aprovada em Python3.10.22. Airflow2.9.2 instalado em venv
descartável externo ao repositório, usando constraints oficiais3.10 da versão.
Nenhum serviço, imagem ou banco provisionado; nenhuma migração executada.
Dependências desse venv não são idênticas às da imagem; entre outras,
pendulum3.0.0, requests2.31.0 e tzdata2024.1. A imagem existente usa
Python3.10.14 e tzdata2026.5. Não se declara equivalência integral.

Primeira rodada:8 testes estruturais aprovados em2.413s; import_errors vazio,
um único dag_id e três tasks com as arestas/propriedades especificadas.
O parsing passou com os bloqueios de HTTP, socket, conexãoSQLAlchemy,
Variables/Connections e execução de operadores/task bodies ativos.
Nenhum módulo scripts.* foi importado pelo parsing.
Serialização/deserialização da estrutura também aprovada, sem executar tasks.

Após ampliar os bloqueios de arquivos, rodada final:8 testes aprovados
em0.743s. git diff --check aprovado; entrega restrita aos três arquivos
listados, com baseline109544e. A identificação do commit/push será
registrada externamente após sua criação.
Não foram repetidos os149 testes comportamentais da extração neste gate.
No Windows sem Airflow, estes8 testes são explicitamente ignorados;
isso não constitui aprovação de parsing.

### Resultados no ambiente Docker de João

Validações realizadas entre 15 e 16/10/2026, com saídas de terminal
fornecidas por João. Não são resultados inferidos do ambiente isolado.

| Verificação | Evidência recebida |
|---|---|
| Sincronização inicial | Fast-forward local de109544e para220014b, somente3 arquivos/542 inserções |
| Saúde | postgres, airflow-webserver e airflow-scheduler healthy |
| Versões no scheduler | Airflow2.9.2; Python3.10.14 |
| Interface importável | /opt/airflow/scripts/weather_interface.py |
| Arquivo da DAG | /opt/airflow/dags/weather_extract.py: True |
| Cadastro | /opt/airflow/config/locations.json: True |
| Diretório de dados | /opt/airflow/data: True |
| DagBag e testes estruturais |8 testes executados, todos aprovados, em1.403s |
| Import errors | Vazio; verificado pelo teste antes das asserções |
| Pausa real | dags list retornou is_paused="True" |
| Graph e agenda | Confirmados por João:3 nós sequenciais, agendaNone, DAG pausada |
| Execuções criadas | João confirmou nenhuma execução criada |

O teste de importabilidade/caminhos demonstra os caminhos visíveis no
contêiner. Não equivale a nova auditoria completa das definições de mounts.
Nenhuma função de extração foi chamada nessa inspeção.

Saída do teste na imagem existente:

```text
Ran 8 tests in 1.403s
OK
```

Avisos de depreciação de openlineage.client.run e openlineage.client.filter
apareceram na serialização; não houve falha. Não foram alteradas dependências
ou imagens para silenciá-los.

Estado real recebido via dags list:

```json
[{"dag_id":"logistics_weather_extract","fileloc":"/opt/airflow/dags/weather_extract.py","owners":["airflow"],"is_paused":"True"}]
```

A lista comprova a pausa. A ausência de agenda foi comprovada separadamente
pelos testes declarativos e pela confirmação da UI, pois não consta desse JSON.

#### Correção do comando por stdin

A primeira tentativa fornecida ao usuário usou exec com um dicionário de
namespace separado. unittest.main consultou o módulo __main__ real e
encontrou zero testes. O resultado "Ran 0 tests / OK" foi rejeitado como
evidência. O comando desta documentação foi corrigido para usar globals()
do módulo __main__, preservando __file__ para localizar a DAG real.
A segunda tentativa executou efetivamente os8 testes e passou. Não houve
alteração da DAG ou das tasks por causa dessa correção documental.

#### Inspeção visual

João confirmou explicitamente em16/10/2026:
prepare_extraction → extract_batch → reconcile_extraction; schedule=None;
DAG pausada e nenhuma execução criada.

As capturas anexadas não ficaram acessíveis ao assistente. Registrar a
evidência como **inspeção visual confirmada por João**, sem atribuir ao
assistente leitura das imagens. Não foram copiadas capturas para o repositório.

### Versionamento e limites do gate

- Baseline do núcleo:109544e.
- Implementação/testes/documentação inicial:220014ba4f448349d4d4d49091f0eac3ec577841,
  branchmain, publicação remota e pull local confirmados.
- Diff da implementação:3 arquivos,542 inserções; verificação de formatação
  aprovada. Nenhuma mudança de núcleo, Docker ou PostgreSQL.
- Esta atualização altera somente este documento; seu commit é identificado
  externamente após a publicação.
- A confirmação final de sincronização e árvore limpa no computador de João
  será anexada ao relato antes de submetê-lo ao Planeamento.

Nenhuma task, DAG run, coleta, replay de execução, agenda, SQL ou carga
foi executada neste passo. O teste valida estrutura/importação, não o
comportamento futuro das tasks. XCom em execução, reprocessamento, falhas,
deadline14h15 e publicação14h30 continuam sem comprovação neste gate.
Ressalvas dos passos anteriores permanecem registradas.

Após a conferência Git, devolver o pacote como
**Passo07 — EVIDÊNCIA SUBMETIDA**. Somente Planeamento e João podem
registrar07 VALIDADO e liberar08. Passos08–11 continuam NÃO LIBERADOS.
