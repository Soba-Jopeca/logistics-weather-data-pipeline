# P09-T01 — Evidências de resiliência offline E1/E2

## 1. Identificação e autorização

- Projeto: Logistics Weather Data Pipeline.
- Checkpoint: CP-2026-10-13 v2.
- Execução: 17 e 18/10/2026, America/Sao_Paulo.
- Responsável: Custos e APIs Gratuitas.
- Parecer complementar: Airflow — Seção 4.
- Branch: test/p09-t01-offline.
- Base local: b825486fcd13fcb69675ad7c3c236c85b7927939.
- Baseline funcional: 770a7a1.
- Contrato: docs/23-proposta-p09-p01-resiliencia-agendamento.md, v0.2.
- Estado: evidências consolidadas; commit, push e submissão central pendentes.

João aprovou expressamente a proposta antes da implementação.
O pacote limita-se aos cenários F01–F12 em E1/E2.

Passos 01–08 permanecem validados com suas ressalvas.
Passo 09 não validado. E3, implementação temporal, agenda e passos
10–11 não liberados.

## 2. Escopo e arquivos

Foram criados:

- tests/helpers/__init__.py
- tests/helpers/weather_resilience.py
- tests/test_weather_resilience_offline.py
- tests/test_weather_interruption.py
- docs/24-evidencias-p09-t01-offline.md

Nenhum arquivo de produção foi modificado.

Conferência realizada antes da documentação:

```powershell
git branch --show-current
git status --short
git diff --exit-code b825486 -- scripts dags compose.yaml config requirements.txt requirements-dev.txt .env.example
$LASTEXITCODE
```

Resultado: branch esperada, somente arquivos novos de testes/helpers
e código 0 na comparação dos caminhos de produção.

Não houve alteração de DAG, infraestrutura, imagem, dependências de
produção, PostgreSQL ou contratos Raw/run/batch.

## 3. Ambiente e procedência

Ambiente-alvo:

- Python 3.10.14.
- pytest 8.3.3.
- packaging 24.2.
- Requests 2.34.2.
- urllib3 2.8.0.
- Imagem local: jopecadata/logistics-weather-data-pipeline:1.0.0.

ID da imagem consultado após a execução:

```text
sha256:3aef1bab0449408e82325a554aaa882dfbd4077578d99923f10d857744888930
```

Condições do contêiner:

- Descartável, com --network none e --pull never.
- Scripts, testes, config e wheels montados somente para leitura.
- Sem montagem de .env operacional, dados históricos ou socket Docker.
- Evidências e fixtures em nova pasta temporária por execução.
- Dependências de teste instaladas offline, somente em /tmp.
- PYTHONDONTWRITEBYTECODE=1.
- PYTEST_DISABLE_PLUGIN_AUTOLOAD=1.
- Sem inicialização de Airflow ou PostgreSQL pelos testes.

Windows/venv foi utilizado para edição, coleta de testes e verificações
complementares iniciais. Não substituiu a execução no Python 3.10.

A procedência do comando, das montagens e das versões é sustentada
pelas saídas fornecidas por João no chat executor. A revisão do pacote
anexado foi estática; não constitui execução independente pelo revisor.

## 4. Isolamento e instrumentação

As fixtures reutilizam configuração, localidades, payload e relógio
sintéticos dos testes existentes.

O transporte é interceptado em HTTPSConnectionPool.urlopen,
preservando Session.request, Session.send e HTTPAdapter.send reais.
A configuração JSON atravessa a reconstrução do timeout existente.

São registrados cidade, parâmetros, ordem das chamadas, resultado
simulado e tempos de conexão/leitura.

As esperas de retries são interceptadas, verificando [1, 2] sem
aguardar tempo real.

Barreiras adicionais:

- Bloqueio de DNS e conexões socket.
- Tentativas de rede não podem ser ocultadas por captura da exceção.
- Auditoria de operações Python de escrita na raiz temporária.
- Descritores de pipe permitidos para comunicação entre processos.
- Inventários com caminho relativo, tamanho e SHA-256.
- Comparação de arquivos anteriores e arquivos novos admitidos.

Os cinco testes de suporte incluem sondagens deliberadas das barreiras.
Essas sondagens são bloqueadas e esperadas; não representam acesso
efetivo à rede ou escrita fora da raiz.

As barreiras Python não são sandbox universal de syscalls,
descritores previamente abertos ou subprocessos arbitrários.
O bloqueio de rede do contêiner, as montagens somente para leitura
e a ausência de dados operacionais são complementos essenciais.

## 5. Matriz de resultados

Todos os casos abaixo passaram nas condições offline descritas.

