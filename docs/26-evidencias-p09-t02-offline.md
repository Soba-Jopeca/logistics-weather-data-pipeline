# P09-T02 — Evidências offline C1–C5

## Estado da entrega — 19/10/2026

**P09-T02 — IMPLEMENTAÇÃO E VALIDAÇÃO OFFLINE CONCLUÍDAS, PACOTE SUBMETIDO À REVISÃO CENTRAL.**

Esta conclusão refere-se ao escopo offline. P09-T02 e Passo 09 continuam
**NÃO VALIDADOS pelo Planeamento central**. Merge na main, E3, DAG runs/tasks,
agenda, infraestrutura e passos 10–11 não foram liberados nem executados.

- Mandato: CP-2026-10-13 v2, execução controlada C2–C5 ratificada por João.
- Baseline: `14ed58b9426edc7663b9d6420ba7af5db9e37479`.
- Branch exclusiva: `feat/p09-t02-offline-policy`.
- Última referência remota antes deste pacote: `eecb5943e6a89d28404dfc1fe17503c5e120f469`.
- Implementação e testes conduzidos pelo assistente, sob requisitos e autorizações
  de João. Os testes não demonstram domínio autoral individual de João.
- Os registros anteriores, inclusive falhas, estão preservados ao final.
  Seus estados de bloqueio descrevem aquele momento, não o estado desta entrega.

## Resultados e ambiente

Suíte final: **295 passed in 7.73s**, código de saída **0**.
JUnit: **295 testes, 0 falhas, 0 erros, 0 skips**. Inclui os testes P09-T01,
C1, integração pura dos produtores, parsing/serialização da DAG e timetables.
Não somar contagens de rodadas: há sobreposição entre elas.

| Rodada | Resultado | Significado |
|---|---|---|
| C1 original | 43 aprovados; regressão 235 | Referência aceite para continuidade |
| Reprodutor C2-T12-001 | 1 falha, saída 1 | Confirmação tardia podia ser aceita em replay |
| C2 corrigido + regressão | 248 aprovados, saída 0 | Gate anterior à integração C3 |
| C3 + regressão sem Airflow | 254 aprovados, saída 0 | CLI/coordenador e compatibilidade do núcleo |
| Primeiro gate Airflow | 275 aprovados, 10 falhas, saída 1 | Identificou Date do Pendulum |
| Timetables/entradas após correção | 24 aprovados, saída 0 | Corrigida normalização, sem mudar expectativas |
| Gate final completo | 295 aprovados, saída 0 | Todas as verificações versionadas, sem skips |

Versões efetivamente utilizadas: CPython **3.10.14**, Airflow **2.9.2**,
Pendulum **3.0.0**, pytest **9.1.1**, requests **2.34.2**, python-dotenv **1.2.4**,
tzdata **2026.5**, urllib3 **2.8.0**. Os pacotes já presentes foram reutilizados;
nenhum requirements, imagem ou serviço foi alterado. O executável temporário
3.10.14 precisou ser restaurado na mesma versão após reinicializações do ambiente.
O PYTHONPATH deu precedência aos pacotes do ambiente P09 e, depois, aos pacotes
Airflow 2.9.2 preexistentes para Python 3.10. Não houve mistura ABI 3.10/3.12.

Comando final (diretório da branch):

```bash
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=/workspace/scratch/5bbc9498ddbd/p09-offline-venv/lib/python3.10/site-packages:/workspace/scratch/5bbc9498ddbd/airflow-p07-venv/lib/python3.10/site-packages \
AIRFLOW_HOME=/workspace/scratch/5bbc9498ddbd/p09-airflow-synthetic \
AIRFLOW__CORE__LOAD_EXAMPLES=False AIRFLOW__CORE__UNIT_TEST_MODE=True \
/workspace/scratch/5bbc9498ddbd/p09-offline-venv/bin/python -m pytest \
-q -p no:cacheprovider tests \
--junitxml=/workspace/scratch/5bbc9498ddbd/p09-final-junit.xml
```

Os caminhos são do ambiente descartável usado nesta execução. Reproduzir exige
ambiente equivalente aprovado; o comando não instala dependências nem aciona
scheduler. O teste estrutural falha se Airflow não estiver disponível, em vez
de omitir o gate via skip.

## Arquitetura implementada e contratos

