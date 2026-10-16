# P08-C01 — Correção de imports e validação sem execução operacional

**Checkpoint:** CP-2026-10-13 v2

**Data:** 16/10/2026 — America/Sao_Paulo

**Responsável pela consolidação:** Docker explicado

**Contribuições:** Custos e APIs Gratuitas; Airflow — Seção 4

**Estado:** validações técnicas reunidas; versionamento e submissão central pendentes.

## 1. Escopo e autorização

A autorização central P08-C01 permitiu diagnóstico, proposta e correção
controlada da resolução dos módulos Python, seguida de validações sem
execução operacional.

João aprovou explicitamente a proposta conjunta:

- Incluir `/opt/airflow` no `PYTHONPATH` compartilhado dos serviços Airflow.
- Adicionar `scripts/__init__.py`.
- Recriar somente webserver e scheduler para aplicar a configuração.
- Validar imports, CLI, regressão, parsing e preservação do estado existente.

Não houve autorização para uma segunda execução manual da DAG.

O passo08 permanece NÃO VALIDADO. P08-R02 e passos09–11 permanecem
NÃO LIBERADOS.

## 2. Referências e baseline

| Item | Referência |
|---|---|
| Repositório | Soba-Jopeca/logistics-weather-data-pipeline |
| Branch local | main |
| Baseline do diagnóstico e dos testes | 9fa3ff75339fe4862e16299f404aed9ce67b6003 |
| Registro do incidente original | docs/18-evidencias-passo08-execucao-manual.md |
| Commit do registro do incidente | 6eab6f1c5522a87503ec5aefa5f7e1392c4688b9 |
| DAG | logistics_weather_extract |
| Run original preservada | manual_cp_v2_p08_20261016_01 |

Após as validações, a cópia local recebeu o commit documental `6eab6f1`
por fast-forward. Esse commit acrescentou somente o documento18,
preservando as alterações locais da correção.

O commit desta correção será identificado no relatório de entrega após
o versionamento; não se confunde com as baselines acima.

## 3. Diagnóstico observado

Antes da correção:

- `PYTHONPATH` não estava definido no scheduler.
- O diretório de trabalho era `/opt/airflow`.
- `scripts` não possuía `__init__.py`.
- Em `python -c`, a resolução encontrava um namespace composto por
  `/opt/airflow/scripts` e pelo diretório homônimo em `site-packages`.
- Ao simular o contexto de console substituindo `sys.path[0]` por
  `/home/airflow/.local/bin`, a resolução encontrava somente o namespace
  em `site-packages`.

A ausência explícita da raiz do projeto no caminho de imports é coerente
com o erro real:

```text
ModuleNotFoundError: No module named 'scripts.extract_weather'
```

O `sys.path` do processo original da task, já encerrado, não foi capturado.
O contexto de console foi simulado para explicar e testar a resolução;
não representa uma captura retrospectiva daquele processo.

A existência do namespace homônimo foi comprovada. Não se atribui
isoladamente toda a falha a essa colisão.

## 4. Correção aplicada

### compose.yaml

Na configuração compartilhada `x-airflow-common.environment`:

```diff
     AIRFLOW__CORE__MAX_ACTIVE_TASKS_PER_DAG: "4"
+    PYTHONPATH: /opt/airflow
     WEATHER_ENDPOINT: ${WEATHER_ENDPOINT:?Define WEATHER_ENDPOINT no .env}
```

O inventário não encontrou valor anterior de `PYTHONPATH` a preservar.
Os caminhos padrão do interpretador continuam disponíveis.

### scripts/__init__.py

```python
"""Núcleo Python do pipeline meteorológico."""
```

O arquivo torna `scripts` um pacote regular, sem importar outros módulos
ou executar lógica da aplicação.

A solução combina a inclusão da raiz no caminho com a identificação
explícita do pacote. O `__init__.py` sozinho não resolveria a ausência
de `/opt/airflow` no caminho de imports.

Não foram alterados:

- Código ou estrutura da DAG.
- Lógica de extração, CLI e contratos Raw/run/batch.
- Imagem Docker ou dependências de produção.
- Executor, PostgreSQL ou volumes.

