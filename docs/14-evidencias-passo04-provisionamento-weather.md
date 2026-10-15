# CP v2 | Passo 04 | Provisionamento PostgreSQL meteorológico

- Data de execução: 14/10/2026.
- Checkpoint: CP-2026-10-13 v2.
- Responsável: Docker explicado.
- Estado: execução técnica concluída; evidências em preparação para submissão central.
- Código de partida: 80b99604021e561f45e99f10e94331f5ffeb6d1a.
- Repositório de trabalho: C:\Users\João\Projetos\logistics-weather-data-pipeline.
- Branch de trabalho: main.

A conclusão técnica não equivale a validação central. Passos 05–11 permanecem não liberados.

## Autorização e escopo

João apresentou a liberação central do passo 04 e aprovou expressamente a proposta de provisionamento, incluindo retirar CONNECT de PUBLIC no banco airflow.

A reinicialização controlada para testar persistência foi autorizada separadamente por João.

O escopo compreendeu banco weather, role weather_app, privilégios, autenticação, preservação operacional e documentação.

Não foram criadas tabelas meteorológicas, cargas SQL ou DAGs. Não houve alteração do Executor, inclusão de Redis/Celery ou substituição de volumes.

## Inventário anterior

| Item | Resultado |
|---|---|
| PostgreSQL | 16.15, Debian 16.15-1.pgdg13+2 |
| Projeto Compose | logistics-weather |
| Contêiner PostgreSQL | logistics-weather-postgres-1 |
| Volume | logistics-weather_postgres-data |
| Bancos existentes | airflow, postgres, template0, template1 |
| Role administrativa | airflow |
| weather | Ausente |
| weather_app | Ausente |
| Serviços originais | PostgreSQL, webserver e scheduler healthy |
| Login original | Confirmado |

A role airflow era superuser, com criação de roles e bancos, replicação e bypass de RLS.

O banco airflow pertencia à role airflow e apresentava ACL nula, correspondendo aos privilégios padrão, incluindo CONNECT concedido a PUBLIC.

O schema public do banco airflow pertencia a pg_database_owner, com uso permitido a PUBLIC.

A consulta de memberships mostrou somente associações entre roles predefinidas de monitoramento.

Autenticação observada:

- Conexões locais e loopback: trust.
- Conexões host gerais: scram-sha-256.
- password_encryption: scram-sha-256.

Por isso, a autenticação da aplicação foi testada a partir de outro contêiner, pela rede do projeto.

O PostgreSQL original havia passado por recuperação automática após interrupção anterior. Antes do provisionamento, os serviços e o login já estavam funcionais. A causa da interrupção anterior permaneceu indeterminada.

## Decisão de privilégios

| Recurso | Definição |
|---|---|
| Banco | weather |
| Proprietário administrativo | airflow |
| Aplicação | weather_app |
| LOGIN | Permitido |
| Superuser | Não |
| Criar banco ou role | Não |
| Replicação e bypass de RLS | Não |
| CONNECT em weather | Permitido |
| CREATE/TEMPORARY em weather | Não permitidos |
| USAGE no schema public de weather | Permitido |
| CREATE no schema public de weather | Não permitido |
| Conexão de weather_app ao banco airflow | Recusada |

A aplicação não é proprietária do banco. As permissões de futuras tabelas serão definidas na etapa correspondente.

A administração permanece na role airflow, já existente e superuser. Isso é uma simplificação do laboratório, sem isolamento administrativo ou de infraestrutura entre os bancos.

Os bancos de sistema não tiveram seus privilégios alterados. Não se afirma que weather_app esteja impedida de conectar a todos os demais bancos da instância.

## Provisionamento executado

Comandos executados na pasta original, um por vez.

### Role e senha

```powershell
docker compose -p logistics-weather exec postgres psql -X -v ON_ERROR_STOP=1 -U airflow -d airflow -c "CREATE ROLE weather_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;"
```

Resultado: CREATE ROLE; código 0.

```powershell
docker compose -p logistics-weather exec postgres psql -X -v ON_ERROR_STOP=1 -U airflow -d airflow -c "\password weather_app"
```

Senha definida interativamente e guardada em WEATHER_DB_PASSWORD no .env local. A senha não integra comandos versionados ou este documento.

### Banco e permissões

```powershell
docker compose -p logistics-weather exec postgres psql -X -v ON_ERROR_STOP=1 -U airflow -d airflow -c "CREATE DATABASE weather OWNER airflow TEMPLATE template0;"
```

```powershell
docker compose -p logistics-weather exec postgres psql -X -v ON_ERROR_STOP=1 -U airflow -d airflow -c "REVOKE ALL PRIVILEGES ON DATABASE weather FROM PUBLIC; GRANT CONNECT ON DATABASE weather TO weather_app;"
```

```powershell
docker compose -p logistics-weather exec postgres psql -X -v ON_ERROR_STOP=1 -U airflow -d weather -c "REVOKE ALL PRIVILEGES ON SCHEMA public FROM PUBLIC; GRANT USAGE ON SCHEMA public TO weather_app;"
```

```powershell
docker compose -p logistics-weather exec postgres psql -X -v ON_ERROR_STOP=1 -U airflow -d airflow -c "REVOKE CONNECT ON DATABASE airflow FROM PUBLIC;"
```

Resultados: CREATE DATABASE, REVOKE e GRANT concluídos; código final 0.

O procedimento foi aplicado à instância existente. Não dependeu de scripts de inicialização automática, que não seriam executados retroativamente no volume já inicializado.

Esses comandos são um registro de provisionamento inicial, não um script idempotente. Não devem ser repetidos sem inventário e verificação de conflitos.

## Autenticação e acesso Python