CLI e contexto Airflow manual/agendado → resolução de slot/D → claim exclusivo
→ manifesto imutável → dispatch exclusivo → barreira started por batch →
revalidação imediatamente antes do primeiro requests.get → coleta técnica →
completed íntegro → avaliação operacional → recibo → confirmação pós-gravação.

- Slot diário D 13h45 America/Sao_Paulo; admissão inclusiva até 14h00.
- Agendado: D vem do fim do intervalo diário; logical_date corresponde ao início
  e não seleciona D. Manual/CLI: D explícito. Slots vencidos não são reassociados.
- Chave compacta canônica SHA-256, independente de batch, produtor ou configuração.
- CLI/manual/agendado disputam o mesmo namespace. Só criação inédita entrega
  token ao fluxo proprietário. Dispatch e started impedem reentrada.
- Claim sem continuidade, dispatch existente, started sem completed e corrupção
  bloqueiam automaticamente; não há TTL, tomada de propriedade ou reparo.
- Primeiro transporte revalida admissão. As cidades e retries seguintes pertencem
  à mesma rodada admitida: não são novos inícios. A política HTTP 3 tentativas e
  backoff 1/2 segundos foi preservada. Timeout não promete pontualidade.
- Replay verifica manifesto original, claim, dispatch, início, conclusão, hashes,
  relatórios e Raw; não renova IDs, collected_at, prontidão ou coleta.
- Qualidade operacional exige as cinco localidades, janela integral de 32 horas
  por cidade e zero nulos. batch_status permanece técnico: success com nulos
  continua inelegível operacionalmente.
- Frescor: idade por cidade, pior idade consolidada, nominal 2700 s e máximo
  inclusivo 3600 s no consumo. Idade negativa/inválida bloqueia. Trata idade da
  resposta coletada, não atualização ou precisão do modelo meteorológico.
- Antes de 14h30, a avaliação é explicitamente `provisional=true`, com referência
  às 14h30. Atraso na disponibilização usa relógio novamente após a confirmação;
  o consumidor deve reavaliar no instante efetivo por `evaluate_for_consumption`.
- Sem resultado: `unavailable`; sem prova íntegra: inelegibilidade explícita.
  Não se procura batch anterior nem se executa fallback automático.

### Correção C2-T12-001

O rascunho publicava um indicador positivo antes da confirmação final da gravação.
Lançar uma exceção depois não impedia a leitura desse indicador em outra chamada.

Agora o leitor exige **readiness-confirmed.json**, ligado por hash ao recibo e ao
claim, produzido somente após observar a persistência de readiness.json às
14h15 inclusive ou antes. É um testemunho da confirmação já observada, não
um novo horário de prontidão nem uma reconstrução por mtime. Sua gravação pode
ocorrer depois da observação; até existir e estar íntegro o resultado é inelegível.
Se a observação for tardia, esse testemunho positivo não é criado. Interrupção
entre recibo e testemunho, falta de testemunho, corrupção ou falha de escrita
mantêm inelegibilidade em replay. Não há marca negativa opcional como única defesa.

O teste original conserva a expectativa de rejeição às 14h15:00.000001.
Há também casos positivos em 14h15 exato, persistência falhando em cada estágio,
confirmação ausente/corrompida/divergente e disponibilização atrasada.

### Outras correções internas

1. Normalização de `pendulum.Date` para `datetime.date` ao resolver D. Os testes
   reais de timetable revelaram a diferença; não foram relaxados para ignorá-la.
2. Replay verifica também dispatch; corrupção desse registro não é ignorada.
3. Tempo de disponibilização não fica congelado antes da escrita do testemunho.
4. Avaliação provisória separada da referência efetiva de consumo.

### Novos controles (schema_version 1)

Todos ficam fora de Raw/run/batch, sob `data/orchestration/slots/<sha>/`:

| Registro | Campos e finalidade |
|---|---|
| claim.json | slot/hash, política, owner/token, batch/run IDs, fingerprint, claimed_at, manifesto/hash |
| dispatch.json | slot/claim/manifest hashes, batch, dispatch_id, dispatched_at; aquisição exclusiva |
| assessment-started.json | claim hash, token, started_at; avaliação não retomada automaticamente |
| assessment.json | política, claim/batch/manifest, verificação técnica/hashes, assessed_at, motivos de qualidade e collected_at por cidade |
| readiness.json | referência/hash de assessment, instante pós-gravação observado, on_time; isoladamente não autoriza consumo |
| readiness-confirmed.json | claim hash, referência/hash de readiness, confirmed_at posterior à gravação do recibo e até o corte |
| events/<uuid>.json | rejeição do primeiro transporte, claim/batch e decisão temporal |

