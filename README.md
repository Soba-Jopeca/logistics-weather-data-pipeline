# Logistics Weather Data Pipeline

Pipeline de dados meteorológicos para apoio ao planejamento logístico, desenvolvido como projeto autoral de Engenharia de Dados em um **cenário empresarial inteiramente fictício**.

## Contexto de negócio

- **Consultoria simulada:** Phoenix Data.
- **Cliente fictício:** AuroraLog Transportes & Distribuição S.A.
- **Consultor responsável:** João Pedro Caneca.
- **Projeto:** PHD-AL-2026-001.

No cenário, o planejamento de transportes consulta previsões meteorológicas manualmente, em fontes diferentes e sem histórico padronizado. A iniciativa busca organizar previsões por localidade e horário, preservar a rastreabilidade das coletas e disponibilizar informações para o planejamento diário, iniciado aproximadamente às **15h em America/Sao_Paulo**.

O objetivo é apoiar decisões humanas. O projeto não automatiza alterações de rotas nem demonstra causalidade entre clima e atrasos. Empresas, entrevistas, métricas operacionais e aprovações de negócio são simulações.

## Objetivo e escopo do MVP

- **Localidades:** Campinas, São Paulo, Sorocaba, Jundiaí e Ribeirão Preto, no estado de São Paulo.
- **Fonte:** API de previsão meteorológica da Open-Meteo.
- **Variáveis:** temperatura em °C, precipitação em mm e velocidade do vento em km/h.
- **Janela do planejamento:** ciclo D, de D às 16h até D+2 às 00h, com fim exclusivo em `America/Sao_Paulo`.
- **Cobertura inicial:** normalmente 32 horários por cidade, calculados pelos limites da janela convertidos para UTC.
- **Coleta tardia:** a cobertura exigida começa na primeira hora cheia igual ou posterior a `collected_at`, respeitando o início da janela.
- **Identificação do ciclo:** argumento obrigatório `--cycle-date AAAA-MM-DD`.
- **Consumo previsto:** consultas SQL e tabela consolidada. Não há dashboard obrigatório.

A necessidade operacional documentada prevê coletas a cada duas horas nas horas pares, rodada pré-planejamento às 14h, encerramento das tentativas até 14h15, publicação-alvo até 14h30 e frescor máximo de três horas no uso. Esses controles ainda precisam ser implementados e validados.

## Estado atual

### Extração Python local — validada em 13/10/2026

A primeira rodada real das cinco cidades foi concluída com:

- Status de rodada `success` e código de saída `0`.
- Cinco localidades com estado `validated`.
- 32 horários por cidade, totalizando 160 registros.
- Unidades, estrutura, sequência UTC, cobertura e valores validados.
- Nenhum valor nulo nessa rodada.
- Cinco respostas Raw e respectivos relatórios individuais.
- Um resumo da rodada.
- Hashes SHA-256 conferidos a partir dos bytes persistidos.

**Batch de referência:** `fc8057d2-702c-4da3-90b1-61159f8917c2`.

Os arquivos dessa rodada são evidências locais e não são versionados.

### Cenários controlados verificados

Foram executadas verificações manuais com dados simulados e mocks para:

- Construção da janela e conversão entre timezone IANA e UTC.
- Coleta anterior ao início, coleta em hora exata, coleta tardia e ciclo encerrado.
- Cobertura completa e identificação de horário ausente.
- Conversão de Unix timestamps e rejeição de horários duplicados.
- Rejeição de séries com tamanhos diferentes, unidades incorretas, valores infinitos e precipitação negativa.
- Preservação de nulos e aceitação de temperaturas negativas.
- Associação das medidas ao horário, à cidade e ao run corretos.
- Gravação Raw, conferência de hash, replay de bytes idênticos e bloqueio de conflito.
- Registro de sucesso HTTP e timeout.
- Recuperação após timeout, limite de três tentativas e ausência de repetição no erro HTTP 400.
- Continuidade da rodada após resultado de falha em uma cidade.
- Fluxo integrado de cinco cidades com respostas simuladas e persistência temporária.