"Inicial" inclui a construção sintética da fixture quando necessária.
"Adicional" refere-se à tentativa posterior de replay, inspeção ou
reconciliação, quando aplicável.

| Cenário | Variante | Transporte observado | Resultado e preservação |
|---|---|---|---|
| F01 | Timeout | 7 chamadas | Sorocaba failed após 3 tentativas; demais cidades continuam; partial_success, 128 registros; sem Raw da cidade sem resposta |
| F01 | Conexão | 7 chamadas | Mesmo limite, continuidade, identidades e parâmetros preservados |
| F02 | Timeout → 503 → 200 | 7 chamadas | Recuperação no mesmo run; esperas [1, 2]; success, 160 registros; um Raw final por cidade |
| F03 | Última hora ausente | 5 chamadas | HTTP 200 não promove sucesso: cidade incomplete, 31/32 horas; partial_success, 159 registros; Raw preservado |
| F04 | Relatório impedido após Raw | 5 iniciais; 0 adicionais | Raw preservado; causa no resumo; execution_error; reinício bloqueado por ambiguous_state; sem conclusão |
| F05 | Após started | 0 iniciais; 0 adicionais | Filho encerrado com -15; inspeção nova com código 0; ambiguous_state; arquivos anteriores preservados |
| F05 | Após Raw | 1 inicial; 0 adicionais | Raw já persistido; mesmo bloqueio, preservação e encerramento dos processos |
| F06 | Replay íntegro | 5 iniciais; 0 adicionais | mode=replay; 160 registros; mesmos IDs; 14 arquivos com inventários idênticos |
| F07 | Parcial por timeout | 7 iniciais; 0 adicionais | Replay mantém partial_success e 128 registros; nenhum arquivo novo ou alterado |
| F07 | Parcial por cobertura | 5 iniciais; 0 adicionais | Replay mantém partial_success e 159 registros; nenhum arquivo novo ou alterado |
| F08 | started sem completed | 0 chamadas | ambiguous_state; somente novo incidente permitido |
| F08 | Raw órfão | 0 chamadas | Mesmo bloqueio; nenhum arquivo anterior sobrescrito |
| F09 | Raw adulterado | 5 iniciais; 0 adicionais | artifact_integrity; um byte alterado; sem reparo automático |
| F09 | Relatório adulterado | 5 iniciais; 0 adicionais | Mesmo bloqueio e preservação do estado adulterado |
| F09 | Conclusão adulterada | 5 iniciais; 0 adicionais | Mesmo bloqueio e preservação do estado adulterado |
| F10 | Hash informado incorreto | 0 chamadas | manifest_integrity; sem nova marca de início ou Raw |
| F10 | Bytes alterados, hash antigo | 0 chamadas | Mesmo bloqueio; incidente sem batch_id confiável |
| F11 | Contador divergente | 5 iniciais; 0 adicionais | Verificador Python rejeita com ValueError; sem reparo ou novas escritas |
| F11 | Run ID divergente | 5 iniciais; 0 adicionais | Mesmo resultado pelo verificador puro |
| F11 | Referência divergente | 5 iniciais; 0 adicionais | Mesmo resultado pelo verificador puro |
| F12 | Mesmo contexto e contexto distinto | 0 chamadas | Repetição conserva IDs; contexto distinto cria outro manifesto/batch para o mesmo ciclo |

Nos casos E1 não há código de saída de aplicação individual:
as funções retornam resultados ou exceções esperadas, avaliados
pelo pytest. O processo da suíte terminou com código 0.
Os códigos próprios dos subprocessos F05 são -15 e 0.

F03 identificou como ausente:

```text
2026-10-15T02:00:00+00:00
```

A integridade técnica de um resultado parcial não significa
sucesso integral, publicação ou aptidão analítica.

## 6. Interrupção determinística F05

O processo filho sinaliza prontidão por pipe somente após:

1. Persistir started.json e antes do transporte.
2. Persistir o Raw da primeira cidade e antes da conclusão.

A sinalização inclui PID, batch, contador de transporte e inventário.
Não se utiliza sleep para adivinhar o ponto de interrupção.

O controlador aguarda o evento por até 45 segundos, encerra somente
o filho criado pelo teste e aguarda sua saída. Há contenção com
terminate, wait e kill em caso de necessidade.

O diário de transporte é gravado na raiz temporária com flush/fsync.

Um novo subprocesso inspeciona a mesma fixture. A inspeção:

- Bloqueia antes de nova coleta.
- Retorna ambiguous_state.
- Não altera o diário de transporte.
- Preserva manifestos, IDs e arquivos anteriores.
- Pode acrescentar somente um incidente.
- Termina com código 0.