Imutabilidade significa não sobrescrever pelo protocolo, não proteção contra
um operador que edite arquivos. Os controles pressupõem namespace confiável.

## Matriz T01–T20 → teste → evidência

Todos os testes abaixo constam do JUnit final preservado neste documento.
Nomes prefixados abrangem as parametrizações identificadas no XML.

| Cenário | Arquivo(s) em tests/ e teste principal | Entrada/verificação | Resultado |
|---|---|---|---|
| T01 | test_weather_timetables.py::test_t01_timetable_semantics | DataInterval diário vs Trigger intervalo zero; logical_date, run_after, D e serialização | PASS |
| T02 | test_weather_timetables.py::test_t02_* | Retomada com/sem histórico, antes/no slot e após admissão; candidato seguinte após intervalo já concluído | PASS |
| T03 | test_weather_temporal.py::test_t03_admission_boundaries | Microssegundos antes/depois de 13h45 e 14h00; extremos inclusivos | PASS |
| T04 | test_weather_entrypoints.py::test_t04_revalidation_at_transport_no_http; test_weather_temporal.py::test_t04_* | Fila até 14h00:00.000001; zero transporte; reserva preservada | PASS |
| T05 | test_weather_temporal.py::test_t05_cycle_comes_from_interval_end | Viradas de dia/mês/ano, D pelo fim do intervalo | PASS |
| T06 | test_weather_temporal.py::test_t06_*; test_weather_entrypoints.py::test_t06_* | Sem timezone, intervalo/contexto inválido, overrides e tipo de run não suportado | PASS |
| T07 | test_weather_slots.py::test_t07_*; test_weather_entrypoints.py::test_t07_* | Dois processos spawn, um claim; contagem de transporte simulado [0,5] | PASS |
| T08 | test_weather_slots.py::test_t08_*; test_weather_entrypoints.py::test_t08_* | CLI/manual/agendado, mesma chave, conflito, contexto válido e inventário AST dos produtores | PASS |
| T09 | test_weather_slots.py::test_t09_*; test_weather_entrypoints.py::test_t09_* | Encerramento de processo após link e falha antes do manifesto; sem tomada/reparo | PASS |
| T10 | test_weather_slots.py::test_t10_*; test_weather_entrypoints.py::test_t10_* | Dispatch de uso único e started sem completed | PASS |
| T11 | test_weather_operational.py::test_t11_*; test_weather_entrypoints.py::test_t11_* | Replay sem HTTP, manifesto original e inventário de bytes preservados | PASS |
| T12 | test_weather_operational.py::test_t12_* | Corte exato, tardio 1 µs, testemunho ausente/corrompido e reprodutor C2-T12-001 | PASS |
| T13 | test_weather_operational.py::test_t13_* | Respostas às 14h00; reconciliação às 14h16; replay inelegível | PASS |
| T14 | test_weather_temporal.py::test_t14_freshness_boundaries | Idades 45/60 min, acima de 60 e negativas | PASS |
| T15 | test_weather_temporal.py::test_t15_*; test_weather_operational.py::test_t15_* | Pior cidade, consumo atrasado e escrita do testemunho demorando além do frescor | PASS |
| T16 | test_weather_operational.py::test_t16_* | Nulos, janela parcial, Raw corrompido, dispatch corrompido | PASS |
| T17 | test_weather_operational.py::test_t17_t20_no_fallback_to_another_cycle | Resultado íntegro de D não preenche D+1 | PASS |
| T18 | test_weather_slots.py::test_t18_*; test_weather_operational.py::test_t18_* | Falha de link/fsync ou escrita em cada estágio; sem alternativa insegura | PASS |
| T19 | test_weather_slots.py::test_t19_*; test_weather_entrypoints.py::test_t19_* | Fingerprint divergente; original preservado, sem segunda rodada | PASS |
| T20 | test_weather_operational.py::test_t17_t20_no_fallback_to_another_cycle | Slot ausente retorna indisponibilidade e não altera arquivos | PASS |

