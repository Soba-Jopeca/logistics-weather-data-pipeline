# Logistics Weather Data Pipeline

Pipeline de dados meteorológicos para apoio ao planejamento logístico, desenvolvido como projeto autoral de Engenharia de Dados em um **cenário empresarial inteiramente fictício**.

## Contexto de negócio

**Consultoria simulada:** Phoenix Data
**Cliente fictício:** AuroraLog Transportes & Distribuição S.A.
**Consultor responsável:** Mr. João Caneca
**Projeto:** PHD-AL-2026-001

No cenário, o planejamento de transportes consulta previsões meteorológicas manualmente, em fontes diferentes e sem histórico padronizado. A iniciativa busca organizar previsões por localidade e horário, preservar a rastreabilidade das coletas e disponibilizar informações antes do planejamento diário, iniciado aproximadamente às **15h (America/Sao_Paulo)**.

O objetivo é **apoiar decisões humanas**, e não automatizar alterações de rotas ou demonstrar causalidade entre clima e atrasos. As entrevistas, as empresas, as métricas operacionais e as aprovações documentadas são simulações; não representam cliente ou contrato reais.

## Objetivo e escopo do MVP

- **Localidades-alvo:** Campinas, São Paulo, Sorocaba, Jundiaí e Ribeirão Preto (SP).
- **Fonte:** API de previsão meteorológica da Open-Meteo.
- **Horizonte inicial:** 24 horários consecutivos por localidade e extração.
- **Variáveis:** precipitação, temperatura e velocidade do vento.
- **Saída esperada:** dados estruturados por localidade e horário, com histórico de previsões e metadados das execuções.
- **Necessidade operacional:** disponibilizar informações atualizadas antes das 15h; frequência, margem e regras de frescor serão refinadas no discovery.

A implementação atual do extrator abrange **somente Campinas**, com execução manual. As cinco localidades integram o escopo-alvo aprovado **na simulação**, não o estado de implementação.

## Documentação e governança

| Documento | Finalidade | Estado |
|---|---|---|
| [Business Case v1.1](docs/01-business-case-v1.1.md) | Problema, oportunidade, objetivos, benefícios esperados e restrições | Baseline do cenário |
| [Discovery, Requisitos e Escopo v1.1](docs/02-discovery-requisitos-escopo-v1.1.md) | Registro mestre de entrevistas, requisitos, decisões, premissas e gates | Em evolução; Reunião 1 encerrada |
| [ATA-KO-001 — Reunião 1](docs/04-ata-reuniao-01-kickoff-aprovada-simulacao.md) | Decisões DEC-001 a DEC-006 e aprovação fictícia do Kickoff | Aprovada **na simulação** |
| [Reunião 2 — Abertura e agenda](docs/05-reuniao-02-abertura-e-agenda.md) | Preparação do mapeamento AS-IS/TO-BE | Preparada; ainda não realizada |

As decisões sobre processo e consumo serão consolidadas na Reunião 2; contrato de dados, qualidade e critérios de aceite nas reuniões seguintes. O escopo final ainda **não** está homologado.

## Discovery — Reunião 2 (AS-IS / TO-BE)

A Reunião 2 foi encerrada **na simulação empresarial**, com os processos e decisões documentados. Os diagramas abaixo permanecem editáveis no Excalidraw:

- [AS-IS — Processo atual](docs/diagrams/reuniao-02-as-is.excalidraw)
- [TO-BE — Arquitetura de referência](docs/diagrams/reuniao-02-to-be.excalidraw)
- [ATA-R2-001 — Reunião 2](docs/06-ata-reuniao-02-processos-as-is-to-be.md)
- [Discovery, Requisitos e Escopo v1.2](docs/02-discovery-requisitos-escopo-v1.2.md)

O AS-IS representa consultas manuais descentralizadas. O TO-BE representa arquitetura planejada; o extrator manual e JSON bruto para Campinas são as funcionalidades implementadas até aqui. O MVP prevê consultas/tabela consolidada, sem dashboard interativo obrigatório. A biblioteca gráfica de terceiros não integra o repositório.

## Discovery — Reunião 3 (Contrato, Qualidade e Governança)

A Reunião 3 foi **encerrada apenas na simulação**, como baseline de requisitos para desenvolvimento. Não comprova implantação nem aceite real.

- [ATA-R3-001 — decisões e responsabilidades](docs/07-ata-reuniao-03-contrato-dados-aprovacao-simulada.md)
- [Contrato de dados meteorológicos v0.1](docs/08-contrato-dados-weather-v0.1.md)
- [Matriz de Data Quality v0.1](docs/09-matriz-qualidade-weather-v0.1.md)

