# P09-E3-P03 — Implementação submetida; validação offline BLOQUEADA

Baseline: `70b02b044e36adaa0a29612da87cf8bf688567c9`.
Branch exclusiva: `feat/p09-e3-isolated-harness`.
Data: 25/10/2026 (America/Sao_Paulo).

## Atualização C02 — 26/10/2026: bloqueio fundamentado

**CPython compilado; runtime Airflow ainda INCOMPLETO. Não houve reteste nem regressão nova.**
Esta atualização substitui a descrição de ausência absoluta do interpretador abaixo,
que permanece como histórico P03/C01. Os 315 aprovados, 14 falhas e 8 erros são
resultados anteriores e NÃO resultados desta rodada C02.

### Proveniência e integridade

- Origem oficial: https://www.python.org/downloads/release/python-31014/
- Artefato: https://www.python.org/ftp/python/3.10.14/Python-3.10.14.tar.xz
- Assinatura: mesma URL com sufixo `.asc`.
- Tipo: código-fonte XZ, 19.600.188 bytes; destino Linux x86_64.
- SHA-256: `9c50481faa8c2832329ba0fc8868d0a606a680fc4f60ec48d26ce8e076751fda`.
- MD5 publicado na página oficial e conferido: `05148354ce821ba7369e5b7958435400`.
  MD5 não foi usado isoladamente como prova de autenticidade.
- GPG: GOODSIG/VALIDSIG para subchave `CFDCA245B1043CF2A5F97865FFE87404168BD847`,
  chave primária `A035C8C19219BA821ECEA86B64E628F8D684696D`, Pablo Galindo Salgado.
- Chave obtida de https://keys.openpgp.org/vks/v1/by-fingerprint/CFDCA245B1043CF2A5F97865FFE87404168BD847
  e identidade da subchave corroborada no projeto oficial:
  https://github.com/python/cpython/issues/117476 e
  https://discuss.python.org/t/bogus-3-10-beta-1-build/8461 .
- O keyring temporário reporta TRUST_UNDEFINED, sem certificação local de confiança.
  A procedência combina download HTTPS oficial, checksum publicado e assinatura
  criptográfica com fingerprint corroborado; não é inferida apenas do hash calculado.
- A tentativa de obter `/static/files/pubkeys.txt` retornou 404; não foi usada como evidência.

### Preparação executada

Diretório temporário: `/workspace/scratch/5bbc9498ddbd/e3-cpython-c02`.
Ferramentas já presentes: GCC 13.3.0 e GNU Make 4.3.

```bash
tar -xf ../Python-3.10.14.tar.xz
cd Python-3.10.14
./configure --prefix=/workspace/scratch/5bbc9498ddbd/e3-cpython-c02/runtime --with-ensurepip=no
make -j4
make altinstall
```

Configure/build/install concluíram com exit 0. O executável confirma CPython
3.10.14, ABI `cpython-310-x86_64-linux-gnu`. O resultado do make NÃO comprova que
todos os módulos opcionais foram construídos.

Nenhum pip/compilador/pacote novo foi instalado. Um `.pth` exclusivamente dentro
do prefixo temporário referencia os site-packages locais preexistentes de
`p09-offline-venv` e `airflow-p07-venv`. Os 9.954 arquivos inventariados nesses
pacotes tiveram seus hashes reconferidos e permaneceram idênticos.

### Falha atual C02-ENV-03

Airflow 2.9.2 não importável: `ModuleNotFoundError: No module named '_sqlite3'`.
Import independente de ctypes: `ModuleNotFoundError: No module named '_ctypes'`.
Ambos exit 1, sem iniciar serviços ou conectar a banco operacional.

A compilação informa ausência dos headers SQLite e falha `ffi.h: No such file or
directory` para ctypes. Busca local não encontrou sqlite3.h nem ffi.h compatível
com Linux, nem extensões CPython 3.10 correspondentes. Há um ffi.h específico de
macOS no fonte CPython, que NÃO foi usado como substituto Linux.

Bibliotecas runtime locais existem: libsqlite3-0 `3.45.1-1ubuntu2.5` e libffi8
`3.4.6-1build1`. Os headers de desenvolvimento não estão presentes. Extensões
CPython 3.12 encontradas não foram reaproveitadas por incompatibilidade de ABI.

Outros módulos opcionais ausentes reportados pelo build: _bz2, _curses,
_curses_panel, _dbm, _gdbm, _lzma, _tkinter, _uuid, nis e readline. Não se afirma
que todos sejam exigidos pelo harness; não foram instaladas dependências para eles.

### Gates e matriz de ocorrências