Fixtures: cadastro estático das cinco cidades, respostas sintéticas de 32 horas,
relógios UTC/São Paulo fixos ou sequenciais, `tmp_path`, snapshots SHA-256,
Pipes com eventos ready/go/result e timeout de recebimento. Filhos usam spawn,
barreiras próprias e são finalizados com join/terminate/kill quando necessário.
Não são testes de carga, de filesystem distribuído nem execução operacional.

A regressão P09-T01 permanece sem edição de seus arquivos, inclusive F01–F12
presentes nas suítes de resiliência/interrupção. O cenário histórico F12 sobre
chamada direta ao núcleo continua válido: esse caminho residual não passa pelo
coordenador e impede afirmar unicidade global contra código arbitrário.

## Isolamento e limites

- `requests.Session.request` bloqueado pela fixture geral. Respostas HTTP dos
  cenários são mocks; não houve chamada à API meteorológica.
- Testes de controles/integração/concorrência usam bloqueio de DNS/conexões e
  auditoria de escritas temporárias; trabalhadores possuem barreiras próprias.
- Parsing usa barreiras para dados/configuração, SQL connect, execução de
  operadores, corpos de tasks e DAG.test. Timetable chama apenas cálculo.
- `bwrap --unshare-net` continuou indisponível; não houve escalada. As barreiras
  Python são evidência limitada, não isolamento universal de kernel/processo.
- Nenhuma garantia de semântica de hardlink, durabilidade de diretório ou queda
  de energia foi demonstrada para o volume Windows/Docker operacional.
- Relógios e namespace são confiados. Sem assinaturas, NTP atestado, proteção
  contra edição externa ou unicidade entre raízes/filesystems diferentes.
- São suportados CLI principal e adaptadores Airflow manual/agendado. Chamadas
  diretas ao coletor legado ou versões antigas ficam fora do protocolo.
- Schedule permanece None, catchup False, pausa inicial True, retries 0;
  sem alterações de timeouts, concorrência, Docker, PostgreSQL ou dependências.
- Não há monitor externo/alerta agendado: indisponibilidade é retornada quando
  o avaliador é consultado. Não confundir silêncio com disponibilidade.

## Compatibilidade e rollback

Raw/run/batch, manifesto, janela e documentos 23–25 têm o mesmo conteúdo da
baseline. A interface recebe apenas um argumento opcional interno para a
barreira de primeiro transporte. Chamadas antigas ao núcleo conservam seu
comportamento; CLI principal passa a devolver 1 para inelegibilidade operacional,
mesmo quando batch_status é success. Não há reclassificação dos artefatos antigos.

Manifestos históricos sem scheduled_slot não são inferidos/associados a slots.
Histórico de batches e runs não foi reescrito. A nova DAG preserva os três task IDs,
mas XCom do novo protocolo tem referências de slot; não reutilizar XCom antigo
para executar o código novo. Migração operacional de runs antigas exige inspeção
própria, fora deste gate offline. Nenhuma run foi alterada nesta sessão.

Rollback conservador: manter agenda pausada; retirar esta branch da proposta ou
reverter exclusivamente seus commits autorizados, preservando controles/Raw e
histórico. Não apagar claim/dispatch/started para permitir repetição. Não executar
CLI antiga como compensação: ela contorna o controle diário. Se houver adoção
operacional futura, o rollback dependerá de inventário de runs/slots e autorização
própria, sem reaproveitar automaticamente reservas ambíguas.

## Inventário fechado e hashes

Commit local de implementação/testes: `774a9cc968f26c873b53e2ad1ddb109ac12a52ef`.

SHA-256 do diff binário de scripts/dags/tests contra 14ed58b: `ddebc088838fa1155adfc6ba2962e0a83cdb5e6f0db861f82214f18cb00daa2d`.

São 16 arquivos no pacote contra a baseline, incluindo este documento.
O próprio documento não recebe hash autorreferente; seu blob Git identifica a versão.

