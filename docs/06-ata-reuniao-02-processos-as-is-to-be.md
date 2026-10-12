# ATA-R2-001 — Reunião 2 | Mapeamento AS-IS / TO-BE

**Projeto:** PHD-AL-2026-001 — Logistics Weather Data Pipeline  
**Consultoria:** Phoenix Data (fictícia)  
**Cliente:** AuroraLog Transportes & Distribuição S.A. (fictício)  
**Condução:** Mr. João Caneca  
**Participantes no roteiro simulado:** Rafael Mendes, Camila Rocha, Bruno Tavares e João Caneca  
**Data prevista no cenário:** 15/10/2026 (não representa reunião realizada)  
**Consolidação documental:** 12/10/2026  
**Status:** **R2 aprovada e encerrada no cenário simulado**; diagramas validados pelo responsável pelo projeto. Não constitui aceite real de terceiros.

> Os diálogos, papéis e indicadores operacionais são fictícios. Esta ata não constitui assinatura, aceite contratual ou evidência de reunião real.

## 1. Objetivo e pré-condições
Mapear o fluxo atual de utilização de informações meteorológicas, identificar gargalos, validar o TO-BE operacional e a arquitetura de referência, priorizar perguntas de negócio e estabelecer o consumo mínimo do MVP. O Kickoff (ATA-KO-001) já foi encerrado no cenário simulado.

## 2. Evidências e artefatos
- `diagrams/reuniao-02-as-is.excalidraw` — AS-IS, arquivo editável local, aprovado pelo responsável na revisão visual.
- `diagrams/reuniao-02-to-be.excalidraw` — TO-BE, arquivo editável local, carregamento confirmado pelo responsável após reparação dos índices Excalidraw e revisão dos nove critérios visuais/técnicos.
- A presença exata dos arquivos, seus hashes e a exportação em imagem deverão ser conferidos localmente antes do PR #2. Os desenhos não estão incluídos neste pacote documental.

## 3. Processo AS-IS — fluxo reconhecido no exercício
1. Fontes meteorológicas externas diversas são consultadas em momentos distintos.
2. Profissionais da equipe de planejamento realizam consultas manuais.
3. Ocorre interpretação individual das previsões.
4. As anotações são consolidadas manualmente.
5. A informação é comunicada à Coordenação de Planejamento e Transportes.
6. O planejamento do dia seguinte, por volta das 15h (America/Sao_Paulo), utiliza essa informação como apoio à decisão humana.

**Gargalos:** fontes/horários divergentes; falta de padronização; ausência de histórico estruturado; baixa rastreabilidade; dificuldade para comparar localidades; esforço de consolidação manual.

**Premissa não medida:** em dias instáveis, 20–30 minutos de *tempo decorrido por ciclo* de consolidação; não equivale a 20–30 minutos por profissional. A equipe fictícia possui oito integrantes; quatro fazem consultas regularmente.

## 4. Processo TO-BE — fluxo de negócio
1. Previsões das cinco localidades são extraídas e validadas.
2. A solução preserva a origem e diferentes versões das previsões.
3. A publicação estruturada informa localidade, horário previsto, métrica, instante da coleta e situação de qualidade/frescor.
4. O planejamento consulta a visão geral das localidades e o detalhamento horário.
5. Condições meteorológicas relevantes levam a uma *verificação humana*, não a mudanças automáticas de rotas.
6. Uma versão da previsão usada deve ser rastreável posteriormente.

**Arquitetura técnica de referência:** Open-Meteo API → Python/extrator e validação → Raw JSON → PostgreSQL → SQL/ELT → consultas analíticas → Planejamento/Transportes. Docker (ambiente), Airflow (orquestração), pytest e avaliação de Soda (qualidade/testes), GitHub Actions (CI/CD) são componentes transversais. Apenas extrator Python manual para Campinas e Raw JSON possuem evidência técnica anterior; demais itens são planejados.

