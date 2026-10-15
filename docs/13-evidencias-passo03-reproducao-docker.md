# CP v2 | Passo 03 | Reprodução Docker isolada

- Data: 14/10/2026.
- Checkpoint: CP-2026-10-13 v2.
- Responsável: Docker explicado.
- Estado: verificações de execução concluídas; documentação em preparação para submissão central.

A execução não equivale a validação central. Passos 04–11 permanecem não liberados.

## Objetivo e escopo

Reproduzir o ambiente a partir de uma cópia nova do repositório, configuração local nova, imagem publicada e volume PostgreSQL independente.

A reprodução ocorreu na mesma máquina Windows, com Docker Desktop/WSL2 e Engine linux/amd64. Não houve validação em uma segunda máquina física nem em um Docker Engine sem cache.

Não foram criadas DAGs, tabelas meteorológicas, cargas SQL, banco weather ou role weather_app.

## Código e imagens

Código reproduzido:

```text
80b99604021e561f45e99f10e94331f5ffeb6d1a
```

Imagem Airflow:

```text
jopecadata/logistics-weather-data-pipeline@sha256:3aef1bab0449408e82325a554aaa882dfbd4077578d99923f10d857744888930
```

A imagem contém o ambiente e as dependências. Código e cadastro são fornecidos por bind mounts; portanto, o digest da imagem não identifica a versão do código.

O pull confirmou o digest publicado e reutilizou camadas locais.

| Componente | Versão observada |
|---|---|
| Docker Client/Server | 29.8.2 |
| Docker Compose | v5.5.1 |
| Plataforma do Engine | linux/amd64 |
| Python do contêiner | 3.10.14 |
| Airflow | 2.9.2 |
| Provider Docker | 3.13.0 |
| tzdata | 2026.5 |
| PostgreSQL | 16.15 |

O PostgreSQL foi executado com a tag postgres:16. Essa tag é mutável; seu digest não foi registrado nesta execução.

## Isolamento

| Recurso | Ambiente de reprodução |
|---|---|
| Diretório | C:\Users\João\Projetos\logistics-weather-repro-p03 |
| Projeto Compose | logistics-weather-repro-p03 |
| Volume PostgreSQL | logistics-weather-repro-p03_postgres-data |
| Rede | logistics-weather-repro-p03_default |
| Interface | http://localhost:8081 |
| Administrador | joao_repro |

O arquivo .env foi criado a partir de .env.example, com senha e chaves novas. Não foi copiado do ambiente original e permaneceu ignorado pelo Git.

Os mounts de dags, data, include, logs, plugins, scripts e config/locations.json apontaram para o diretório de reprodução. O cadastro foi configurado somente para leitura.

O volume original logistics-weather_postgres-data não foi utilizado pela reprodução.

## Procedimento executado

Os comandos abaixo registram o procedimento realizado. Credenciais não integram este documento.

### Preparação da cópia

```powershell
git clone --no-checkout https://github.com/Soba-Jopeca/logistics-weather-data-pipeline.git 'C:\Users\João\Projetos\logistics-weather-repro-p03'
Set-Location -LiteralPath 'C:\Users\João\Projetos\logistics-weather-repro-p03'
git checkout --detach 80b99604021e561f45e99f10e94331f5ffeb6d1a
git rev-parse HEAD
git status --short
```

Na cópia isolada de compose.yaml foram alterados somente:

- name para logistics-weather-repro-p03;
- imagem compartilhada do Airflow para o digest publicado;
- porta do webserver para 127.0.0.1:8081:8080.

Esses ajustes são locais à reprodução. O Compose principal não deve ser substituído pela configuração isolada.

### Imagem e configuração

```powershell
docker pull jopecadata/logistics-weather-data-pipeline@sha256:3aef1bab0449408e82325a554aaa882dfbd4077578d99923f10d857744888930
```

O pull confirmou o digest, com status Image is up to date.

O .env foi criado a partir de .env.example e preenchido com credenciais novas. As chaves foram geradas com Python da imagem:

```powershell
docker run --rm --entrypoint python $reproImage -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
docker run --rm --entrypoint python $reproImage -c "import secrets; print(secrets.token_hex(32))"
```

Nesses comandos, $reproImage correspondia à referência completa da imagem pelo digest informado neste documento.

Validação:

```powershell
docker compose -p logistics-weather-repro-p03 config --quiet
```

Resultado: código 0.

Também foram conferidos:

- .env ignorado pelo Git.
- Ausência prévia de contêineres e volumes da reprodução.
- Diff do Compose com os três ajustes de isolamento.

