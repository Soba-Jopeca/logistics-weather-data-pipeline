# Reunião 2 — Abertura e pauta | Processos AS-IS e TO-BE

**Referência:** PHD-AL-2026-001 | **Tipo:** simulação não realizada
**Data prevista no cenário:** 15/10/2026 | **Duração:** 75 min
**Consultor:** Mr. João Caneca (Phoenix Data)
**Participantes previstos:** Rafael Mendes, Camila Rocha, Bruno Tavares e João Caneca.

## 1. Pré-condição atendida

Reunião 1 formalmente aprovada **somente na simulação** conforme `04-ata-reuniao-01-kickoff-aprovada-simulacao.md`. A aprovação cobre o problema, cinco localidades, definição da hipótese 20–30 min/ciclo, disponibilidade antes das 15h e fronteiras de uso.

## 2. Objetivo desta reunião

Representar como uma informação meteorológica percorre hoje o processo de planejamento (AS-IS), identificar pontos de decisão, desenhar o fluxo de uso desejado (TO-BE **de negócio**) e obter requisitos verificáveis de consulta. Não rediscutir seleção de tecnologia.

## 3. Abertura sugerida — João Caneca

> Bom dia, Rafael, Camila e Bruno. Encerramos o Kickoff com um entendimento comum do problema e do alcance inicial. Hoje quero acompanhar o processo de ponta a ponta: quem recebe a demanda de planejamento, quem consulta o clima, que dados são comparados, como uma condição de atenção é comunicada e qual registro fica para auditoria. Depois desenharemos o processo desejado a partir das decisões reais de vocês. A arquitetura técnica de referência permanece Open-Meteo, Python, PostgreSQL/SQL, Docker, Airflow e GitHub Actions, com testes e qualidade; nosso foco hoje é garantir que ela produza a informação certa, no momento certo, para a pessoa certa.

## 4. Agenda (75 minutos)

| Intervalo | Tema | Evidência de saída |
|---|---|---|
| 0–10 min | Recapitular gate R1 e delimitar processo | Fronteiras do processo |
| 10–30 min | Caminhar pelo AS-IS com um caso concreto | Fluxo, papéis, gatilhos, fontes e tempos |
| 30–45 min | Dores, retrabalhos, divergências de previsão e decisão | Inventário de problemas com impacto/hypóteses |
| 45–60 min | Desenhar TO-BE operacional e formas de consumo | Fluxo futuro e perguntas priorizadas |
| 60–70 min | Definir critérios de valor e medição | Métricas + donos de medição |
| 70–75 min | Ler de volta decisões e registrar aceite | Ata R2 ou pendências atribuídas |

## 5. Perguntas que João deve conduzir

1. Descrevam um dia recente de instabilidade desde a entrada do pedido até a decisão no planejamento.
2. Quem consulta o quê, a que horas, para quais localidades, e para quem envia o resultado?
3. O que acontece quando duas fontes dão previsões diferentes? Quem arbitra e documenta?
4. O que cada pessoa precisa visualizar: ranking de localidades, série horária, valores, carimbo de atualização ou histórico de versões?
5. Que ação humana é desencadeada por um alerta e quais informações adicionais são exigidas?
6. Como registraremos **tempo decorrido**, **horas-pessoa** e quantidade de consultas, sem misturá-los?
7. Qual evidência demonstraria que a consulta preparada é útil antes das 15h?

## 6. TO-BE — restrição já estabelecida

**Fluxo de negócio desejado:** chegada das previsões estruturadas → verificação da qualidade e do frescor → comparação por localidade e hora → sinalização de condições a avaliar → análise e decisão humana → registro do contexto e da versão consultada.

**Implementação técnica de referência (planejada):** Open-Meteo → Python / JSON bruto → PostgreSQL + SQL / ELT → consultas/saídas analíticas; Docker (ambiente), Airflow (agenda/orquestração), GitHub Actions (CI/CD), pytest (testes), Soda (avaliação). Arquitetura não implica que todos os componentes já estejam implantados.

## 7. Critérios de encerramento da Reunião 2

- [ ] AS-IS com início, fim, participantes, sistemas, entradas, saídas e handoffs descritos.
- [ ] Principais gargalos e situações de divergência registrados.
- [ ] TO-BE de negócio com ação humana e trilha de consulta descritos.
- [ ] Perguntas analíticas priorizadas e formato mínimo de consumo decidido.
- [ ] Plano de medição do baseline (tempo decorrido versus esforço total) acordado.
- [ ] Ata R2 com decisões, responsáveis e questões encaminhadas, sem lacunas da pauta.

**Status:** pronta para abertura, ainda não realizada na simulação.
