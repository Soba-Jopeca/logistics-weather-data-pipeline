# P09-T02 — Evidências parciais de C1

## Estado e autorização

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