### Inicialização do PostgreSQL e dos metadados

```powershell
docker compose -p logistics-weather-repro-p03 up -d postgres
docker compose -p logistics-weather-repro-p03 ps
docker inspect logistics-weather-repro-p03-postgres-1 --format '{{range .Mounts}}{{println .Type .Name .Destination}}{{end}}'
docker compose -p logistics-weather-repro-p03 run --rm airflow-init
```

Resultados:

- PostgreSQL healthy.
- Volume logistics-weather-repro-p03_postgres-data montado em /var/lib/postgresql/data.
- Migração concluída com Database migrating done! e código 0.

### Administrador e serviços Airflow

```powershell
docker compose -p logistics-weather-repro-p03 run --rm airflow-init airflow users create --username joao_repro --firstname Joao --lastname Caneca --role Admin --email admin@example.com
```

A senha foi informada interativamente. O endereço de e-mail é ilustrativo para o laboratório.

Resultado: joao_repro criado como Admin; código 0.

```powershell
docker compose -p logistics-weather-repro-p03 up -d airflow-webserver airflow-scheduler
docker compose -p logistics-weather-repro-p03 ps
```

Os três serviços ficaram healthy. Login com joao_repro em localhost:8081 confirmado.

O scheduler carregou LocalExecutor.

### Dependências e imports

```powershell
docker compose -p logistics-weather-repro-p03 run --rm --no-deps --entrypoint python airflow-init -m pip check
```

Resultado: No broken requirements found.

```powershell
docker compose -p logistics-weather-repro-p03 run --rm --no-deps --entrypoint python airflow-init -c "import sys; from pathlib import Path; from importlib.metadata import version; from zoneinfo import ZoneInfo; import scripts.extract_weather as weather; print('Python:', sys.version.split()[0]); print('Airflow:', version('apache-airflow')); print('Provider Docker:', version('apache-airflow-providers-docker')); print('tzdata:', version('tzdata')); print('Diretorio:', Path.cwd()); print('Fuso:', ZoneInfo('America/Sao_Paulo')); print('Endpoint:', weather.load_api_config()['endpoint']); print('Localidades:', len(weather.load_locations())); print('Imports: OK')"
```

Resultados:

- Python 3.10.14.
- Airflow 2.9.2.
- Provider Docker 3.13.0.
- tzdata 2026.5.
- Diretório /opt/airflow.
- Fuso America/Sao_Paulo.
- Endpoint https://api.open-meteo.com/v1/forecast.
- Cinco localidades.
- Imports: OK.
- Código de saída 0.

```powershell
docker compose -p logistics-weather-repro-p03 exec postgres postgres --version
```

Resultado: PostgreSQL 16.15, Debian 16.15-1.pgdg13+2.

### Extração e integridade

```powershell
docker compose -p logistics-weather-repro-p03 run --rm --no-deps --entrypoint python airflow-init -m scripts.extract_weather --cycle-date 2026-10-14
```

Resultados:

- Batch: 6a3ba75f-7f20-4b4d-9f21-268a5beb6e07.
- Ciclo: 2026-10-14.
- Status success.
- Código de saída 0.
- Cinco cidades com estado validated.
- 32 registros por cidade, total 160.
- Resumo em data/raw/batches/6a3ba75f-7f20-4b4d-9f21-268a5beb6e07.json.

| Localidade | Registros | Raw existe | Hash confere | Relatório existe | Relatório confere |
|---|---:|---|---|---|---|
| br_sp_campinas | 32 | True | True | True | True |
| br_sp_sao_paulo | 32 | True | True | True | True |
| br_sp_sorocaba | 32 | True | True | True | True |
| br_sp_jundiai | 32 | True | True | True | True |
| br_sp_ribeirao_preto | 32 | True | True | True | True |

No Windows foram conferidos:

- Existência dos Raw e relatórios individuais.
- SHA-256 dos bytes Raw igual ao registrado no relatório.
- Correspondência de run_id, batch_id e raw_sha256 entre os relatórios individuais e o resumo.

Todas as conferências retornaram True.

Os registros normalizados foram produzidos em memória. Não houve carga meteorológica no PostgreSQL.

### Persistência após recriação

```powershell
docker compose -p logistics-weather-repro-p03 down
docker compose -p logistics-weather-repro-p03 up -d airflow-webserver airflow-scheduler
docker compose -p logistics-weather-repro-p03 ps
docker inspect logistics-weather-repro-p03-postgres-1 --format '{{range .Mounts}}{{println .Type .Name .Destination}}{{end}}'
```

Não foi utilizada a opção -v.