Foi utilizado um contêiner temporário da imagem do projeto, na rede Compose, com Python 3.10 e psycopg2.

A senha foi solicitada com getpass. Não foi montado o .env completo nem incluída a senha na linha de comando.

Conexão observada:

```text
Banco: weather
Utilizador: weather_app
Endereço do cliente: 172.18.0.5/32
Código de saída: 0
```

O endereço é uma evidência daquela execução, não uma configuração fixa.

Privilégios consultados pela própria aplicação:

```text
CONNECT / CREATE / TEMPORARY: (True, False, False)
Schema USAGE / CREATE: (True, False)
```

Não foram criadas tabelas para testar permissões.

### Testes negativos

O teste Python executado:

1. Gerou uma senha diferente da correta e tentou conectar a weather.
2. Usou a senha correta de weather_app para tentar conectar a airflow.

Os critérios foram:

- Senha incorreta: password authentication failed.
- Metadados: permission denied for database.

João confirmou duas mensagens PASS e código 0. Falhas de rede ou outros erros não eram aceitos como evidência de bloqueio.

### Preservação do Airflow

```powershell
docker compose -p logistics-weather run --rm airflow-init airflow db check
```

Resultado: Connection successful; código 0.

Esse comando verifica uma nova conexão. Não executa migração, pois substitui o comando padrão do serviço.

Os três serviços permaneceram healthy e o login original em localhost:8080 foi confirmado.

As propriedades de weather_app foram consultadas:

```text
rolcanlogin: true
rolsuper: false
rolcreatedb: false
rolcreaterole: false
rolreplication: false
rolbypassrls: false
```

## Persistência após reinicialização autorizada

João autorizou a interrupção breve dos serviços originais para este teste.

Procedimento:

```powershell
docker compose -p logistics-weather stop airflow-webserver airflow-scheduler
docker compose -p logistics-weather restart -t 60 postgres
docker compose -p logistics-weather ps
```

Após PostgreSQL healthy:

```powershell
docker compose -p logistics-weather start airflow-webserver airflow-scheduler
docker compose -p logistics-weather ps
docker inspect logistics-weather-postgres-1 --format '{{range .Mounts}}{{println .Type .Name .Destination}}{{end}}'
```

Resultados apresentados:

- Três serviços healthy.
- Volume logistics-weather_postgres-data preservado.
- Sem remoção ou recriação da instância.

Após a reinicialização, João confirmou novamente:

- Conexão como weather_app em weather.
- CONNECT permitido; CREATE e TEMPORARY não permitidos.
- USAGE no schema permitido; CREATE não permitido.
- Senha incorreta recusada.
- Conexão de weather_app ao banco airflow recusada.
- airflow db check aprovado.
- Login original funcional.

As verificações posteriores à reinicialização foram confirmadas por João como aprovadas; suas saídas completas não foram reenviadas ao chat.

## Configuração documentada

.env.example passou a declarar:

```dotenv
WEATHER_DB_HOST=postgres
WEATHER_DB_PORT=5432
WEATHER_DB_NAME=weather
WEATHER_DB_USER=weather_app
WEATHER_DB_PASSWORD=
```

A senha real fica somente no .env local.

O host postgres é válido na rede interna do Compose, não como endereço direto do Python no Windows.

Essas variáveis ainda não são injetadas pelo Compose nem consumidas pelo extrator. A conexão da aplicação foi verificada por parâmetros explícitos e senha interativa no contêiner.

Não foi criada conexão Airflow para weather neste passo.

## Arquivos da entrega

- .env.example: interface pública de configuração, sem senha real.
- README.md: estado do provisionamento, permissões e próximos gates.
- docs/14-evidencias-passo04-provisionamento-weather.md: procedimento e evidências.

O .env real não deve ser versionado.

O commit e seu estado de publicação serão informados no pacote final de submissão.

## Limitações e ressalvas

- Banco vazio de objetos de negócio; não há warehouse ou carga.
- Permissões DML sobre futuras tabelas ainda não foram concedidas.
- Administração compartilhada pela role airflow, que continua superuser.
- Mesma instância e volume para os dois bancos.
- Autenticação local trust não foi alterada; os testes de senha utilizaram a rede entre contêineres.
- Não houve teste de acesso direto pelo Python do Windows.
- Não foi realizado backup/restore nem auditoria completa de integridade dos metadados.
- A tag PostgreSQL permanece mutável.
- As ressalvas de portabilidade e testes Python do passo 03 permanecem registradas.
- A evidência do passo 03 foi publicada na branch docs/passo03-reproducao-docker; sua integração à main continua pendente neste registro.
- O procedimento exige inventário e provisionamento manual em uma instalação nova.

## Estado final e gate

Na última verificação enviada, PostgreSQL, webserver e scheduler originais estavam healthy, com o volume existente preservado. João confirmou login e testes posteriores à reinicialização.

Não foram emitidos comandos deste passo para alterar o ambiente isolado do passo 03; seu estado final não foi novamente inspecionado aqui.

| Critério | Evidência |
|---|---|
| Banco e role provisionados | Comandos e resultados registrados |
| Privilégios mínimos | Consultados pela aplicação e propriedades da role |
| Autenticação real | Conexão por psycopg2 a partir de outro contêiner |
| Bloqueio dos metadados | Conexão de weather_app a airflow recusada |
| Funcionamento do Airflow | Nova conexão, saúde e login aprovados |
| Persistência | Verificações repetidas após reinicialização autorizada |
| Configuração reproduzível | Parâmetros públicos e procedimento manual documentados |
| Documentação e commit | Arquivos preparados; commit/publicação a registrar |

A documentação será submetida ao Planeamento como evidência do passo 04.

A conclusão técnica não autoriza iniciar o passo 05. Aguardar avaliação central e ratificação explícita de João.