Essas verificações foram realizadas durante o desenvolvimento. A suíte de testes reproduzível no repositório e sua integração ao CI continuam pendentes.

### Ambiente Docker — atualizado e validado em 13/10/2026

- Imagem local `jopecadata/logistics-weather-data-pipeline:1.0.0`, reconstruída com as dependências atuais, incluindo `tzdata==2026.5`.
- Airflow 2.9.2 com Python 3.10.14.
- Provider Docker fixado em 3.13.0; `pip check` aprovado no build.
- PostgreSQL 16 para metadados do Airflow, com volume `postgres-data`.
- Webserver e scheduler com `LocalExecutor`; três serviços `healthy` e login confirmado.
- Imports, fuso IANA e cadastro de cinco localidades verificados no contêiner.
- Extração do ciclo `2026-10-13` concluída com status `success`, cinco cidades, 32 registros por cidade e código de saída 0.
- Raw e relatórios confirmados no Windows, com hashes SHA-256 conferidos.
- Persistência validada após `docker compose down` sem `-v` e recriação: migração com código 0, serviços saudáveis, login existente preservado e arquivos íntegros.

**Batch de referência no contêiner:** `ac2066c6-3250-48c1-b2c6-2b507f777bc1`.

Os 160 registros normalizados foram produzidos em memória; sua carga no PostgreSQL permanece pendente.

Imagem publicada no Docker Hub em 13/10/2026. Pull pelo digest e execução verificados no mesmo computador, com Airflow 2.9.2, tzdata 2026.5 e `pip check` aprovado. Reprodução completa em máquina limpa ainda não validada.

Em 14/10/2026, o banco `weather` e a role `weather_app` foram provisionados na instância PostgreSQL original. Conexão autenticada pelo contêiner Python, permissões mínimas, bloqueio de acesso aos metadados e persistência após reinicialização foram verificados. O passo 04 aguarda submissão das evidências e validação central.

Não existem DAGs, tabelas meteorológicas ou cargas implementadas.

## Contrato temporal

Cada execução manual informa explicitamente a data do ciclo. Isso evita associar automaticamente uma coleta ao ciclo errado durante a virada de dia ou a sobreposição de janelas.

Exemplo para o ciclo `2026-10-13`:

| Limite | America/Sao_Paulo | UTC |
|---|---|---|
| Início incluído | 13/10/2026 às 16h | 13/10/2026 às 19h |
| Último horário | 14/10/2026 às 23h | 15/10/2026 às 02h |
| Fim exclusivo | 15/10/2026 às 00h | 15/10/2026 às 03h |

Nesse ciclo:

- Coleta antes das 16h exige todos os 32 horários.
- Coleta às 18h00 exatas inclui as 18h e exige 30 horários.
- Coleta às 18h07 exige os horários a partir das 19h, totalizando 29.
- Coleta no fim exclusivo ou depois não recebe cobertura completa.

O cálculo usa `zoneinfo` e regras reais de timezone. Não fixa permanentemente o deslocamento UTC em três horas.

A API é consultada com limites em `GMT` e `timeformat=unixtime`. Os registros normalizados usam timestamps UTC com informação de fuso.

## Cadastro de localidades

O arquivo `config/locations.json` mantém os identificadores internos, nomes, coordenadas, timezone e identificadores da fonte de geocodificação.

| Localidade | location_id | Latitude | Longitude |
|---|---|---:|---:|
| Campinas | br_sp_campinas | -22.90556 | -47.06083 |
| São Paulo | br_sp_sao_paulo | -23.5475 | -46.63611 |
| Sorocaba | br_sp_sorocaba | -23.50167 | -47.45806 |
| Jundiaí | br_sp_jundiai | -23.18639 | -46.88417 |
| Ribeirão Preto | br_sp_ribeirao_preto | -21.1775 | -47.81028 |

Todas usam `America/Sao_Paulo`.

As coordenadas foram conferidas na API de geocodificação da Open-Meteo. Representam pontos de referência das cidades, não centros de distribuição reais.

