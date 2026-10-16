# P08-C02 — Correção da fronteira JSON → Requests

## Identificação e autorização

- Projeto: Logistics Weather Data Pipeline.
- Checkpoint: CP-2026-10-13 v2.
- Data: 16/10/2026.
- Responsável: Custos e APIs Gratuitas.
- Validação complementar: Airflow — Seção 4.
- Baseline: b7a94ce96ed94ade1038cd46a46def099f7d1bc9.
- Estado: evidências consolidadas; versionamento e submissão central pendentes.

João aprovou expressamente a proposta antes das alterações, incluindo
a reconstrução do timeout em memória e o tratamento da classificação
secundária do incidente.

A intervenção não autoriza nova execução operacional.

## Diagnóstico

A configuração original utiliza timeout como tupla: (10, 30).

O manifesto representa esse valor como array JSON: [10, 30].
A desserialização recupera uma lista Python.

Antes da correção, execute_extraction entregava manifest["config"]
diretamente a collect_batch. A lista chegava ao Requests, cuja validação
não a interpreta como o par de tempos de conexão e leitura.

Os mocks anteriores substituíam a chamada HTTP antes dessa validação
interna. Por isso, a suíte anterior não detectava a incompatibilidade.

## Correção implementada

Arquivo: scripts/weather_interface.py.

Nova função:

    build_execution_config(manifest_config)

A função valida a estrutura da configuração, o endpoint e a política
de timeout aprovada. Rejeita tipos inadequados, booleanos, valores não
finitos, valores não positivos e tempos diferentes de 10 e 30 segundos.

Retorna um novo dicionário com timeout como tupla, sem modificar
a configuração recuperada do manifesto.

Em execute_extraction:

- A reconstrução ocorre antes de claim_extraction.
- collect_batch recebe a configuração de execução reconstruída.
- O caminho de replay permanece sem nova coleta.
- Não há regravação ou migração dos manifestos existentes.

As assinaturas públicas existentes e os contratos Raw/run/batch
foram preservados.

## Classificação secundária do incidente

O erro original podia escapar da tentativa HTTP e ser registrado por
collect_batch como run_execution_error, sem relatório individual.

A verificação posterior procurava esse relatório e classificava
o incidente como artifact_integrity.

Foi adicionada uma verificação após a persistência do resumo e antes
da verificação de integridade. Resultados com run_execution_error
e report_path ausente interrompem o fluxo com a categoria existente
execution_error.

A causa original permanece no resumo da rodada. Não são criados
novos schemas, categorias ou estados de negócio. Os demais caminhos
continuam sujeitos à verificação de integridade.

## Arquivos de implementação e testes

- scripts/weather_interface.py:
  conversão em memória e tratamento da classificação secundária.
- tests/test_weather_timeout.py:
  novo arquivo com 16 testes.
- tests/test_weather_execution.py:
  teste adicional da preservação da causa original.

## Cobertura adicionada

- Serialização e desserialização do timeout.
- Lista no manifesto e tupla na configuração de execução.
- Preservação da configuração original.
- Rejeição de timeouts inválidos.
- Reprodução do erro original usando o adaptador real do Requests.
- Sucesso com a tupla reconstruída.
- Integração de manifesto temporário até o transporte Requests.
- Cinco cidades e 160 registros simulados.
- Preservação do manifesto e de seu hash.
- Replay sem modificação dos arquivos temporários.
- Preservação da causa primária e ausência de marca de conclusão
  quando faltam relatórios por falha de execução.

Os testes da fronteira não substituem Session.send ou HTTPAdapter.send.
O transporte urllib3 é interceptado e as conexões de socket são bloqueadas.

Todos os manifestos executados pelos novos testes são temporários.
Não foi executado execute_extraction com os manifestos reais anteriores.

## Resultados no Windows

Ambiente: venv local, Python 3.13 e pytest 8.3.3.

Comandos:

    python -m pytest tests -q -rs
    python -B -m scripts.extract_weather --help
    python -m pytest tests/test_weather_execution.py tests/test_weather_timeout.py -q
    git diff --check

Resultados:

- Suíte: 166 passed, 8 skipped em 2,82 s.
- Os oito testes ignorados exigem Airflow 2.9.2.
- CLI: ajuda exibida e código de saída 0.
- Após ajuste de formatação: 30 passed em 1,41 s.
- git diff --check: sem apontamentos.

## Resultados no Python 3.10

Execução em contêiner descartável da imagem:

    jopecadata/logistics-weather-data-pipeline:1.0.0

Condições:

- --network none e --pull never.
- Scripts, testes, configuração e wheels montados somente para leitura.
- Sem montagem de .env ou data do projeto.
- Dependências de teste instaladas em /tmp/weather-test-deps.
- Instalação offline com --no-index e wheels locais.
- pytest==8.3.3 e packaging==24.2.
- PYTHONDONTWRITEBYTECODE=1.
- PYTEST_DISABLE_PLUGIN_AUTOLOAD=1.
- Testes estruturais da DAG explicitamente excluídos.

Seleção executada:

    pytest /opt/airflow/tests --ignore=/opt/airflow/tests/test_weather_dag_structure.py -q -rs -p no:cacheprovider

Resultado:

- Python: 3.10.14.
- pytest: 8.3.3.
- packaging: 24.2.
- 166 passed em 2,41 s.
- Código de saída: 0.

Uma primeira tentativa com código passado por -c falhou por perda de
aspas na passagem pelo PowerShell, antes de executar o script.
O comando foi corrigido para transmitir o código pela entrada padrão.
Não foi necessário alterar a imagem ou o Compose.

## Validação complementar do Airflow

Evidências devolvidas pelo chat Airflow — Seção 4:

- DAG sem diferenças contra o baseline; código 0.
- Oito testes estruturais aprovados; código 0.
- Três tasks sequenciais preservadas:
  prepare_extraction → extract_batch → reconcile_extraction.
- DAG pausada.
- schedule_interval=null.
- has_import_errors=False.
- Runs 01 e 02 preservadas em failed.
- Nenhuma nova DAG run.
- Inventário pós-R02: 31 arquivos antes e depois.
- Zero diferenças de caminhos e SHA-256.

A comparação da DAG utilizou:

    git diff --exit-code b7a94ce -- dags/weather_extract.py

Os avisos de depreciação do OpenLineage não impediram os testes.

## Preservação e limites

Não foram alterados DAG, Compose, imagens Docker, PostgreSQL ou
contratos R3/DQ.

Não foram executados coleta real, tasks, triggers, dag.test,
tasks test, clear ou unpause operacional.

Os testes de importação existentes integram a regressão aprovada.
A integridade histórica foi conferida para os 31 arquivos inventariados.

A validação comprova o comportamento simulado, a compatibilidade
Python e a estrutura do Airflow. Não comprova sucesso operacional
de uma nova execução da DAG.

## Rollback

O rollback consiste em reverter o commit específico desta correção,
após identificação do hash final e decisão central.

Não utilizar reset destrutivo, excluir artefatos ou modificar
as runs históricas.

A reversão restaura o comportamento anterior, incluindo a
incompatibilidade conhecida. Não autoriza executar novamente a DAG.

## Versionamento e submissão

Branch prevista: main.

O hash final e a confirmação de push serão apresentados no
encaminhamento de encerramento, após a revisão do staging.

Estado central preservado:

- Passo 08: NÃO VALIDADO.
- P08-R03: NÃO LIBERADO.
- Passos 09–11: NÃO LIBERADOS.

A submissão das evidências de P08-C02 não libera nova DAG run.