| Arquivo | SHA-256 do conteúdo testado |
|---|---|
| `dags/weather_extract.py` | `37e22cd3c007f10517e609cf9a5d27f3091b73c4fbd1366736145d7a34d19568` |
| `scripts/extract_weather.py` | `1bd23fec467ecf9523b8a7973519e26c5721bd2c519913275d596e93373c0b84` |
| `scripts/weather_daily.py` | `eb81b40ce0228fc484034e96d12cc6f2c75322ca5c776d6548c346abb423c920` |
| `scripts/weather_interface.py` | `1b589c0cfb1ab01465634ac34d97fcf3e121f35dc4b87c0533a7b79095ebc49c` |
| `scripts/weather_slots.py` | `48399aa1249602c462655b027419d2c0a170ffc173ee441ad08f6866008e73bb` |
| `scripts/weather_temporal.py` | `14fb428e0c417da942905d82ff14d96c49d194c7129da4bba88f2803fd475112` |
| `tests/helpers/weather_temporal.py` | `95294938731fc387f27f78e01f303b4173761e4bc34de2b6be7ad900b137211b` |
| `tests/test_weather_cli.py` | `ba0d29446d9b370b23789f801974c033102e58ed90a6f3330169fc33c92156f9` |
| `tests/test_weather_dag_structure.py` | `f03a31df0c1fa0a560238fac2aaf08fb229fd60238eae0d9652adb7ba75ccda3` |
| `tests/test_weather_entrypoints.py` | `61d401985fd134b3cc0b6685f5247131e0b2f3a18f3e314a002f79686108a6a0` |
| `tests/test_weather_imports.py` | `e1426613255abe40c17c1e2b16756370b8029ef8e82994a860096db5ace5a6b9` |
| `tests/test_weather_operational.py` | `f1f11bcd74289bcf700c4b56d0b7a4bd582bac595100581b438179867e98becb` |
| `tests/test_weather_slots.py` | `102e99d7787c9bb08e111ce7f91df2836d3086157b583a68afe7f1c8047aeb2f` |
| `tests/test_weather_temporal.py` | `4ff6f83937d70cac518214b44caaf980569c2da1bdd3cae605341890db1fbf07` |
| `tests/test_weather_timetables.py` | `43d9489cc91c049f4536264dcf8c6de04365d498fd2f4758cab01f49be10ae82` |

## Contagem final por módulo

| Módulo | Casos aprovados |
|---|---:|
| `tests.test_weather_cli` | 7 |
| `tests.test_weather_dag_structure.WeatherDagStructureTests` | 8 |
| `tests.test_weather_entrypoints` | 16 |
| `tests.test_weather_execution` | 14 |
| `tests.test_weather_http` | 10 |
| `tests.test_weather_identity` | 5 |
| `tests.test_weather_imports` | 14 |
| `tests.test_weather_interface` | 20 |
| `tests.test_weather_interruption` | 2 |
| `tests.test_weather_manifest` | 15 |
| `tests.test_weather_manifest_snapshot` | 9 |
| `tests.test_weather_operational` | 20 |
| `tests.test_weather_persistence` | 9 |
| `tests.test_weather_quality` | 32 |
| `tests.test_weather_reconciliation` | 6 |
| `tests.test_weather_resilience_offline` | 24 |
| `tests.test_weather_slots` | 16 |
| `tests.test_weather_temporal` | 27 |
| `tests.test_weather_timeout` | 16 |
| `tests.test_weather_timetables` | 10 |
| `tests.test_weather_window` | 15 |

## Evidências JUnit preservadas

O XML final integral está comprimido abaixo com gzip/base64. Pode ser recuperado
com `gzip.decompress(base64.b64decode(texto))`, usando somente a biblioteca padrão.
Não contém credenciais ou respostas da API; apenas resultados e metadados sintéticos.

SHA-256 do XML descomprimido: `e6086edd873497723eed030c97cedd9098264955f46ca06934fdbabbc2fa344b`.

<details>
<summary>JUnit final completo — 295 casos</summary>

```text
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
```

</details>

Histórico de relatórios (não somar contagens):

