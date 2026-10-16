# Passo06 — Interface Python e manifesto de extração

**Checkpoint:** CP-2026-10-13 v2

**Especificação:** AF-S4-CPv2-P05-v0.1

**Data:** 15/10/2026 — America/Sao_Paulo

**Estado:** implementação e testes concluídos; aguardando submissão e validação central.

**Baseline inicial:** 51be4ba.

## Escopo realizado

Interface Python independente de Airflow e da CLI, com manifesto
persistente, identidades preestabelecidas, snapshots congelados,
replay sem rede e bloqueio de estados ambíguos.

A CLI permanece disponível. Os formatos Raw/run/batch foram
preservados; os metadados de orquestração ficam separados.

Não foram criados ou executados DAGs, tasks, triggers, agendas,
tabelas ou cargas SQL. Imagem e Compose não foram alterados.

## Interface pública

Módulo: `scripts.weather_interface`.

```python
prepare_extraction(
    *,
    cycle_date,
    config,
    locations,
    project_root,
    orchestration_context=None,
    batch_id=None,
    run_ids=None,
)
```

Retorna `manifest_path`, `manifest_sha256`, `batch_id` e `cycle_date`.

```python
execute_extraction(
    *,
    manifest_path,
    manifest_sha256,
    project_root,
)
```

Retorna referências relativas, identidade da rodada, ciclo, estados,
contadores e modo `new_collection` ou `replay`.

Os retornos não contêm payload meteorológico, registros normalizados
ou a coleção completa dos relatórios. O limite de 8 KiB foi
verificado nos cenários de execução testados.

“Python pura” significa independente de Airflow e da CLI:
as funções executam I/O somente quando chamadas. Não chamam
argparse ou sys.exit.

## CLI preservada

```powershell
python -m scripts.extract_weather --cycle-date AAAA-MM-DD
```

Cada invocação normal prepara uma nova rodada. Replay é feito pela
interface Python com a referência do manifesto anterior; não há
opção nova de retomada automática na CLI.

Estados de extração bem-sucedidos retornam código zero.
Rodada parcial ou falha retorna código um.
Argumentos inválidos continuam retornando código dois.

A compatibilidade foi testada com HTTP simulado, sem coleta live.

## Identidade e persistência

- Batch e runs podem ser fornecidos antes da execução.
- Cada tentativa HTTP mantém seu próprio attempt_id.
- Mesmo contexto dag_id/Airflow run_id reencontra o manifesto.
- Mesmo batch_id explícito na preparação sem contexto reencontra
  o caminho da rodada.
- IDs, cadastro, configuração, ciclo e parâmetros são preservados.
- Configuração divergente ou manifesto inválido bloqueia a preparação.
- Marca de início é publicada exclusivamente antes da coleta.
- Relatórios individuais continuam sendo gravados por cidade.
- A conclusão vincula manifesto, marca de início e hashes dos artefatos.
- Resultado final íntegro pode ser reutilizado sem HTTP.
- Rodada parcial finalizada é preservada no replay.
- Estado iniciado sem conclusão, ou artefatos sem conclusão,
  bloqueia nova coleta automática.
- Conflitos e falhas tratadas geram incidente sanitizado quando
  a persistência está disponível.
- Falha ao gravar incidente é informada explicitamente.

Os novos documentos são escritos em arquivo temporário e publicados
sem sobrescrita por hard link. Falta de suporte no sistema de arquivos
produz erro explícito.

Caminhos de referências são resolvidos sob a raiz autorizada.
Artefatos locais de orquestração estão excluídos do Git.

## Organização

- `scripts/extract_weather.py`: coleta e validação existentes,
  configuração runtime, IDs/parâmetros opcionais e CLI.
- `scripts/weather_manifest.py`: caminhos, documentos imutáveis,
  construção e verificação do manifesto.
- `scripts/weather_interface.py`: preparação, execução, reconciliação
  de arquivos, replay e incidentes.