O cadastro e os parâmetros são copiados para preservar a configuração usada na coleta. As coordenadas retornadas pela previsão podem corresponder à célula do modelo meteorológico e diferir das solicitadas.

## Fluxo implementado

1. Ler a data do ciclo, a configuração da API e o cadastro.
2. Criar uma rodada com `batch_id`.
3. Criar um `run_id` por cidade.
4. Construir a janela e congelar os parâmetros da requisição.
5. Consultar a API com tentativas limitadas.
6. Preservar os bytes da última resposta recebida e calcular seu hash.
7. Validar estrutura, unidades, horários, valores e cobertura.
8. Produzir registros normalizados em memória.
9. Gravar o relatório da cidade.
10. Classificar a rodada e gravar seu resumo.

Uma falha registrada em uma cidade permite continuar para as demais.

### Tentativas HTTP

Cada chamada possui `attempt_id`, número da tentativa, início e fim UTC, duração, status HTTP e categoria de erro.

A política atual permite até três tentativas, com esperas de um e dois segundos. Repete timeout, falha de conexão e HTTP 500, 502, 503 ou 504. Outros erros, incluindo 400 e 429, encerram as tentativas do run.

O timeout é de 10 segundos para conexão e 30 segundos de espera de leitura. Não representa um limite total de duração da coleta.

## Estados e qualidade

### Estado por cidade

| Estado | Significado |
|---|---|
| validated | Validações aprovadas, cobertura exigida completa e ausência de nulos na resposta |
| validated_with_nulls | Cobertura exigida completa, com nulos preservados e sinalizados |
| incomplete | Estrutura e valores processados, mas cobertura exigida não atendida |
| failed | Falha HTTP, de validação ou de persistência |

### Estado da rodada

| Estado | Significado |
|---|---|
| success | Todas as cidades ficaram em validated ou validated_with_nulls |
| partial_success | Parte das cidades atingiu esses estados |
| failed | Nenhuma cidade atingiu esses estados |

**Sucesso de extração não equivale a publicação ou aptidão de todos os produtos.** Nulos permanecem `null`; totais, médias e máximos integrais exigem completude das métricas e dos horários necessários.

Frescor no uso, publicação, fallback, consulta histórica as-of e sinalização de atraso operacional permanecem pendentes.

## Arquivos gerados

Os arquivos ficam em `data/raw/`:

| Caminho | Conteúdo |
|---|---|
| weather_<run_id>.json | Bytes do corpo da última resposta HTTP recebida |
| runs/<run_id>.json | Metadados, cadastro usado, ciclo, parâmetros, tentativas, validações e referência ao Raw |
| batches/<batch_id>.json | Resumo da rodada e resultados individuais |

O Raw utiliza `response.content`, após eventual descompressão feita pelo Requests. O hash SHA-256 corresponde aos bytes efetivamente gravados e fica no relatório do run.

O mesmo `run_id` com bytes idênticos reutiliza o arquivo. Conteúdo conflitante é bloqueado, preservando o original. Uma nova coleta gera novos identificadores.

O relatório também bloqueia conteúdo conflitante no mesmo identificador. A auditoria completa de incidentes de replay ainda precisa ser consolidada.

As tentativas anteriores ficam registradas nos metadados; seus corpos HTTP não são preservados individualmente nesta versão.

Os registros normalizados são produzidos em memória, com:

- `run_id`
- `location_id`
- `forecast_time_utc`
- `temperature_2m_c`
- `precipitation_mm`
- `wind_speed_10m_kmh`

Sua persistência no PostgreSQL será implementada posteriormente.

## Preparação do ambiente Python

Ambiente local utilizado: Windows, PowerShell e Python 3.13.

Após clonar o repositório, execute na raiz do projeto:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

O pacote `tzdata` está registrado nas dependências para disponibilizar as regras de timezone, inclusive no Windows.

Crie `.env` a partir de `.env.example` somente se ainda não existir. Preserve as configurações existentes.

Para a extração, a configuração necessária é:

```dotenv
WEATHER_ENDPOINT=https://api.open-meteo.com/v1/forecast
```

O arquivo `.env` é opcional quando a variável já está definida no ambiente. Variáveis do terminal têm prioridade sobre o arquivo.

Não é necessária chave de API para esta consulta pública. Credenciais do Docker/Airflow permanecem no `.env` local.

## Execução manual

Na raiz do projeto, com o ambiente virtual ativo:

```powershell
python -m scripts.extract_weather --cycle-date 2026-10-13
$LASTEXITCODE
```

Substitua a data pelo ciclo que deseja consultar, dentro da cobertura disponível na API. O exemplo acima corresponde à rodada validada em 13/10/2026.

Para consultar a ajuda sem realizar coleta:

```powershell
python -m scripts.extract_weather --help
```

Códigos de saída:

- `0`: rodada com status `success`, podendo conter nulos sinalizados.
- `1`: rodada parcial, falha de execução ou falha de persistência.
- `2`: erro de argumentos identificado pelo `argparse`.

O resumo é gravado antes do retorno do código da rodada, quando a persistência está disponível.

Para sair do ambiente virtual:

```powershell
deactivate
```

Não é necessário recriar o ambiente a cada execução.

## Exploração no Postman

A coleção pública fica em:

```text
postman/collections/Logistics Weather Pipeline/
```

Ela contém uma requisição GET de Campinas com janela fixa, `GMT`, `unixtime` e unidades do contrato, sem autenticação ou corpo de requisição.

As datas salvas representam a prova de conceito de outubro de 2026 e devem ser ajustadas para novas consultas.

A pasta `.postman/`, que vincula o projeto ao workspace local, não é versionada.

## Ambiente local com Docker

A implementação atual utiliza `compose.yaml`, Airflow com `LocalExecutor` e PostgreSQL 16.

### Escolhas de arquitetura

**LocalExecutor**

O projeto é executado num único computador, com processamento em lote e sem necessidade atual de distribuir tarefas entre máquinas. O LocalExecutor permite executar tarefas em processos locais no contêiner do scheduler, mantendo o ambiente com três serviços: PostgreSQL, webserver e scheduler.

Essa escolha reduz os componentes a configurar e operar. A concorrência está limitada a quatro tarefas globais e quatro por DAG, como configuração inicial a avaliar durante a implementação dos fluxos. A coleta atual das cinco cidades é sequencial; esses limites não a tornam paralela.

O ambiente depende da disponibilidade e dos recursos do computador local. A escolha será revista se houver necessidade de execução distribuída, isolamento dos workers ou maior capacidade de processamento.

**PostgreSQL 16**

O PostgreSQL 16 foi mantido porque o ambiente com Airflow 2.9.2 passou pelas verificações locais de inicialização dos metadados, funcionamento dos serviços, login e persistência após recriação dos contêineres.

Fixar a versão principal evita mudanças automáticas entre versões principais. A tag `postgres:16` ainda pode receber atualizações menores; ela não fixa uma imagem imutável.

O banco `airflow` armazena metadados da orquestração. O banco `weather` foi provisionado separadamente, com a role de aplicação `weather_app`. Ambos compartilham a mesma instância e o mesmo volume PostgreSQL, sem isolamento de infraestrutura.

A role `airflow` permanece proprietária administrativa dos dois bancos e superuser. `weather_app` possui somente `CONNECT` em `weather` e `USAGE` no schema `public`, sem criação de schemas, tabelas permanentes ou temporárias e sem poderes administrativos. Permissões sobre futuras tabelas serão definidas na etapa correspondente.

O privilégio `CONNECT` de `PUBLIC` foi removido do banco `airflow`. A conexão de `weather_app` aos metadados foi recusada, enquanto novas conexões do Airflow e o login existente permaneceram funcionais. As permissões dos bancos de sistema não foram alteradas.

Mudanças de versão principal serão planejadas com backup e procedimento de migração, preservando o volume existente.

Pré-requisitos: Docker Desktop iniciado, WSL2 funcional no Windows e Docker Compose disponível.