As evidências confirmam encerramento dos filhos e dos leitores.
Isso não comprova durabilidade em queda de energia, falha física
de disco ou outro filesystem.

## 7. Execução reproduzível da regressão

Pré-requisitos: imagem local e wheels previamente disponíveis.
Não baixar dependências nem reconstruir imagem como parte deste comando.

Executar da raiz do repositório, em PowerShell. Ajustar somente
o caminho local dos wheels, se necessário.

```powershell
$projectPath = (Get-Location).Path
$pytestWheelDir = 'C:\Users\João\AppData\Local\Temp\weather-pytest-f2c33e49-7c82-4b7a-a25c-b7f999cedd44'

if (-not (Test-Path -LiteralPath $pytestWheelDir)) {
    throw "Wheels locais não disponíveis."
}

$p09EvidenceDir = Join-Path ([System.IO.Path]::GetTempPath()) `
    ("weather-p09-regression-" + [guid]::NewGuid().ToString())

New-Item -ItemType Directory -Path $p09EvidenceDir | Out-Null

$p09RegressionCode = @'
import subprocess
import sys

dependencies = "/tmp/weather-test-deps"

subprocess.check_call([
    sys.executable, "-m", "pip", "install",
    "--no-index",
    "--find-links=/tmp/test-wheels",
    "--target", dependencies,
    "--ignore-installed",
    "pytest==8.3.3",
    "packaging==24.2",
])

sys.path.insert(0, dependencies)

import pytest

print("Python:", sys.version.split()[0], flush=True)
print("pytest:", pytest.__version__, flush=True)

raise SystemExit(pytest.main([
    "/opt/airflow/tests",
    "--ignore=/opt/airflow/tests/test_weather_dag_structure.py",
    "-q",
    "-rs",
    "-x",
    "-p", "no:cacheprovider",
    "--basetemp=/tmp/p09-evidence/fixtures",
    "--junitxml=/tmp/p09-evidence/results.xml",
]))
'@

$p09RegressionCode | docker run --rm -i --pull never --network none `
  --entrypoint python `
  --workdir /tmp `
  --env PYTHONPATH=/opt/airflow `
  --env PYTHONDONTWRITEBYTECODE=1 `
  --env PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 `
  --mount "type=bind,source=${projectPath}\scripts,target=/opt/airflow/scripts,readonly" `
  --mount "type=bind,source=${projectPath}\tests,target=/opt/airflow/tests,readonly" `
  --mount "type=bind,source=${projectPath}\config,target=/opt/airflow/config,readonly" `
  --mount "type=bind,source=${pytestWheelDir},target=/tmp/test-wheels,readonly" `
  --mount "type=bind,source=${p09EvidenceDir},target=/tmp/p09-evidence" `
  jopecadata/logistics-weather-data-pipeline:1.0.0 `
  -B -

