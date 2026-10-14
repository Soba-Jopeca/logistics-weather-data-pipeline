# Passo02 — Evidências de testes da extração

**Checkpoint:** CP-2026-10-13 v2

**Data:** 14/10/2026

**Estado:** execução concluída; evidência preparada para submissão ao Planeamento.

**Validação central:** pendente.

## Escopo autorizado

Consolidar verificações da extração em uma suíte automatizada e
versionada, independente da API Open-Meteo em tempo real.

Não foram alterados o extrator, a infraestrutura Docker, bancos,
cargas SQL ou DAGs. O passo06 não foi antecipado.

## Ambiente

- Windows e PowerShell.
- Ambiente virtual local do projeto.
- Python 3.13.
- pytest 8.3.3.

A execução em Python 3.10 não foi realizada neste passo.

## Arquivos

- `requirements-dev.txt`
- `tests/conftest.py`
- `tests/test_weather_window.py`
- `tests/test_weather_quality.py`
- `tests/test_weather_http.py`
- `tests/test_weather_persistence.py`
- `tests/test_weather_cli.py`

## Reprodução

Na raiz do projeto, com o ambiente virtual ativo:

~~~powershell
python -m pip install -r requirements-dev.txt
python -m pytest tests/ -q
~~~

Resultado informado pelo executor:

~~~text
73 passed in 0.31s
~~~

## Cobertura verificada

- Cadastro das cinco localidades e timezone America/Sao_Paulo.
- Janela inicial de 32 horários, limites UTC e fim exclusivo.
- Coleta anterior ao início, hora exata, coleta 18h07 → 19h,
  virada de dia, ciclo encerrado e sobreposição de ciclos.
- Identificação explícita do ciclo pela CLI.
- Cobertura completa, horário ausente e horário fora da janela.
- Unidades, integridade das séries, tipos e valores finitos.
- Rejeição de duplicatas, lacunas, ordem invertida, valores
  negativos de chuva/vento e timestamps inválidos.
- Nulos preservados sem conversão em zero.
- Associação de horário, cidade, run e medidas.
- Timeout simulado em requests.get para Sorocaba, atravessando
  tratamento HTTP, retries, run e batch, com continuidade das
  demais cidades.
- Retentativas limitadas, parâmetros preservados e ausência de
  repetição para HTTP 400 e 429.
- Bytes Raw, hash SHA-256, replay, nova versão e bloqueio de conflito.
- Falhas de gravação Raw, relatório individual e resumo de batch.
- Persistência do diagnóstico e estados de execução.
- Fluxo main para sucesso, nulos, coleta tardia, cobertura incompleta
  e ciclo encerrado.
- Argumentos inválidos interrompendo a execução.

## Isolamento

O conftest bloqueia chamadas HTTP reais. Respostas e falhas são
simuladas; datas relevantes são fixas; a persistência dos testes
usa pastas temporárias.

## Limitações

- A suíte verifica a extração e persistência local em arquivo.
- Não comprova publicação analítica, aptidão integral de produtos,
  fallback, frescor no uso ou SLA operacional.
- Não comprova idempotência SQL ou execução de DAG.
- O bloqueio de conflito preserva o original, mas a auditoria
  completa de incidentes de replay permanece pendente.
- Não foram simuladas interrupções do processo durante a escrita
  nem concorrência entre processos.
- DQ-01 a DQ-12 não estão integralmente implementadas.
- Não houve mudança nem validação da infraestrutura neste passo.

## Controle do gate

Após registrar o commit, submeter os arquivos, o diff, o resultado
da suíte, o commit e estas limitações ao Planeamento.

Declarar: `Passo02 — EVIDÊNCIA SUBMETIDA`.

A conclusão técnica não libera automaticamente o passo03.
Aguardar validação central e nova liberação confirmada por João.