| Gate | Resultado |
|---|---|
| Obtenção/procedência CPython | Conferida; assinatura válida |
| Executável e ABI 3.10.14 | Confirmados |
| Airflow importável | BLOQUEADO por _sqlite3; ctypes também indisponível |
| Retestes das 22 ocorrências | NÃO EXECUTADOS nesta rodada |
| Regressão integral | NÃO EXECUTADA nesta rodada |
| Preservação operacional | Arquivos operacionais intactos; sem operações E3 |

Cada uma das 22 linhas da matriz histórica abaixo permanece **pendente de reteste**.
A causa imediata histórica continua registrada no JUnit preservado; a falha atual
de runtime impede concluir se há defeitos adicionais de implementação. Não houve
mudança de expectativa, remoção de teste ou transformação em skip.

### Decisão necessária e rollback

Autorizar obtenção apenas dos headers/arquivos de desenvolvimento compatíveis com
SQLite/libffi locais, com proveniência verificável e extração em prefixo temporário,
sem instalação sistêmica; ou fornecer runtime 3.10.14 completo e confiável.
Depois repetir os gates e todos os testes já autorizados. Dependências adicionais
que se revelem necessárias continuam exigindo decisão específica.

Nenhum código do harness foi alterado nesta rodada. Atualizados apenas este
relatório e tools/e3/README.md, ambos entre os 13 arquivos autorizados. Não há
consumo do orçamento futuro de 15 runs/37 transportes, nem execução de A/B/C.
Rollback: manter branch sem merge, preservar logs e prefixo temporário para análise;
não tocar ambientes, bancos, volumes ou dados operacionais.

### Hashes dos registros C02

| Registro temporário | SHA-256 |
|---|---|
| `configure.log` | `ac5fd2c8ab69ed1502c11e7429774d3b97876605b2278ec37eccf4b57414fbd9` |
| `build.log` | `ef014e950424812bd1b20ba13edef0d591be181c52edb64e70b360cbcde0cbe7` |
| `install.log` | `8d1d26c5a2a511f6058c972e468433e76eec931e1886a13f0c83284e19a18c31` |
| `signature.log` | `7e1a0e16b195edcc35ed7ddf6f46e41c23dcd7028094b72a9987308847b37ea3` |
| `import-airflow.log` | `9333548a37241b072e2ef3d93abf8791f2f85b25ee7228a45d4bd390a07a5778` |
| `import-ctypes.log` | `a8648f795fd091061723f43290fb11ddcce45b31794b508145b7070beb88cdb2` |
| `runtime/bin/python3.10` | `54f4a5b3971977b7b2eb1d595837bd5eff4528eb0e56760b9635e5a66b0386db` |
| `local-packages-before.json` | `f0066aee365e4af3674f8a18f520ddd9b2acab4b053e073e7e9ceff157f9dd5a` |

### Tracebacks e assinatura preservados

```text
Traceback (most recent call last):
  File "<string>", line 1, in <module>
  File "/workspace/scratch/5bbc9498ddbd/airflow-p07-venv/lib/python3.10/site-packages/airflow/__init__.py", line 53, in <module>
    from airflow import configuration, settings
  File "/workspace/scratch/5bbc9498ddbd/airflow-p07-venv/lib/python3.10/site-packages/airflow/configuration.py", line 2348, in <module>
    conf.validate()
  File "/workspace/scratch/5bbc9498ddbd/airflow-p07-venv/lib/python3.10/site-packages/airflow/configuration.py", line 718, in validate
    self._validate_sqlite3_version()
  File "/workspace/scratch/5bbc9498ddbd/airflow-p07-venv/lib/python3.10/site-packages/airflow/configuration.py", line 815, in _validate_sqlite3_version
    import sqlite3
  File "/workspace/scratch/5bbc9498ddbd/e3-cpython-c02/runtime/lib/python3.10/sqlite3/__init__.py", line 57, in <module>
    from sqlite3.dbapi2 import *
  File "/workspace/scratch/5bbc9498ddbd/e3-cpython-c02/runtime/lib/python3.10/sqlite3/dbapi2.py", line 27, in <module>
    from _sqlite3 import *
ModuleNotFoundError: No module named '_sqlite3'

Traceback (most recent call last):
  File "<string>", line 1, in <module>
  File "/workspace/scratch/5bbc9498ddbd/e3-cpython-c02/runtime/lib/python3.10/ctypes/__init__.py", line 8, in <module>
    from _ctypes import Union, Structure, Array
ModuleNotFoundError: No module named '_ctypes'

[GNUPG:] NEWSIG
gpg: Signature made Thu Mar 21 07:55:53 2024 GMT
gpg:                using RSA key CFDCA245B1043CF2A5F97865FFE87404168BD847
[GNUPG:] KEY_CONSIDERED A035C8C19219BA821ECEA86B64E628F8D684696D 0
[GNUPG:] SIG_ID rq8iYvHRkoABx8NBwjv+v56o4RU 2024-03-21 1711007753
[GNUPG:] GOODSIG FFE87404168BD847 Pablo Galindo Salgado <pablogsal@gmail.com>
gpg: Good signature from "Pablo Galindo Salgado <pablogsal@gmail.com>" [unknown]
[GNUPG:] VALIDSIG CFDCA245B1043CF2A5F97865FFE87404168BD847 2024-03-21 1711007753 0 4 0 1 8 00 A035C8C19219BA821ECEA86B64E628F8D684696D
[GNUPG:] KEY_CONSIDERED A035C8C19219BA821ECEA86B64E628F8D684696D 0
[GNUPG:] TRUST_UNDEFINED 0 pgp
gpg: WARNING: This key is not certified with a trusted signature!
gpg:          There is no indication that the signature belongs to the owner.
Primary key fingerprint: A035 C8C1 9219 BA82 1ECE  A86B 64E6 28F8 D684 696D
     Subkey fingerprint: CFDC A245 B104 3CF2 A5F9  7865 FFE8 7404 168B D847

```