## 5. Aplicação da configuração

Comandos executados:

```powershell
git diff --check
docker compose -p logistics-weather config --quiet
docker compose -p logistics-weather up -d --no-deps --force-recreate airflow-webserver airflow-scheduler
docker compose -p logistics-weather ps
docker compose -p logistics-weather exec airflow-scheduler printenv PYTHONPATH
docker compose -p logistics-weather exec airflow-webserver printenv PYTHONPATH
```

Resultados observados:

- Configuração Compose válida, código de saída0.
- Webserver e scheduler recriados.
- PostgreSQL permaneceu no contêiner e volume existentes.
- Três serviços posteriormente `healthy`.
- `PYTHONPATH=/opt/airflow` confirmado no webserver e scheduler.

A imagem declarada permaneceu
`jopecadata/logistics-weather-data-pipeline:1.0.0`.

Não houve rebuild ou push de imagem nesta correção. A tag é mutável;
este registro não representa uma nova verificação de identidade por digest.

## 6. Imports e resolução do pacote

A resolução no contexto de console simulado passou a apontar para:

```text
scripts:
  /opt/airflow/scripts/__init__.py

scripts.extract_weather:
  /opt/airflow/scripts/extract_weather.py
```

O caminho do pacote ficou restrito a `/opt/airflow/scripts`, sem composição
com o namespace homônimo de `site-packages`.

Também foi executado um processo Python novo no scheduler, iniciado em
`/tmp`, com `-B`, simulando o caminho inicial do console e bloqueando
rede e operações de escrita por audit hook.

Comando de execução da sonda preparada em PowerShell:

```powershell
docker compose -p logistics-weather exec -w /tmp airflow-scheduler python -B -c "$p08ImportCheck"
```

Saída:

```text
PASS: scripts.extract_weather /opt/airflow/scripts/extract_weather.py
PASS: scripts.weather_interface /opt/airflow/scripts/weather_interface.py
PASS: scripts.weather_manifest /opt/airflow/scripts/weather_manifest.py
PASS: scripts.weather_window /opt/airflow/scripts/weather_window.py
PASS: imports reais com rede e escrita bloqueadas
```

Código de saída:0.

As origens dos quatro módulos foram conferidas. Nenhuma função de
extração ou task foi executada nessa verificação.

## 7. Preservação da CLI

Foi executada a opção `--help` em processo novo iniciado em `/tmp`,
com contexto de console simulado, rede e escrita bloqueadas.

```powershell
docker compose -p logistics-weather exec -w /tmp airflow-scheduler python -B -c "$p08CliCheck"
```

Resultado:

```text
usage: extract_weather.py [-h] --cycle-date AAAA-MM-DD
```

A ajuda apresentou o argumento obrigatório `--cycle-date`.
Código de saída:0.

Essa verificação comprova a disponibilidade da CLI e sua ajuda;
não constitui execução de uma coleta.

## 8. Regressão — contribuição de Custos e APIs

Evidência encaminhada pelo responsável:

| Item | Resultado |
|---|---|
| Python | 3.10.14 |
| pytest | 8.3.3 |
| packaging | 24.2 |
| Resultado | 149 passed in 1.80s |
| Código de saída | 0 |

Condições informadas:

- Contêiner descartável da imagem existente.
- Diretório inicial `/tmp`.
- `PYTHONPATH=/opt/airflow`.
- Rede desativada.
- Scripts, cadastro e testes montados somente para leitura.
- Dados reais e `.env` não montados.
- pytest instalado offline somente em `/tmp`.
- Teste estrutural da DAG excluído dessa rodada e reservado ao responsável Airflow.

Não foi instalado pytest nos serviços em operação nem modificada a imagem.

O relatório informou ausência de alterações nos arquivos do projeto
durante essa validação.

## 9. Parsing e estrutura — contribuição de Airflow

Evidência encaminhada pelo responsável:

| Verificação | Resultado |
|---|---|
| Parsing e estrutura | 8 testes aprovados em 1,202s |
| Código de saída | 0 |
| Tasks | Três tasks sequenciais preservadas |
| Configuração | Timezone, start_date, retries, concorrência e timeouts conferidos |
| Estado persistido | DAG ativa e pausada |
| Agenda | schedule_interval=null |
| Import errors | Ausentes |
| Histórico | Somente a run original, em failed |

Foram informados o teste estrutural por stdin e as consultas
`airflow dags details` e `airflow dags list-runs`.

Nenhuma task foi executada nessas validações.

Os avisos de depreciação do OpenLineage permanecem registrados.
Parsing e imports aprovados não comprovam sucesso operacional da DAG.

## 10. Preservação dos arquivos e metadados

Antes da recriação dos serviços, foram registrados caminho e SHA-256
dos arquivos existentes em `data/raw`.

A comparação posterior por caminho e hash não apresentou diferenças:

```text
Antes: 27 | Depois: 27
```

O resultado se limita aos arquivos desse diretório inventariado;
não constitui auditoria de todo o filesystem.

As consultas de metadados foram realizadas em transação somente leitura.

Estado observado antes e depois:

| Elemento | Estado | try_number |
|---|---|---|
| DAG logistics_weather_extract | Pausada | Não aplicável |
| Run manual_cp_v2_p08_20261016_01 | failed | Não aplicável |
| prepare_extraction | failed | 1 |
| extract_batch | upstream_failed | 0 |
| reconcile_extraction | upstream_failed | 0 |

A consulta de tasks em estados ativos não retornou linhas.
Nenhuma nova DAG run foi observada.

A execução original permaneceu preservada, sem clear, exclusão ou
alteração para aparentar sucesso.

## 11. Atualização documental local

Após confirmar a publicação do registro do incidente:

```powershell
git fetch origin
git merge --ff-only 6eab6f1c5522a87503ec5aefa5f7e1392c4688b9
git rev-parse HEAD
git status --short
git ls-files docs/18*
git diff --check
```

Resultados:

- Fast-forward concluído.
- HEAD em `6eab6f1c5522a87503ec5aefa5f7e1392c4688b9`.
- Documento18 presente e versionado.
- Alteração de `compose.yaml` preservada.
- `scripts/__init__.py` preservado como arquivo novo.
- `git diff --check` sem erros.

## 12. Procedimento de rollback

O rollback não foi executado.

Se necessário e autorizado:

1. Reverter apenas as alterações desta correção, usando o commit específico
   após sua publicação e revisando eventuais mudanças posteriores.
2. Remover a inclusão de `PYTHONPATH` e o `scripts/__init__.py`
   acrescentados nesta intervenção.
3. Validar a configuração Compose.
4. Recriar somente webserver e scheduler para aplicar a configuração anterior.
5. Conferir serviços, pausa da DAG, histórico e integridade dos arquivos.

Não remover volumes, recriar o PostgreSQL, executar migrações adicionais,
disparar tasks ou alterar a run original como parte desse rollback.

A reversão recuperaria a configuração anterior, incluindo a limitação
de importabilidade diagnosticada.

## 13. Limitações e estado de entrega

- As evidências de regressão e parsing foram recebidas dos respectivos
  responsáveis e consolidadas neste documento.
- Os corpos das sondas PowerShell e os comandos completos da instalação
  offline não estão reproduzidos integralmente neste registro.
- Não houve execução operacional da DAG após a correção.
- Não houve chamada à API Open-Meteo nesta intervenção.
- Os testes não comprovam SLA, frescor, publicação ou aptidão integral.
- As ressalvas anteriores dos passos03–04 permanecem.
- A correção técnica não valida automaticamente o passo08.

Arquivos previstos para versionamento:

- `compose.yaml`
- `scripts/__init__.py`
- `docs/19-evidencias-p08-c01-imports.md`

Após revisão, commit e publicação, encaminhar o pacote ao Planeamento
com o estado:

**P08-C01 — EVIDÊNCIA SUBMETIDA**

Aguardar avaliação central e ratificação explícita de João.
Uma nova execução manual depende de autorização específica P08-R02.