Não foram repetidas a migração nem a criação do administrador após essa recriação.

Resultados:

- Volume independente reutilizado.
- Três serviços healthy.
- Login com joao_repro e a senha existente confirmado.
- Raw e relatórios da rodada preservados.
- Conferências de integridade novamente True.
- Soma dos registros novamente 160.

### Conferência dos mounts

```powershell
docker inspect logistics-weather-repro-p03-airflow-scheduler-1 --format '{{range .Mounts}}{{println .Type .Source .Destination}}{{end}}'
```

Todos os bind mounts apontaram para subdiretórios de:

```text
C:\Users\João\Projetos\logistics-weather-repro-p03
```

Foram identificados dags, data, include, logs, plugins, scripts e config/locations.json, com os destinos esperados em /opt/airflow.

## Ambiente original e ocorrências

### Condição encontrada antes da reprodução

No inventário inicial, o PostgreSQL original já estava parado:

- Contêiner: logistics-weather-postgres-1.
- Estado exited.
- Código de saída 255.
- OOMKilled false.
- State.Error vazio.
- FinishedAt: 2026-10-14T08:59:55.231683939Z.
- Volume: logistics-weather_postgres-data.

Os logs disponíveis apresentavam funcionamento normal antes da parada, mas não permitiram determinar sua causa. Os serviços Airflow originais estavam tentando iniciar.

A parada foi registrada antes da criação do ambiente isolado e não foi atribuída à reprodução.

### Recuperação pontual autorizada

Após concluir as verificações isoladas de execução e persistência, João solicitou a recuperação do ambiente original.

Foi executado:

```powershell
docker start logistics-weather-postgres-1
```

O PostgreSQL identificou um encerramento anterior inadequado, realizou recuperação automática e voltou a aceitar conexões.

Os logs registraram automatic recovery in progress e, posteriormente, database system is ready to accept connections.

A causa da interrupção inicial permanece indeterminada.

A verificação posterior confirmou:

- PostgreSQL original running e healthy, código 0.
- Webserver e scheduler originais healthy.
- Login com joao e a senha existente confirmado em localhost:8080.

Foi utilizado o contêiner existente, sem remoção ou substituição do volume e sem migração manual. A recuperação foi uma intervenção pontual autorizada por João, separada dos testes de reprodução.

Saúde dos serviços e login não constituem auditoria completa da integridade do banco original.

### Ocorrência no comando de inspeção

Uma consulta dos mounts falhou por interpretação das aspas do template no PowerShell.

O comando foi corrigido removendo o separador textual do template. A consulta corrigida confirmou os caminhos isolados.

Não houve alteração de infraestrutura decorrente desse erro.

## Estado final observado

| Ambiente | Estado |
|---|---|
| Original | Três serviços healthy; login existente confirmado após recuperação pontual |
| Reprodução | Três serviços healthy; login e arquivos preservados após recriação |
| Volume original | Mantido no contêiner original |
| Volume de reprodução | Independente e reutilizado após recriação |
| Código reproduzido | Commit 80b9960 |
| Compose isolado | Três ajustes locais; fora do commit documental |
| Credenciais e dados gerados | Fora do versionamento |

Os ambientes permaneceram em execução nas últimas verificações. Não foi realizado encerramento posterior como parte das evidências registradas.

## Critérios de aceite e limitações

| Critério | Evidência |
|---|---|
| Código e imagem identificados | Commit fixado e digest confirmado |
| Isolamento de diretório, projeto e volume | Confirmado |
| Migração e login | Aprovados na execução |
| Saúde dos três serviços | Confirmada antes e depois da recriação |
| Imports e dependências | Aprovados |
| Extração e integridade | Cinco cidades, 160 registros, hashes conferidos |
| Persistência | Login e arquivos preservados após recriação |
| Recuperação do ambiente original | Reinício pontual autorizado; três serviços healthy e login existente confirmado |
| Segunda máquina física | Não verificado |
| Engine sem cache de imagens | Não verificado |
| Documentação e commit | Documento preparado; commit e publicação ainda a registrar |

A evidência demonstra reprodução isolada na mesma máquina com estado de aplicação novo. Não comprova portabilidade para outro host, outra arquitetura ou ambiente sem cache.

A tag postgres:16 permanece mutável. O digest registrado fixa a imagem Airflow, mas o código depende do commit e dos mounts identificados.

A suíte de 73 testes pertence à evidência do passo 02; não foi executada novamente no contêiner neste procedimento.

A validação central do passo 03 e a liberação do passo 04 dependem de decisão explícita de João no Planeamento.