| Artefato | Testes | Falhas | Erros | Skips | SHA-256 |
|---|---:|---:|---:|---:|---|
| p09-c1-junit.xml | 43 | 0 | 0 | 0 | `92f8869829223a3047e09b701c814d6610ec62a289b7b4f1dff8e01e9f609cc0` |
| p09-c2-regression-junit.xml | 248 | 0 | 0 | 0 | `1145c8cee5073552c414ee6dfd7223379a74229398e39feac78716410ca71fc7` |
| p09-c2-t12-junit.xml | 1 | 1 | 0 | 0 | `89d51a9a98e503c6b6de91e05625406ee73ee5d41d018d5e78f0f45d527e5596` |
| p09-c3-regression-junit.xml | 254 | 0 | 0 | 0 | `82c2b8c161229cd57a31db27a8f3457b1eb51f6a44bcade7b380507b0dde6689` |
| p09-c4-directed-junit.xml | 24 | 0 | 0 | 0 | `8e1fbfd327e4f26026133b9499e135fbdc736a118d7d24df3c1a97294bc3c746` |
| p09-c4-junit.xml | 285 | 10 | 0 | 0 | `4b196f90689e64d583346a20c82370be4319532027507808e7f0b751cc1fffaf` |
| p09-final-junit.xml | 295 | 0 | 0 | 0 | `e6086edd873497723eed030c97cedd9098264955f46ca06934fdbabbc2fa344b` |
| p09-regression-junit.xml | 235 | 0 | 0 | 0 | `96b2fb319d26994e88cd311057c7ccb9b4515bbd48f1f7df1ec5b41cb8395c87` |

## Publicação e decisão seguinte

Publicação exclusivamente na branch autorizada. O HEAD remoto final e a conferência
de equivalência de conteúdo serão fornecidos na devolução central após a publicação.
O commit que contém esta versão do documento identifica o pacote publicado.
O aceite central e a ratificação de João são necessários para declarar P09-T02
validado; merge/E3/agenda continuam em gate separado.

## Histórico preservado — registros anteriores à consolidação

## Ocorrência C2-T12-001 — bloqueio local em 19/10/2026

Após o parecer central de continuidade C2–C5, foi iniciado o rascunho local
de `scripts/weather_daily.py` e o teste
`tests/test_weather_operational.py`. Ambos permanecem não integrados e
não publicados; o coordenador ainda depende de uma interface de transporte
não implementada. Não são uma entrega funcional de C2/C3.

O teste dirigido T12 revelou promoção indevida de elegibilidade no replay:

1. Cinco respostas sintéticas completas são coletadas às 14h00; nenhum HTTP
   real. A conclusão técnica é montada pelo núcleo existente, sem DAG/tasks.
2. Avaliação inicia às 14h14 e sua persistência é observada às 14h15.
3. O rascunho grava `readiness.json` com `on_time=true` antes da última
   confirmação de persistência.
4. O relógio após essa gravação marca 14h15:00.000001; a reconciliação lança
   erro, mas o recibo antecipadamente positivo permanece no filesystem.
5. Uma leitura às 14h30 retorna `eligible=true`, contrariando o resultado
   esperado `false`. A exceção na primeira chamada não protege o replay.

Execução CPython 3.10.14, PYTHONDONTWRITEBYTECODE=1:

```text
python -m pytest -q -p no:cacheprovider tests/test_weather_operational.py
FAILED test_t12_late_receipt_must_remain_ineligible_on_replay
assert True is False
1 failed in 0.14s
```

Saída 1; JUnit temporário `p09-c2-t12-junit.xml`. Rede bloqueada pelo helper,
requests.get substituído por respostas sintéticas, escrita da fixture
restrita à raiz temporária. O relógio sintético representa a observação
pós-gravação; não houve medição de latência de um volume operacional.

Hashes SHA-256 do rascunho/reprodutor nesse ponto:

- weather_daily.py: `7448dac033bd1725f0ddf6d5dec992c5687e630745d423dd7d26cd8f290a8247`
- test_weather_operational.py: `7990863465f47badd3cb5bb36b574d872993c50fd4e36695cb7d8d76577d0dc6`
- JUnit: `89d51a9a98e503c6b6de91e05625406ee73ee5d41d018d5e78f0f45d527e5596`

Conduta conforme parecer: interrompido o avanço dependente C2–C5 e devolvida
a ocorrência central. Nenhuma alteração da CLI, DAG ou interface foi feita.
O C1 publicado permanece no estado anteriormente aceite para continuidade.
Os 235 resultados anteriores não validam este rascunho; nesta rodada houve
somente o teste dirigido acima, que falhou.

Correção necessária: o leitor não pode aceitar um indicador de pontualidade
calculado antes da confirmação exigida. O protocolo de prova de prontidão
precisa tratar conclusão tardia e interrupção entre publicações de forma
conservadora, inclusive quando não for possível gravar uma marca posterior
de rejeição. Apenas capturar a exceção ou acrescentar uma marca de falha
opcional não corrige a janela de inconsistência. Preservar o corte aprovado;
qualquer redefinição do recibo que constitui prontidão exige revisão central.

