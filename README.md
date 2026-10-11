# Logistics Weather Data Pipeline

Pipeline de dados meteorológicos para apoio ao planejamento logístico.
Projeto autoral de aprendizagem e portfólio em Engenharia de Dados,
desenvolvido de forma incremental.

## Objetivo

Coletar, armazenar e organizar previsões meteorológicas para identificar
condições que mereçam atenção no planejamento de operações logísticas.

Pergunta inicial:
Que previsão de precipitação, temperatura e vento temos para Campinas
nas próximas 24 horas?

Os dados permitirão analisar exposição meteorológica. Demonstrar impacto
sobre atrasos exigiria dados operacionais e análise adicional.

## Escopo inicial

- Uma localidade: Campinas, São Paulo, Brasil.
- Fonte: API de previsão meteorológica da Open-Meteo.
- Variáveis previstas: precipitação, temperatura e velocidade do vento.
- Extração inicial em Python, executada manualmente.
- Persistência da resposta original em JSON.
- Registro dos parâmetros, instante da coleta e identificador da execução.
- Ampliação posterior para cinco localidades.

Os campos, unidades e critérios de validação serão definidos no contrato
de extração antes da implementação.

## Etapas previstas

1. Preparar o repositório e documentar o escopo.
2. Configurar o interpretador Python e o ambiente virtual.
3. Explorar a API e definir o contrato de extração.
4. Implementar e validar o primeiro extrator.
5. Carregar os dados no PostgreSQL e transformá-los com SQL.
6. Organizar a execução em containers Docker.
7. Orquestrar o pipeline com Apache Airflow.
8. Incorporar testes de código e qualidade dos dados.
9. Automatizar verificações e construção da imagem com GitHub Actions.

## Princípios de engenharia

- Preservar os dados originais para rastreabilidade e reprocessamento.
- Distinguir o instante previsto do instante em que a previsão foi coletada.
- Preservar revisões das previsões.
- Tratar falhas de comunicação e dados ausentes explicitamente.
- Projetar reexecuções sem duplicações indevidas.
- Manter configurações e segredos fora do código versionado.
- Documentar decisões e limitações.

## Execução e custos

O projeto será desenvolvido para execução local, utilizando ferramentas
gratuitas e respeitando as condições de acesso da API e os limites do
GitHub Actions.

A operação agendada local dependerá do computador e dos serviços ligados.

## Estado atual

## Estado atual

Extrator manual para Campinas implementado em Python.

Validado localmente:
- Consulta à Open-Meteo com retorno HTTP 200.
- Conferência de 24 horários consecutivos e das três séries meteorológicas.
- Validação de unidades, fuso, tipos numéricos e contagem de nulos.
- Gravação e releitura de JSON com metadados e resposta original.
- Coletas sucessivas preservadas em arquivos diferentes.
- Importação do módulo sem executar uma coleta.
- Configuração inválida interrompendo a execução com código de saída 1.

O script possui tratamento básico de erros de comunicação, mas falhas
de rede e HTTP ainda não foram testadas de forma controlada.

Banco de dados, Docker, Airflow e CI/CD permanecem como etapas futuras.

## Fonte de dados

Open-Meteo: https://open-meteo.com/

Documentação da API: https://open-meteo.com/en/docs

A utilização e a atribuição dos dados seguirão as condições da fonte.

## Preparação do ambiente

Ambiente utilizado no desenvolvimento: Windows, PowerShell e Python 3.13.

Após clonar o repositório, abra um terminal na raiz do projeto.

Em uma nova instalação, crie e ative o ambiente virtual:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

Instale as dependências registradas:

```powershell
python -m pip install -r requirements.txt
```

Crie um arquivo `.env` na raiz copiando o conteúdo de `.env.example`.
Se o `.env` já existir, revise-o sem sobrescrever configurações locais.

A consulta utilizada neste projeto não exige chave de API.
Variáveis já definidas no terminal têm prioridade sobre o arquivo `.env`.

## Execução manual

Na raiz do projeto, com o ambiente virtual ativo:

```powershell
python scripts/extract_weather.py
```

Para consultar o código de saída imediatamente após a execução:

```powershell
$LASTEXITCODE
```

- `0`: execução concluída; conferir também eventuais avisos de nulos.
- `1`: falha; consultar a mensagem apresentada no terminal.

Para encerrar o ambiente virtual:

```powershell
deactivate
```

Em outra sessão, ative novamente o ambiente existente.
Não é necessário recriá-lo nem reinstalar dependências a cada execução.

## Arquivos gerados

Cada coleta é salva em `data/raw/`, com timestamp UTC e identificador
da execução no nome, preservando coletas anteriores.

O JSON contém:
- Fonte e localidade.
- Identificador da execução.
- Instantes UTC de início do pedido e recebimento da resposta.
- Endpoint e parâmetros enviados.
- Resultado das validações.
- Resposta JSON original dentro de `response`.

Os horários da previsão usam `America/Sao_Paulo`.
Os instantes da coleta usam UTC e incluem `+00:00`.

Dados ausentes são preservados como `null` e sinalizados.
Não são substituídos por zero.

## Limitações desta versão

- Execução manual para uma localidade e 24 passos horários.
- Uma tentativa HTTP com timeout, sem retries automáticos.
- Respostas com falhas de validação não possuem armazenamento de quarentena.
- Coletas sucessivas são preservadas; isso não representa idempotência
  de carga em banco.
- As previsões não comprovam condições observadas nem causas de atrasos.

## Arquivos fora do versionamento

O `.gitignore` exclui o ambiente virtual, `.env`, caches, logs e dados
gerados em `data/raw/`.

O `.env.example` é o modelo público de configuração.

## Autoria

João Pedro Caneca — https://github.com/Soba-Jopeca

Implementação própria, desenvolvida durante estudos de Engenharia de Dados.
Este repositório não redistribui o código do curso utilizado como referência.