### Construir a imagem

Na raiz do projeto:

```powershell
docker build -t jopecadata/logistics-weather-data-pipeline:1.0.0 .
```

Alterações nas dependências exigem reconstrução da imagem.

### Configurar o laboratório

No `.env` local, mantenha:

```dotenv
WEATHER_ENDPOINT=https://api.open-meteo.com/v1/forecast
POSTGRES_AIRFLOW_PASSWORD=
AIRFLOW_FERNET_KEY=
AIRFLOW_SECRET_KEY=
```

Preencha com os valores locais. Para este laboratório, a senha PostgreSQL utiliza letras e números, evitando caracteres que precisem de codificação na URL de conexão.

Na primeira configuração, gere as chaves:

```powershell
docker run --rm --entrypoint python jopecadata/logistics-weather-data-pipeline:1.0.0 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

docker run --rm --entrypoint python jopecadata/logistics-weather-data-pipeline:1.0.0 -c "import secrets; print(secrets.token_hex(32))"
```

Salve os resultados em `AIRFLOW_FERNET_KEY` e `AIRFLOW_SECRET_KEY`, respectivamente. Preserve os valores entre reinicializações.

### Inicializar e iniciar os serviços

```powershell
docker compose config --quiet
docker compose up -d postgres
docker compose run --rm airflow-init
```

Na primeira configuração, crie o administrador. A senha é solicitada interativamente:

```powershell
docker compose run --rm airflow-init airflow users create --username joao --firstname Joao --lastname Caneca --role Admin --email admin@example.com
```

O endereço de e-mail é ilustrativo para o laboratório.

Inicie os serviços:

```powershell
docker compose up -d airflow-webserver airflow-scheduler
docker compose ps
```

Aguarde PostgreSQL, webserver e scheduler ficarem `healthy`. A interface local está disponível em http://localhost:8080.

### Executar a extração no contêiner

A configuração compartilhada define `/opt/airflow` como diretório de trabalho, fornece `WEATHER_ENDPOINT` por ambiente e monta `config/locations.json` somente para leitura. O `.env` completo não é montado no contêiner.

Na raiz do projeto, execute:

```powershell
docker compose run --rm --no-deps --entrypoint python airflow-init -m scripts.extract_weather --cycle-date 2026-10-13
$LASTEXITCODE
```

Substitua a data pelo ciclo desejado, dentro da cobertura disponível na API. `2026-10-13` identifica o ciclo usado na validação registrada.

O comando reutiliza a configuração de `airflow-init`, mas executa Python diretamente. Não realiza migração nem exige PostgreSQL em execução para a coleta.

A execução validada produziu 32 registros por cidade, totalizando 160, com status `success` e código 0. Raw e relatórios permanecem em `data/raw/` no Windows pelo bind mount de `data/`.

Os registros normalizados continuam em memória nesta etapa.

### Parar e retomar

```powershell
docker compose stop
docker compose start
```

A instância PostgreSQL contém os bancos `airflow` e `weather`. O banco meteorológico ainda não possui tabelas de negócio nem dados carregados. O volume `postgres-data` mantém ambos os bancos entre remoções de contêineres. O comando `docker compose down -v` apaga esse volume.

### Configuração do banco meteorológico

Os parâmetros de conexão pela rede interna do Compose são:

```dotenv
WEATHER_DB_HOST=postgres
WEATHER_DB_PORT=5432
WEATHER_DB_NAME=weather
WEATHER_DB_USER=weather_app
WEATHER_DB_PASSWORD=

### Imagem publicada no Docker Hub

Repositório: [jopecadata/logistics-weather-data-pipeline](https://hub.docker.com/r/jopecadata/logistics-weather-data-pipeline).

Tag publicada: `1.0.0`.

Digest do índice OCI:

```text
sha256:3aef1bab0449408e82325a554aaa882dfbd4077578d99923f10d857744888930
```

A imagem executável publicada é para `linux/amd64`. Ela contém Airflow, Python e dependências; código, cadastro e dados são disponibilizados pelos mounts do projeto.

Para obter a versão identificada pelo digest:

```powershell
$publishedWeatherImage = 'jopecadata/logistics-weather-data-pipeline@sha256:3aef1bab0449408e82325a554aaa882dfbd4077578d99923f10d857744888930'
docker pull $publishedWeatherImage
```

Validações executadas:

```powershell
docker run --rm --entrypoint python $publishedWeatherImage -c "import airflow; from importlib.metadata import version; print('Airflow:', airflow.__version__); print('tzdata:', version('tzdata'))"
docker run --rm --entrypoint python $publishedWeatherImage -m pip check
```

Resultados: Airflow 2.9.2, tzdata 2026.5 e dependências sem conflitos. O pull reutilizou camadas locais; não comprova reprodução em máquina limpa.

O Compose mantém a tag `1.0.0` e `pull_policy: never`. Em máquina limpa, obtenha a imagem antes de iniciar:

```powershell
docker pull jopecadata/logistics-weather-data-pipeline:1.0.0
```

A tag pode mudar; o digest identifica o conteúdo publicado nesta validação. A reprodução completa exige também o repositório, os arquivos montados, a configuração local e a inicialização dos metadados.

### Recriar e verificar a persistência

Procedimento validado em 13/10/2026:

```powershell
docker compose down
docker compose up -d postgres
docker compose run --rm airflow-init
$LASTEXITCODE
docker compose up -d airflow-webserver airflow-scheduler
docker compose ps
```

Execute um comando por vez e interrompa se houver erro. Aguarde os três serviços ficarem `healthy` e confirme o login com o utilizador existente, sem recriá-lo.

Na validação, os metadados de acesso permaneceram disponíveis no volume PostgreSQL. O resumo da rodada, os cinco Raw e os relatórios individuais permaneceram no Windows, com hashes SHA-256 conferidos.

Não acrescente `-v` ao comando `down`: essa opção remove o volume PostgreSQL.

## Arquitetura de referência

```text
Open-Meteo → Python → Raw e relatórios → PostgreSQL + SQL/ELT → consultas analíticas
```

- **Implementado:** extração manual, cadastro, janela por ciclo, tentativas, validações e persistência Raw/relatórios.
- **Ambiente configurado:** Docker, serviços Airflow e PostgreSQL com bancos `airflow` e `weather`, além da role `weather_app`.
- **Testes da extração:** 73 testes versionados no passo 02, commit `80b9960`; não repetidos no contêiner durante o passo 03.
- **Pendente:** especificação e implementação da orquestração, carga meteorológica, publicação dos produtos de dados, fallback e CI/CD, conforme os gates centrais.

## Documentação e governança

| Documento | Finalidade |
|---|---|
| [Business Case v1.1](docs/01-business-case-v1.1.md) | Problema, objetivos, benefícios esperados e restrições |
| [Discovery e Escopo v1.2](docs/02-discovery-requisitos-escopo-v1.2.md) | Baseline histórico, complementado pelas decisões posteriores |
| [Reunião 1 — Kickoff](docs/04-ata-reuniao-01-kickoff-aprovada-simulacao.md) | Decisões iniciais e aprovação fictícia |
| [Reunião 2 — Agenda](docs/05-reuniao-02-abertura-e-agenda.md) | Preparação do AS-IS/TO-BE |
| [Reunião 2 — Ata](docs/06-ata-reuniao-02-processos-as-is-to-be.md) | Processos, decisões e requisitos |
| [Reunião 3 — Ata](docs/07-ata-reuniao-03-contrato-dados-aprovacao-simulada.md) | Contrato, qualidade e responsabilidades |
| [Contrato de dados v0.1](docs/08-contrato-dados-weather-v0.1.md) | Grãos, temporalidade, integridade e rastreabilidade |
| [Matriz de qualidade v0.1](docs/09-matriz-qualidade-weather-v0.1.md) | Regras DQ-01 a DQ-12 e testes de aceite |
| [Reunião 4 — Proposta](docs/10-ata-reuniao-04-priorizacao-mvp-proposta.md) | Priorização, riscos e critérios de aceite |
| [Reunião 5 — Proposta](docs/11-ata-reuniao-05-playback-aceite-condicional-proposta.md) | Playback e proposta de aceite condicional |

Diagramas editáveis no Excalidraw:

- [AS-IS — Processo atual](docs/diagrams/reuniao-02-as-is.excalidraw)
- [TO-BE — Arquitetura de referência](docs/diagrams/reuniao-02-to-be.excalidraw)

O contrato e a matriz DQ são baselines documentais aprovados na simulação R3. R4 e R5 permanecem propostas conforme seus documentos. A documentação não comprova implantação nem aceite de cliente real.

A janela por ciclo definida em R3 substitui o objetivo anterior de 24 horas. As evidências técnicas deste README indicam o que foi efetivamente verificado.

## Próximas entregas

A evolução segue o checkpoint CP-2026-10-13 v2:

1. Submeter as evidências do provisionamento do passo 04 e aguardar validação central.
2. Após liberação do passo 05, especificar a orquestração Airflow.
3. Após liberação do passo 06, preparar a interface Python pura/CLI.
4. Após liberação do passo 07, implementar DAG pausada, com `schedule=None`, e validar parsing sem executar tarefas.
5. Após liberação do passo 08, realizar a primeira execução manual.
6. No passo 09, testar falhas e retentativas; ensaiar agenda somente após autorização específica.
7. No passo 10, consolidar o gate da Seção 4, documentação e versionamento.
8. Somente no passo 11, implementar DDL, carga e SQL meteorológicos, com os gates correspondentes.

A reprodução do passo 03 foi validada centralmente com ressalvas: mesma máquina, reutilização de cache e ausência de validação em outro host. Essas limitações permanecem registradas.

## Princípios de engenharia

- Preservar dados originais e a geografia utilizada em cada coleta.
- Distinguir horário da previsão, coleta e publicação.
- Manter nulos explícitos.
- Identificar rodada, run e tentativa HTTP.
- Congelar parâmetros durante as retentativas.
- Conferir integridade dos arquivos e bloquear conflitos.
- Isolar falhas por cidade.
- Distinguir sucesso de extração de disponibilidade e aptidão dos produtos.
- Manter credenciais fora do repositório.
- Não apresentar resultados hipotéticos como ganhos medidos.

## Limitações e custos

- A execução atual é manual; depende do computador e dos serviços locais.
- A associação do ciclo é explícita; sua seleção automática será definida na orquestração.
- A agenda, o corte das tentativas, a publicação e o atraso ainda não são automatizados.
- As regras DQ-01 a DQ-12 não estão integralmente implementadas.
- Não existe fallback operacional, controle de frescor no uso ou publicação as-of.
- Replay de arquivos não comprova idempotência de carga no PostgreSQL.
- Não há garantia de recuperação de uma gravação interrompida.
- Previsões de modelo não representam observações confirmadas nem explicam atrasos de entregas.
- O objetivo é infraestrutura local sem contratação de serviços pagos, sujeito às condições das ferramentas e APIs.
- Uso e atribuição dos dados devem respeitar as condições da Open-Meteo. CI/CD também depende dos limites do plano utilizado.

## Arquivos fora do versionamento

O `.gitignore` exclui o ambiente virtual, `.env`, caches, logs, `data/raw/` e `.postman/`.

São públicos e versionáveis:

- `.env.example`, com valores de exemplo.
- Cadastro de localidades.
- Código e dependências.
- Documentação.
- Coleção Postman revisada, sem credenciais.

## Fonte de dados

- [Open-Meteo](https://open-meteo.com/)
- [Weather Forecast API](https://open-meteo.com/en/docs)
- [Geocoding API](https://open-meteo.com/en/docs/geocoding-api)

## Autoria

João Pedro Caneca — [Soba-Jopeca](https://github.com/Soba-Jopeca)

Projeto autoral de aprendizado e portfólio de Engenharia de Dados, desenvolvido incrementalmente. Não redistribui código de cursos usados como referência.