Estado: **C2 BLOQUEADO — OCORRÊNCIA SUBMETIDA**, sem validação final de
P09-T02 e sem publicação deste rascunho.

## Atualização após autorização de publicação e ambiente — 19/10/2026

C1 passou nos testes offline abaixo. O restante deste documento conserva o
registro histórico da verificação anterior, cujos bloqueios de Python/pytest
foram resolvidos nesta atualização. P09-T02 e passo 09 continuam NÃO VALIDADOS.

- Ambiente descartável: CPython 3.10.14, pytest 9.1.1; dependências instaladas
  a partir do requirements.txt existente, sem modificá-lo.
- C1: `python -m pytest -q -p no:cacheprovider tests/test_weather_temporal.py tests/test_weather_slots.py`:
  **43 passed in 1.47s**, saída 0.
- Regressão: `python -m pytest -q -p no:cacheprovider tests --ignore=tests/test_weather_dag_structure.py`:
  **235 passed in 5.04s**, saída 0 (inclui os 43 testes de C1; não somar).
- Ambas as execuções usaram PYTHONDONTWRITEBYTECODE=1 e produziram JUnit
  temporário externo ao repositório, respectivamente p09-c1-junit.xml e
  p09-regression-junit.xml. Os XML não integram esta publicação.
- Foram exercitados os testes versionados de concorrência, interrupção,
  dispatch, fronteiras temporais e falhas de persistência de C1.
- O bloqueio HTTP da suíte e as barreiras de rede/escrita dos testes de slots
  permaneceram ativos, inclusive nos trabalhadores sintéticos. Não houve
  chamada meteorológica real. Isso não comprova isolamento por namespace
  nem as garantias do filesystem operacional compartilhado.
- Airflow/DagBag/timetable não foram executados nesta rodada. C2/C3 e o
  restante de T01–T20 continuam pendentes; não há unicidade ponta a ponta.
- Os seis arquivos do commit local 14a7e2d foram publicados pelo conector
  GitHub na branch feat/p09-t02-offline-policy, com head a16f457 antes desta
  atualização. O Git HTTPS não tinha credenciais; o conector gerou commits
  próprios. Comparação local de árvores: nenhuma diferença de conteúdo.
- Main, schedule, retries, Compose, PostgreSQL e contratos existentes não
  foram alterados. Não houve merge na main, E3 ou execução de DAG/tasks.

## Registro histórico: estado e autorização

- Checkpoint: CP-2026-10-13 v2.
- Baseline: `14ed58b9426edc7663b9d6420ba7af5db9e37479`.
- Branch: `feat/p09-t02-offline-policy`.
- Registro: 19/10/2026, America/Sao_Paulo.
- João aprovou a proposta e autorizou validação, continuidade, commit e push.
- Estado: C1 implementado, com verificações complementares; NÃO VALIDADO.

P09-T02, passo 09 e a suíte T01–T20 não estão validados. C2–C5 não foram
implementados. Este registro parcial não significa fechamento do pacote.
Agenda, E3, DAG runs, chamadas meteorológicas e passos 10–11 não foram executados.

## Escopo efetivamente escrito

- `scripts/weather_temporal.py`: resolução de slot/D, admissão, gancho de
  primeiro transporte e avaliação pura de frescor.
- `scripts/weather_slots.py`: identidade, claim exclusivo, inspeção e dispatch.
- `tests/helpers/weather_temporal.py`: fixtures e trabalhadores sintéticos.
- `tests/test_weather_temporal.py`: testes propostos de temporalidade/frescor.
- `tests/test_weather_slots.py`: testes propostos de claim, corrida/interrupção.
- Este documento de evidências parciais.

Os novos módulos ainda não estão integrados à DAG ou à CLI. A exclusividade
de produtores suportados não está implementada ponta a ponta. Dispatch está
escrito, mas não foi exercitado na verificação complementar.

## Ambiente encontrado e bloqueios

O Python disponível é 3.12.14. Não foram encontrados Docker utilizável,
Python 3.10.14, pytest ou python-dotenv utilizáveis nesse runtime.
A pasta preexistente `airflow-p07-venv` contém parte dos pacotes de Airflow,
mas o executável Python original não existe. Não se tratou essa pasta como
ambiente operacional válido nem se misturaram extensões Python 3.10 com 3.12.

