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

Repositório criado e clonado localmente.
Projeto em fase de preparação; extração ainda não implementada.

## Fonte de dados

Open-Meteo: https://open-meteo.com/

Documentação da API: https://open-meteo.com/en/docs

A utilização e a atribuição dos dados seguirão as condições da fonte.

## Autoria

João Pedro Caneca — https://github.com/Soba-Jopeca

Implementação própria, desenvolvida durante estudos de Engenharia de Dados.
Este repositório não redistribui o código do curso utilizado como referência.