## 5. Perguntas analíticas priorizadas — proposta para aceite R2
| ID | Prioridade proposta | Pergunta | Resultado mínimo |
|---|---|---|---|
| PB-01 | P1 | Qual a previsão horária por localidade nas próximas 24 horas? | Tabela por localidade, horário, chuva, vento e temperatura |
| PB-02 | P1 | Quando ocorrerão valores meteorológicos elevados para análise preventiva? | Consulta ordenável e filtros; limiares ainda não aprovados |
| PB-03 | P1 | Qual é a versão e a hora de coleta da informação exibida? | `run_id`, `collected_at`, estado de qualidade/frescor |
| PB-04 | P1 | A coleta esperada está completa e disponível antes das 15h? | Indicador de completude e última extração válida |
| PB-05 | P2 | Como mudou a previsão para um mesmo horário entre coletas? | Consulta comparativa histórica, sujeita à priorização na R4 |

**Consumo mínimo proposto:** consultas SQL e relatório/tabela consolidada reproduzível por localidade e horário; dashboard interativo não é condição de aceite do MVP.

## 6. Decisões aprovadas na simulação
| ID | Decisão | Responsável fictício |
|---|---|---|
| DEC-007 | Aprovar os fluxos AS-IS e TO-BE como baseline processual da R2 | Rafael / Camila |
| DEC-008 | Priorizar PB-01 a PB-04 e manter PB-05 como prioridade secundária | Camila |
| DEC-009 | Aceitar consulta/tabela reproduzível como consumo mínimo, sem dashboard obrigatório | Camila / Rafael |
| DEC-010 | Manter avaliação e eventuais ajustes de transportes sob decisão humana | Rafael |
| DEC-011 | Medir o baseline sem confundir tempo decorrido e horas-pessoa | Camila / Bruno |

## 7. Plano de medição do baseline (aprovado na simulação; execução futura)
- **Unidade:** um ciclo de consolidação meteorológica para o planejamento do dia seguinte.
- **Amostra proposta:** registrar pelo menos dez ciclos, distinguindo dias instáveis e demais dias, quando ocorrerem.
- **Campos:** data; localidade(s); início/fim da consulta; tempo decorrido; número de participantes; tempo dedicado por participante; quantidade de fontes; ocorrências de divergência; responsável pelo registro.
- **Indicadores:** mediana e amplitude do tempo decorrido; soma de horas-pessoa; quantidade de fontes e divergências.
- **Responsáveis:** Bruno registra; Camila valida a metodologia e os resultados.
- **Atenção:** a amostra acima é um plano sugerido, não medição já realizada.

## 8. Pendências pertencentes às etapas posteriores
| Tema | Reunião prevista | Responsável |
|---|---|---|
| Frequência exata, frescor, timestamps, identificadores e coordenadas | R3 | João / Beatriz / Camila |
| Regras formais de qualidade e comportamento de falhas | R3 | João / Beatriz |
| Limiares para atenção meteorológica | R3/R4 | Camila / Rafael |
| MoSCoW, critérios de aceite finais e política de publicação | R4 | Camila / Helena |
| Aceite consolidado do escopo e apresentação final | R5 | Helena |

Estas não impedem o fechamento da R2 quando suas próprias decisões forem ratificadas.

## 9. Gate R2 — verificação de encerramento
- [x] AS-IS documentado e diagrama visualmente validado pelo responsável.
- [x] Gargalos registrados e premissa temporal qualificada.
- [x] TO-BE documentado e diagrama tecnicamente/visualmente validado pelo responsável.
- [x] PB-01 a PB-05 e formato mínimo de consumo ratificados na simulação.
- [x] Plano de medição do baseline ratificado na simulação.
- [x] DEC-007 a DEC-011 registrados como aprovados na simulação.
- [ ] Verificar localmente presença e nomes exatos dos diagramas e preparar PR #2 (controle de integração documental, não pendência de definição de negócio).

**Parecer:** **GATE-R2 = APROVADO NA SIMULAÇÃO** por confirmação expressa do responsável em 12/10/2026. AS-IS, TO-BE, PB-01 a PB-05, DEC-007 a DEC-011, consumo mínimo e metodologia de baseline são baseline de negócio da R2. O push, o PR e a publicação na `main` são controles de integração ainda pendentes; a reunião 3 só será iniciada após integração conforme regra do projeto.

**Registro de aprovação do exercício:** aprovação dada pelo responsável pelo projeto no chat em 12/10/2026; as manifestações atribuídas a representantes da AuroraLog são simulações, sem assinatura, participação ou consentimento real.