Nenhuma dependência foi instalada ou atualizada. Não houve mudança de
requirements, imagem, Compose ou PostgreSQL.

A tentativa de isolamento complementar com `bwrap --unshare-net` terminou
com código 1, antes de executar o programa:

```text
bwrap: Creating new namespace failed: Operation not permitted
```

Esse mecanismo de isolamento não foi considerado validado. Não houve escalada
de privilégios ou alteração das permissões do ambiente.

## Verificação complementar executada

Foi executado um programa ad hoc via `PYTHONDONTWRITEBYTECODE=1 python -B -`,
na raiz da branch, usando somente biblioteca padrão e os módulos puros.
Não houve execução de pytest, import da DAG ou chamada ao coletor.

O programa bloqueou `socket.getaddrinfo`, `socket.create_connection`,
`socket.socket.connect`, `connect_ex` e `sendto` antes de importar os módulos
autorais. Esses bloqueios Python não equivalem a isolamento universal de rede.
As escritas do programa foram limitadas por sua lógica a um TemporaryDirectory
novo com prefixo `weather-c1-check-`; a raiz foi descartada ao término.
Não houve barreira universal de escrita nessa execução complementar.

Verificações e entradas:

| Verificação | Entrada | Resultado |
|---|---|---|
| Sintaxe | Cinco novos fontes, `ast.parse(feature_version=(3,10))` e `compile` | PASS no runtime 3.12; não comprova runtime 3.10 |
| Admissão | D=2026-10-13; um microssegundo antes de 13h45, 13h45, 14h00, um microssegundo depois | False, True, True, False |
| Slot vencido | Mesmo slot, relógio no dia seguinte | `start_expired`; D preservado |
| Gancho | Primeiro transporte às 14h00:01 | `DailyAdmissionError` |
| Frescor | Cinco cidades com idades 2700, 3600, 3601 e -1 segundos, em cenários separados | True, True, False, False |
| Chave | D=2026-10-13, São Paulo | JSON compacto com slot UTC 16h45 |
| Primeiro claim | Candidato sintético íntegro | `created=True` |
| Claim repetido | Mesmo candidato e bytes | `created=False`; bytes preservados |
| Configuração divergente | Mesmo slot, outro `input_sha256` | `conflict`; original preservado |
| Inspeção | Claim original | Documento original recuperado |

Saída final:

```text
PASS: gramatica Python 3.10 e compilacao dos cinco arquivos no Python 3.12
PASS: fronteiras, frescor, guard, chave canonica, claim repetido e conflito
LIMITACAO: verificacao stdlib complementar; nao pytest, nao Airflow, nao concorrencia, nao T01-T20 completo
```

Código de saída: 0. Não se atribui a essa verificação uma contagem de casos
pytest nem cobertura integral dos cenários. O comando ad hoc não é substituto
dos testes versionados e não gerou JUnit ou recibos individuais T01–T20.

## Conferência de escopo e limitações

A comparação dos arquivos existentes de produção com `14ed58b` retornou
código 0: extrator, interface, manifesto, janela, DAG, config e requirements
permaneceram inalterados. Os documentos históricos 23–25 foram preservados.

A cópia de trabalho anterior, separada desta branch, mantém as alterações
preexistentes nos documentos 17 e 18. Elas não integram este pacote.

Pendências que impedem aceite:

- Executar pytest no ambiente-alvo com dependências aprovadas e isolamento.
- Exercitar concorrência, interrupção, dispatch e falhas de persistência.
- Executar regressão P09-T01 e verificar import/parsing/timetable 2.9.2.
- Implementar e revisar C2/C3 e os demais testes da proposta.
- Produzir evidências consolidadas antes de qualquer declaração de validação.

O pacote parcial pode ser preservado na branch como trabalho em andamento.
Não integrar à main como implementação temporal validada. Retomada depende
de ambiente de testes utilizável; eventual instalação/recriação de ambiente
precisa respeitar a restrição vigente sobre dependências e infraestrutura.

## Rollback

Preservar a branch e os registros. Não há integração operacional a desfazer:
DAG/CLI permanecem na baseline. Eventual reversão deve atingir somente os
commits deste pacote, sem apagar artefatos históricos ou alterações alheias.