---

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


## C03 — 26/10/2026: recuperação e regressão offline

Ubuntu 24.04 amd64; GCC 13.3.0; CPython 3.10.14; ABI cpython-310-x86_64-linux-gnu; Airflow 2.9.2 importável. sqlite3/_sqlite3, ctypes/_ctypes, ssl e venv importados. SQLite carregada: 3.45.1.

Obtidos exclusivamente libffi-dev 3.4.6-1build1 e libsqlite3-dev 3.45.1-1ubuntu2 de https://archive.ubuntu.com/ubuntu/pool/main/libf/libffi/ e https://archive.ubuntu.com/ubuntu/pool/main/s/sqlite3/. SHA256 conferidos no Packages.xz cujo hash consta no InRelease noble assinado (gpgv, chave Ubuntu local). Apenas dpkg-deb -x; nenhuma instalação sistêmica. Headers SQLite 3.45.1 base usados com biblioteca instalada 3.45.1-1ubuntu2.5: mesma API upstream, importação/versão e regressão aprovadas. libffi corresponde exatamente à versão instalada. Links temporários apontam às bibliotecas existentes, sem usar arquivos estáticos dos pacotes.

Prefixo temporário: `/workspace/scratch/5bbc9498ddbd/e3-c03/prefix`; links: `e3-c03/link`. Configure com CPPFLAGS incluindo usr/include e usr/include/x86_64-linux-gnu do prefixo; LDFLAGS=-L do diretório link; --with-ensurepip=no e prefixo e3-cpython-c02/runtime. make -j4; make altinstall, ambos exit 0. Pacotes Python reutilizados pelos caminhos .pth documentados em C02; nenhum pacote Python obtido.

Primeira regressão C03: 336 passed, 1 failed, exit 1. Defeito real: pathlib Python 3.10 conserva io.open no accessor, contornando patches builtins/io. Correção em runtime.py: aplicar checked_open também a Path.open. Expectativa original test_write_guard preservada. Regressão posterior: 337 passed, zero falhas/erros/skips, exit 0, 9.91 s.