$p09ExitCode = $LASTEXITCODE
Write-Output "Codigo de saida: $p09ExitCode"
Write-Output "Evidencias: $p09EvidenceDir"
```

O comando acima apresenta de forma autossuficiente a seleção final
executada. Durante os incrementos, a seleção foi construída a partir
do mesmo código-base e executada por arquivo/cenário.

## 8. Resultado consolidado

Saída final fornecida por João:

```text
Python: 3.10.14
pytest: 8.3.3
192 passed in 111.06s
Codigo de saida: 0
```

Composição:

- 166 casos anteriores.
- 26 casos novos: 21 variantes de cenários e 5 verificações de suporte.
- Zero falhas, erros ou skips.
- Arquivo estrutural da DAG explicitamente excluído.

O JUnit anexado contém 192 casos e confirma esses contadores.
Sua duração interna é 110,072 s; o resumo do pytest informa 111,06 s.
São medidas de escopos distintos do mesmo processo de teste.

Raiz local da execução consolidada:

```text
C:\Users\João\AppData\Local\Temp\weather-p09-regression-b8304e30-07a9-4c23-8ad9-467abc17f7cc
```

Essa raiz contém fixtures, inventários e evidências sintéticas.
A existência em diretório temporário não garante retenção permanente.

## 9. Pacote de revisão e vínculo código–resultado

Pacote anexado aos chats executor e Airflow:

```text
weather-p09-t01-review-a3315529-3d65-4914-8954-f673ed0d5bc2.zip
```

SHA-256 do ZIP:

```text
7c9c4ef61a1a117581a6ededa654a13a35243c3c97ebb9d09e0c90cc3fd8b897
```

Conteúdo: quatro fontes Python, results.xml e 21 evidências JSON.
O ZIP usa nomes simples; os caminhos de origem estão abaixo.

Hashes SHA-256 dos bytes locais testados, conferidos contra o ZIP:

| Arquivo | SHA-256 |
|---|---|
| tests/helpers/__init__.py | fbe8972ffc9c20be7fd92596d4272951ca7a5fedf2fefb5c3b97cb48f1ae63f0 |
| tests/helpers/weather_resilience.py | ea80c4f7e5dee4d0e200d099928a93a368bddca247a18d84fc96e707221db673 |
| tests/test_weather_interruption.py | cba2a06b5ed86dfcbf29155d1e1af03a4cf553605abb54d65626745cf9f2dc8d |
| tests/test_weather_resilience_offline.py | 99e497d1e90532f74f0ecd98ed92ad7cac005315a203e7b4be5ca1d62f73422e |

Os recibos individuais incluem IDs, referências, contadores e
inventários/hashes correspondentes a cada cenário. Eles fazem parte
do pacote de revisão; não são dados operacionais nem novos contratos.

O hash do commit final será informado no encaminhamento central.
Esses SHA-256 identificam os bytes locais, não hashes de objetos Git.
Filtros de final de linha podem normalizar a representação no Git.

## 10. Parecer complementar Airflow

Airflow — Seção 4 emitiu parecer estático favorável à aderência
técnica, com ressalvas de rastreabilidade.

O revisor não executou testes, tasks ou DAG runs e não modificou arquivos.

Constatações:

- F01–F12 permanecem na fronteira E1/E2.
- Replay, parcialidade e integridade coerentes com a baseline.
- Retries HTTP não confundidos com retries Airflow.
- F05 utiliza sinalização determinística e contenção.
- Os novos arquivos não importam Airflow/DAG ou executam suas tasks.
- JUnit e 21 evidências internamente consistentes.

As ressalvas de procedência, hashes, escopo e limitações estão
incorporadas neste documento.

O parecer não valida centralmente o passo 09 nem libera E3.

## 11. Ocorrências e limitações

### Ocorrências de implementação

1. Após substituir o transporte, um bloco antigo permaneceu no helper,
   produzindo dois yield calls e RuntimeError: generator didn't stop.
   A execução apresentou 11 falhas e 5 aprovações, código 1.
   O avanço foi interrompido, a causa inspecionada e o bloco duplicado
   removido somente no helper. A repetição apresentou 16 aprovações.
   Nenhuma correção de produção foi realizada.

2. Uma execução coletou 17 casos porque o incremento F03 ainda
   não havia sido salvo. João identificou a causa.
   Após salvar, foram conferidos 18 casos e a evidência específica
   de F03. A execução anterior não foi tratada como aceite de F03.

### Limitações preservadas

- F12 caracteriza duas identidades para o mesmo ciclo; não executa
  duas coletas nem comprova unicidade de slot, exclusão mútua ou
  segurança concorrente.
- F03/F07/F11 não comprovam estados de task/DAG ou aprovação analítica.
- F04 impede a abertura do relatório após Raw; não simula escrita
  truncada ou falha física de disco.
- F04/F05 podem deixar tentativas sem relatório contratual persistido;
  os registros de teste não substituem essa auditoria ausente.
- F05 não comprova resistência a queda de energia.
- As barreiras Python têm os limites descritos na seção 4.
- HTTP 429 e outros mecanismos não foram acrescentados à política.
- Não foi implementada recuperação automática de rodada parcial.
- Não foi implementada política temporal, corte, fallback ou agenda.
- Os resultados são offline e sintéticos, sem garantia de SLA produtivo.

Nenhum defeito de produção foi corrigido neste pacote.

## 12. Preservação e rollback

Os dados e manifestos operacionais não foram montados nos contêineres.
Nenhuma DAG run, task, clear, unpause ou operação SQL foi executada
pelo pacote.

Para fixtures: preservar evidências antes de remover somente suas
raízes temporárias. Não apagar históricos operacionais.

Para código versionado: eventual rollback será por reversão dos commits
específicos deste pacote, após decisão central. Não usar reset
destrutivo nem alterar os commits funcionais aprovados.

A integração com main ainda não foi realizada nesta entrega.

## 13. Encerramento pendente

Após revisão do staging, commit, push e conferência do Git,
encaminhar o hash final e declarar:

P09-T01 — EVIDÊNCIA SUBMETIDA.

A avaliação e ratificação pertencem ao Planeamento central e a João.
Passo 09 permanece não validado.
E3, implementação temporal, agenda e passos 10–11 não liberados.