- `tests/`: regressão e novos cenários do passo06.
- `.gitignore`: exclusão de `data/orchestration/`.

O código antigo inalcançável de Campinas/24 horas foi removido.

## Testes

### Windows / Python 3.13 / venv

```powershell
python -m pytest tests/ -q
```

Resultado final:

```text
149 passed in 2.29s
```

Os 73 casos do passo02 permanecem na suíte. A fixture de endpoint
foi alinhada à URL aprovada, mantendo mocks e bloqueio de HTTP real.

### Contêiner / Python 3.10.14

Imagem existente:
`jopecadata/logistics-weather-data-pipeline:1.0.0`.

Imports dos quatro módulos, leitura das cinco localidades e
configuração por ambiente foram verificados.

A suíte foi executada em contêiner descartável com:

- rede desativada;
- scripts, config e tests montados somente para leitura;
- sem montagem de .env ou dados reais;
- pytest instalado apenas em /tmp/pytest-deps;
- plugins externos do pytest desativados;
- cache do pytest e bytecode desativados.

Versões do conjunto temporário:

- pytest 8.3.3
- packaging 24.2
- iniconfig 2.3.1
- pluggy 1.7.0
- exceptiongroup 1.3.1
- tomli 2.5.0
- typing-extensions 4.16.0

Resultado final:

```text
Python: 3.10.14
pytest: 8.3.3
packaging: 24.2
149 passed in 2.42s
```

A primeira instalação temporária selecionou packaging 26.3,
incompatível com a restrição de limits presente na imagem.
O conjunto temporário foi corrigido para packaging 24.2 e
a suíte repetida sem esse conflito. A imagem não foi modificada.

## Cobertura acrescentada

- IDs fornecidos, raiz explícita e preservação dos argumentos.
- Snapshots e bytes estáveis do manifesto.
- Rejeição de configurações e identidades inválidas.
- Referências inseguras e falhas de publicação de metadados.
- Hash e coerência interna do manifesto.
- Marca de início exclusiva.
- Reconciliação de relatórios, vínculos, validações e hashes.
- Replay sem rede para sucesso, nulos, parcial e falha total.
- Limite de 15 chamadas explícitas quando todas as cidades
  sofrem três timeouts.
- Interrupção após uma cidade, preservação dos arquivos válidos
  e bloqueio da retomada automática.
- Corrupção de Raw, relatório ou conclusão.
- Auditoria de conflitos/corrupção na preparação.
- Impossibilidade de persistir incidentes.
- Código de nível superior sem I/O autoral nas operações bloqueadas.
- Ausência de imports Airflow nos quatro módulos.

## Limitações preservadas

- Não há promessa de exactly-once HTTP.
- Não há recuperação automática de execuções interrompidas.
- Não há lock global entre rodadas diferentes ou proteção completa
  contra concorrência externa.
- O teste de interrupção usa exceção simulada, não encerramento
  forçado do sistema operacional.
- Não foi comprovada durabilidade contra queda de energia.
- Hard links dependem do suporte do sistema de arquivos.
- Falha de persistência pode impedir relatório individual,
  conclusão ou incidente; nesse caso, não se declara integridade.
- Falhas inesperadas podem propagar sem incidente imediato;
  a marca de início bloqueia uma retomada automática.
- Não houve coleta real neste passo.
- Retorno preparado para integração não comprova XCom ou
  execução de tasks Airflow.
- Success/validated_with_nulls não representam publicação
  ou aptidão integral de produtos.
- Agenda, prazos operacionais, frescor, fallback e SQL permanecem
  nos gates posteriores.
- Ressalvas herdadas dos passos03–04 continuam válidas.

## Encerramento e gate

Registrar externamente o diff, commit, branch, push e estado local
da entrega, evitando autorreferência do commit neste documento.

Submeter ao Planeamento como:

`Passo06 — EVIDÊNCIA SUBMETIDA`.

Passos07–11 permanecem NÃO LIBERADOS até nova decisão central
confirmada por João.