Comando: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. AIRFLOW_HOME=<temporário>/airflow-home AIRFLOW__CORE__LOAD_EXAMPLES=False AIRFLOW__CORE__UNIT_TEST_MODE=True <runtime>/bin/python3.10 -m pytest -q -p no:cacheprovider tests --junitxml=<temporário>/final.xml`. Harness repetido separadamente.

### Matriz das ocorrências anteriores

| Teste | Causa/classificação | Correção e reteste |
|---|---|---|
| test_original_dag_parse_only | ABI Python 3.12 versus extensão re2 CPython 3.10 | Runtime 3.10.14 e .pth local; PASS |
| test_finite_timetable_only_two_slots | ABI Python 3.12 versus extensão re2 CPython 3.10 | Runtime 3.10.14 e .pth local; PASS |
| test_dag_id_and_exact_task_ids | ABI Python 3.12 versus extensão re2 CPython 3.10 | Runtime 3.10.14 e .pth local; PASS |
| test_dependencies_and_leaf | ABI Python 3.12 versus extensão re2 CPython 3.10 | Runtime 3.10.14 e .pth local; PASS |
| test_no_authorial_import_at_module_top_level | ABI Python 3.12 versus extensão re2 CPython 3.10 | Runtime 3.10.14 e .pth local; PASS |
| test_no_schedule_and_paused_on_creation | ABI Python 3.12 versus extensão re2 CPython 3.10 | Runtime 3.10.14 e .pth local; PASS |
| test_reconciliation_has_no_collection_call | ABI Python 3.12 versus extensão re2 CPython 3.10 | Runtime 3.10.14 e .pth local; PASS |
| test_serialization_without_execution | ABI Python 3.12 versus extensão re2 CPython 3.10 | Runtime 3.10.14 e .pth local; PASS |
| test_taskflow_retries_trigger_rules_and_timeouts | ABI Python 3.12 versus extensão re2 CPython 3.10 | Runtime 3.10.14 e .pth local; PASS |
| test_temporal_and_concurrency_properties | ABI Python 3.12 versus extensão re2 CPython 3.10 | Runtime 3.10.14 e .pth local; PASS |
| test_f05_interruption_blocks_new_collection_in_fresh_process[after_started-0] | Subprocesso sem requests: caminho de dependências | Runtime 3.10.14 e .pth local; PASS |
| test_f05_interruption_blocks_new_collection_in_fresh_process[after_raw-1] | Subprocesso sem requests: caminho de dependências | Runtime 3.10.14 e .pth local; PASS |
| test_t01_timetable_semantics | ABI Python 3.12 versus extensão re2 CPython 3.10 | Runtime 3.10.14 e .pth local; PASS |
| test_t02_scheduler_resume_candidates[False-13-44-12-False] | ABI Python 3.12 versus extensão re2 CPython 3.10 | Runtime 3.10.14 e .pth local; PASS |
| test_t02_scheduler_resume_candidates[False-13-45-13-True] | ABI Python 3.12 versus extensão re2 CPython 3.10 | Runtime 3.10.14 e .pth local; PASS |
| test_t02_scheduler_resume_candidates[False-14-0-13-True] | ABI Python 3.12 versus extensão re2 CPython 3.10 | Runtime 3.10.14 e .pth local; PASS |
| test_t02_scheduler_resume_candidates[False-14-1-13-False] | ABI Python 3.12 versus extensão re2 CPython 3.10 | Runtime 3.10.14 e .pth local; PASS |
| test_t02_scheduler_resume_candidates[True-13-44-12-False] | ABI Python 3.12 versus extensão re2 CPython 3.10 | Runtime 3.10.14 e .pth local; PASS |
| test_t02_scheduler_resume_candidates[True-13-45-13-True] | ABI Python 3.12 versus extensão re2 CPython 3.10 | Runtime 3.10.14 e .pth local; PASS |
| test_t02_scheduler_resume_candidates[True-14-0-13-True] | ABI Python 3.12 versus extensão re2 CPython 3.10 | Runtime 3.10.14 e .pth local; PASS |
| test_t02_scheduler_resume_candidates[True-14-1-13-False] | ABI Python 3.12 versus extensão re2 CPython 3.10 | Runtime 3.10.14 e .pth local; PASS |
| test_t02_previous_completed_interval_prevents_same_candidate | ABI Python 3.12 versus extensão re2 CPython 3.10 | Runtime 3.10.14 e .pth local; PASS |

Tracebacks originais preservados no JUnit histórico já incorporado neste documento. Evidência completa C03 a seguir (gzip+base64; decodificar sem executar conteúdo).

final.xml: SHA256 `76c981d95d0d50eb3f4d255298de2d85f4659465d3764d8c3590109dedc40321`

```text
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
```

regression.xml: SHA256 `bef94d11ffb493a14741b66933e3b6c6426fa1260c559cdbc118b6acae542303`

```text
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
```

harness.xml: SHA256 `f3332410fc0509c05dcfd67ab3c71885904f34535fc2c557d4101fb7dbcf9510`

```text
H4sIAKwt32oC/71YTXPjKBD9Ky5dt+SR5K84NZ657XFPc0ulKARtmQ0CigYnmV+/DbYTe+Y2wntJJGP1ox+vX7f89fvbqGdH8Kis2VXtvKlmYISVygy7KoZ9/VB9//Y1AAaMiv7NDB9hV7n39NEsf15drd8sUyjvrcddRVH3XOno4XSDL8o5kPk6P7urlh1dqvTwct5ebjDw0e2qrunWddvU3fpH2zwuNo+r9Xzbbjfb7V9N89hQkIPFcILet/t10zWLzYNcnHcmOMJMaI54+kpGnKe/DBbswL0BxGr2uch6ekIrA0yZI5hg/ftlc828aTbV7MufRqaAXCvJBCXG1WCeLlB1z+XzNUpXEgUM7zXIur2BaEtCXC6YkrW1Du+H5K0NtQfNgzrC/ThDQax5ZbGmhQjLG6RFUSRtwxlldb98eAwH69VPos2a+h9rynEHb8FztlegJeNGMkuOorlz5CIsnRaWom4kZyIYSYt4YMlTsFQOUmGukQ/Ciu1ZISYiBh7giZgCb7hmBsKr9S+s11a8gHy+C5p14PNxE+BoownIeI/kaM93Sk7oiFSUbITAJQ/8BuehFM6rp1bDhDV7Ms7x13SWpWCQvkF6SAJmJOgsvGLEvSoj7SsyQ8HpQYopr0K3zRQlR6eVoAzYv2hNLkhAwR2UcuQzMUeFqldahfecBQ92VILuSsFQMQ7g2aeqUiZ06hhvyWrWE0AGbXuqjj4SVvgM2q6meInQ6hwx73nvAX7esL+aEtx6H92FnlJ6PJPtvBW0xDwXHxvu5pvVdlInIs9LW07mSqVL2tQMQSRjKuXeLvZZ8xSSnUdNygUQ/BGQJY8tZRHkOdl9fo3ZTor5FtKOJRBTIwEgkXSSDo86FOtx1KUNOusDo0FgUKktDJH7U9M2ltC07vlNXu0U104nQYd+Sc8A2SjTVMqlxulTJ8g5lONIDakSLio6Gw6VRLxR65SKIKqjOaszW1qguaCcP4zOIjB6eUoqIqzfx4BSwv2QkeQDc9wTrDX6qgOsH7rptZaChTSc5eCMBieWR+ZSPcADZeAsGcg79eVwIMfC4GOaLOh4JDgwkt6KFeCTobG5/uHj9ezcdsv/CTxqXf/NNd6iL0p4czJOvqcbxkWItKU8lFwx3E3RyQAmSTBNUyQ/Cnk6yawYWUqMl6EzT29J92pMg5BKWVLXobeh07vPtbtNKTQUB5AxGZyiEwppDhKcBJL62+85ffn4keT6Gr/9B3GFi6qDEQAA
```

runtime.log: SHA256 `e84efb0ffdbf182e1c0b68e81b7e92e22b1ca6b68e6116ae1a58841e52653795`

```text
H4sIAKwt32oC/wXBvQrCMBAA4D1PcaNCctxfD+2awdEHEBHJYANt7JBCfHu/T5EJ2eC0vWuLcC8dxEFIPALTrD6bneFxyxlYUZGeUPZfX74tKVMaF3+5pbW2Y6RPO4KiTchB8IoS/v28YuJdAAAA
```

signature.log: SHA256 `42d571772f24b8485e3ad777db3ddd8c6f81a346db9bc212293525f6ecca5c82`

```text
H4sIAKwt32oC/12OvQ6CMBRGd57ihkkXw70gWGKM/KiDm+gDIJRCTCkpLYlvrxLj4Lef7xwxiCmGohN9aazmIMuaw7W1kAwaaA0YxogxIZBHAaTF1REz8Tc7dr2AS5HAgz/hGB6y1I9CCqLgkCcsJ0wjj2gTISMvR8YwzZiffb9OStUw/hIarSS4t7vtzTtDV203cUisUbI0XTW3fmTnt2hBHm6WsG3MIMvRcL23M7aqlNy5zgti7mJO3QAAAA==
```

configure.log: SHA256 `4dd333653b44b3e71de36a18997a6c8fc470479180786cb34fc1117f8a2be793`

```text
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
```

build.log: SHA256 `cf78e734435625bbc85f371f01db0303db819684fb508dc17bafbe0213f14751`

```text
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
```

ffi.deb: 62802 bytes SHA256 `7009959b8a3b77206325026917fb45150ac81bf6139468abc0841d5a29c8619d`

sqlite.deb: 910736 bytes SHA256 `d23577c43936fedd8c4fa1337a6e960a6e71e94ac164d7a15c46ea96bf21265d`

Compatibilidade: somente runtime.py e este documento alterados em C03. Nenhum arquivo operacional ou teste anterior alterado. Sem serviços, DAG runs/tasks, CLI operacional ou chamadas meteorológicas reais; orçamento E3 intacto. Barreiras HTTP existentes mantidas. Testes não comprovam confinamento Windows/Docker, durabilidade física ou scheduler real. Rollback: reverter somente commit C03 na branch; preservar registros e runtime temporário para auditoria, sem exclusões operacionais. P03 sujeito ao aceite central; E3 e Passo 09 não validados.