O contrato define versões por execução, identidade estável das cinco localidades, rodada/coleta/tentativa HTTP com auditoria, janela de planejamento fixa de 32 horas, coletas periódicas em horas pares, corte às 14h15 na rodada pré-planejamento, publicação até 14h30, limite de frescor de três horas, DQ por produto, fallback controlado e reprocessamento idempotente. **Tudo isso é requisito planejado**, não funcionalidade já entregue pelo `extract_weather.py`.

## Arquitetura técnica de referência (planejada)

`Open-Meteo API → Python + JSON bruto → PostgreSQL + SQL/ELT → consultas analíticas`

- **Docker:** ambiente de execução local reproduzível.
- **Apache Airflow:** agendamento e orquestração.
- **pytest e avaliação de Soda:** testes e qualidade.
- **GitHub Actions:** CI/CD.

As ferramentas compõem a arquitetura de referência previamente definida. Banco de dados, containers, Airflow e CI/CD **não estão declarados como implementados**.

## Etapas de desenvolvimento

1. Documentar problema, requisitos e decisões de discovery.
2. Preparar o ambiente Python e explorar a Open-Meteo.
3. Definir contrato de extração e validar o extrator manual para Campinas.
4. Ampliar a extração às localidades aprovadas.
5. Persistir e transformar dados no PostgreSQL com SQL.
6. Containerizar com Docker e orquestrar com Airflow.
7. Implementar testes automatizados e verificações de qualidade.
8. Configurar GitHub Actions e validar a entrega ponta a ponta.

## Estado atual — validações realizadas localmente

Extrator manual para Campinas implementado em Python. Validações informadas:

- Requisição à Open-Meteo com retorno HTTP 200.
- Conferência de 24 horários consecutivos e das três séries meteorológicas.
- Validação de unidades, fuso, tipos numéricos e contagem de nulos.
- Gravação e releitura de JSON contendo metadados e resposta original.
- Coletas sucessivas preservadas em arquivos distintos.
- Importação do módulo sem executar uma coleta.
- Configuração inválida interrompendo a execução com código 1.

O tratamento básico de erros de comunicação existe, mas falhas de rede/HTTP não foram testadas de forma controlada.

## Princípios de engenharia

- Preservar os dados originais para rastreabilidade e reprocessamento.
- Distinguir o instante da previsão do instante da extração e preservar revisões.
- Tratar dados ausentes e erros explicitamente; nunca converter automaticamente `null` em zero.
- Projetar cargas idempotentes, com regras de unicidade ainda a definir no contrato de dados.
- Registrar origem, parâmetros, timestamps e identificador de execução.
- Manter configurações e segredos fora do repositório.
- Não apresentar resultados hipotéticos como ganhos reais.

## Preparação do ambiente

Ambiente utilizado no desenvolvimento: Windows, PowerShell e Python 3.13. Após clonar o repositório, na raiz do projeto:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Crie `.env` a partir de `.env.example`. Se `.env` já existir, revise-o sem sobrescrever configurações. Esta consulta não exige chave de API. Variáveis do terminal têm prioridade sobre `.env`.

## Execução manual

```powershell
python scripts/extract_weather.py
$LASTEXITCODE
```

`0`: execução concluída (verifique avisos de nulos). `1`: falha (verifique a mensagem no terminal). Para sair do ambiente: `deactivate`. Não é necessário recriar `venv` a cada execução.

## Arquivos gerados e fusos horários

Cada coleta é salva em `data/raw/` usando timestamp UTC e identificador da execução, sem substituir coletas anteriores. O JSON registra fonte, localidade, execução, timestamps UTC de início e fim, endpoint, parâmetros, validações e resposta original em `response`.

Os horários da previsão usam `America/Sao_Paulo`. Os timestamps da coleta usam UTC com `+00:00`. Dados ausentes permanecem `null` e são sinalizados.

## Limitações e custos

- Execução manual apenas para Campinas, com 24 passos horários.
- Uma tentativa HTTP com timeout, ainda sem retries automáticos.
- Não existe armazenamento de quarentena para respostas inválidas.
- Preservar arquivos sucessivos não equivale a idempotência de carga no PostgreSQL.
- Previsão não demonstra clima observado nem explica atrasos de entregas.
- Infraestrutura planejada para execução local com ferramentas gratuitas; agendamentos dependem da disponibilidade do computador e dos serviços.
- O uso e a atribuição dos dados seguirão as condições da Open-Meteo; GitHub Actions também está sujeito aos limites de uso.

## Arquivos fora do versionamento

O `.gitignore` exclui `venv`, `.env`, caches, logs e dados em `data/raw/`; `.env.example` é o modelo público de configuração.

## Fonte de dados

- [Open-Meteo](https://open-meteo.com/)
- [Documentação da API](https://open-meteo.com/en/docs)

## Autoria

João Pedro Caneca — https://github.com/Soba-Jopeca

Projeto autoral de aprendizado e portfólio de Engenharia de Dados, desenvolvido incrementalmente. Não redistribui código de cursos usados como referência.
