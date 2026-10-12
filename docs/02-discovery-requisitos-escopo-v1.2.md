# Phoenix Data | Discovery, Requisitos e Escopo — v1.2

**Projeto:** Logistics Weather Data Pipeline  
**Consultoria executora:** Phoenix Data (organização fictícia)  
**Consultor responsável:** Mr. João Caneca — Consultor de Dados / Engenharia de Dados  
**Cliente requisitante:** **AuroraLog Transportes & Distribuição S.A.** (empresa fictícia)  
**Referência:** PHD-AL-2026-001  
**Versão / data:** 1.2 / 12 de outubro de 2026  
**Status:** **Reuniões 1 e 2 aprovadas e encerradas na simulação; integração GitHub da R2 pendente; reuniões 3–5 e escopo final ainda não aprovados**  
**Classificação:** Estudo de caso para portfólio; pessoas, reuniões, falas, métricas de exemplo e operações são simuladas.

> **Aviso de integridade:** as reuniões abaixo são **roteiros/atas simulados**, e não encontros que ocorreram. Nomes, cargos e falas foram criados para tornar o processo de levantamento de requisitos reproduzível. Declarações de stakeholders não são fatos verificados. A implementação real do pipeline tem progresso próprio e deve ser acompanhada por evidências no repositório.

## 1. Carta de abertura e contexto do cliente

A AuroraLog atua, neste cenário fictício, com transferências entre centros de distribuição e entregas regionais. O planejamento diário de transportes precisa acompanhar fatores externos que possam demandar atenção especial. Hoje, as informações meteorológicas são consultadas em serviços variados e não ficam registradas de forma comparável e auditável.

**Solicitação do cliente (simulada):** “Precisamos enxergar, num mesmo lugar, as previsões meteorológicas das regiões de operação para as próximas 24 horas, saber quando foram consultadas e identificar janelas de atenção — sem prometer previsão de atrasos.”

**Mandato da Phoenix Data:** conduzir descoberta de requisitos e desenvolver um MVP local, reproduzível e de custo de infraestrutura zero para ingestão e consumo analítico de previsões meteorológicas horárias.

### 1.1 Papéis e partes interessadas

| Papel | Representante fictício | Interesse / autoridade |
|---|---|---|
| Patrocinadora / Diretoria de Operações | Helena Duarte | Aprovação de objetivo, escopo e aceite de negócio |
| Gerência de Transportes | Rafael Mendes | Decisões de planejamento; valida utilidade operacional |
| Coordenação de Planejamento | Camila Rocha | Define perguntas, horários e critérios de consulta |
| Analista de Operações | Bruno Tavares | Usuário de consulta e validação de cenários |
| TI e Segurança | Beatriz Nascimento | Restrições de operação, segurança e dependências |
| Product Owner do cliente | Camila Rocha (designada para o cenário) | Prioriza backlog e aceita entregas por delegação |
| Consultoria / Discovery e execução | Mr. João Caneca, Phoenix Data | Facilitação, documentação, proposta técnica e implementação |

### 1.2 Limites de autoridade

A Phoenix Data **propõe** arquitetura e critérios de dados; o cliente **aprova** regras de negócio, localidades, prioridades e critérios de aceite. O consultor não define sozinho o significado de “risco operacional”.

---

## 2. Ciclo de discovery — cinco reuniões simuladas

### Reunião 1 — Kickoff e entendimento do problema (ENCERRADA NA SIMULAÇÃO)

**Data do encontro (simulada):** 13/10/2026 | **Duração planejada:** 60 min  
**Data do registro de aprovação do exercício:** 12/10/2026. A aprovação antecipada é decisão do usuário sobre o cenário, não comprovação de reunião futura.  
**Participantes simulados:** Helena Duarte (patrocinadora), Rafael Mendes (Transportes), Camila Rocha (Planejamento/PO) e João Caneca (Phoenix Data).  
**Ata formal:** [`04-ata-reuniao-01-kickoff-aprovada-simulacao.md`](04-ata-reuniao-01-kickoff-aprovada-simulacao.md).

**Problema validado no exercício:** consultas meteorológicas descentralizadas, sem histórico padronizado ou rastreabilidade da informação disponível no instante do planejamento. **Objetivo:** informações meteorológicas horárias, comparáveis e auditáveis para apoiar o planejamento preventivo sem automatizar alterações de viagens.

**Declarações operacionais simuladas:** oito integrantes no planejamento, quatro consultando meteorologia regularmente; preparação para o dia seguinte iniciada aproximadamente às 15h; consolidação em dias instáveis consumindo 20–30 minutos **de tempo decorrido por ciclo**, não por pessoa. Trata-se de hipótese a medir no piloto, não de ganho ou baseline comprovado.

**Decisões aprovadas no contexto da simulação:**

| ID | Definição | Tipo |
|---|---|---|
| DEC-001 | Centralizar, padronizar e registrar previsões para apoio à decisão | Necessidade de negócio |
| DEC-002 | Cinco localidades piloto: Campinas, São Paulo, Sorocaba, Jundiaí e Ribeirão Preto (SP) | Escopo geográfico fictício |
| DEC-003 | 20–30 minutos = tempo decorrido por consolidação em dias instáveis; esforço-pessoa não medido | Premissa / baseline a validar |
| DEC-004 | Dados atualizados disponíveis antes do ciclo de planejamento das 15h (America/Sao_Paulo); frequência e antecedência a especificar | Requisito temporal de negócio |
| DEC-005 | Condições meteorológicas orientam avaliação humana; não acionam automaticamente rota, cancelamento ou SLA | Fronteira de escopo |
| DEC-006 | Manter arquitetura de referência já definida, com verificação técnica nas próximas reuniões | Restrição de solução / referência técnica |

**Autorização registrada:** Helena, como patrocinadora *fictícia*, autoriza no exercício a continuidade do discovery, sem aceitar antecipadamente o escopo final ou os resultados do MVP. **Gate da Reunião 1: aprovado na simulação.** Não restam decisões do Kickoff sem encaminhamento; questões de processo, dados e aceite pertencem às reuniões 2–5.

### Reunião 2 — Mapeamento de processo e necessidades de informação

**Data simulada:** 15/10/2026 | **Duração prevista:** 75 min  
**Participantes:** Rafael, Camila, Bruno e João.  
**Objetivo:** entender o fluxo AS-IS e TO-BE e levantar perguntas de negócio.

**Entrevista simulada**

- **João:** “Descrevam, do início ao fim, como analisam as condições para o próximo dia.”
- **Bruno:** “O analista abre sites meteorológicos, anota os pontos críticos e avisa ao planejador.”
- **João:** “Como distinguem previsão de chuva forte de atraso efetivamente causado por chuva?”
- **Camila:** “Não distinguimos por dados. Precisamos que o painel descreva o clima previsto, não um atraso previsto.”
- **João:** “O usuário precisa ver a localidade isolada ou comparar todas?”
- **Rafael:** “Ambos: comparação geral e detalhamento horário.”
- **João:** “Uma tabela ou consulta reproduzível satisfaz o MVP, antes de um dashboard?”
- **Camila:** “Sim, desde que possamos responder às perguntas sem abrir a API manualmente.”

**AS-IS simulado:** fontes dispersas → leitura manual → anotações não padronizadas → comunicação sem histórico confiável.  
**TO-BE proposto:** execução de coleta → validação → persistência com versões → consulta consolidada → priorização humana das verificações.

**Perguntas de negócio aprováveis:** (P1) quais localidades terão maior precipitação horária? (P2) quais horas estão acima dos limites? (P3) qual versão de previsão estava disponível numa coleta anterior? (P4) a coleta está completa e atualizada?

**Decisão proposta:** camada de consultas/relatório simples no MVP; dashboard interativo não é pré-requisito.

**A validar na Reunião 2:** priorização das perguntas e formato de consumo preferido; o roteiro acima ainda não constitui ata executada.

### Reunião 3 — Requisitos de dados, qualidade e governança

**Data simulada:** 19/10/2026 | **Duração prevista:** 90 min  
**Participantes:** Camila, Beatriz, Bruno e João.  
**Objetivo:** decidir granularidade, tratamento temporal, histórico e confiabilidade.

**Entrevista simulada**

- **João:** “Se consultarmos às 06h e novamente às 10h, precisamos manter as duas previsões para as 15h?”
- **Camila:** “Sim. Isso permite entender que informação estava disponível em cada momento.”
- **João:** “Como reconhecer registros repetidos?”
- **Beatriz:** “Precisamos de identificador de execução e regra de unicidade. Reexecutar o mesmo lote não pode multiplicar linhas.”
- **João:** “Qual fuso será adotado?”
- **Beatriz:** “Armazenamento normalizado em UTC e apresentação no fuso local, com documentação.”
- **João:** “Uma hora sem dados pode ser preenchida com zero?”
- **Bruno:** “Não. Zero de precipitação é diferente de valor ausente.”
- **João:** “O que ocorre se uma das localidades falhar?”
- **Camila:** “A falha deve aparecer explicitamente, e não como ausência de evento meteorológico.”

**Decisões propostas:** grão = (localidade, horário previsto UTC, execução); manter cada execução coletada; rejeitar duplicidade indevida; não converter campos ausentes para zero; registrar fonte, momento de extração, contagens, erro e status; UTC na persistência.

**Questões abertas:** identificador estável de localidade; política de retenção (proposta: manter integralmente no MVP e revisar conforme tamanho); limiares para atenção; comportamento de publicação parcial.

**Saída:** contrato de dados preliminar e matriz de qualidade.

### Reunião 4 — Priorização do MVP e critérios de aceite

**Data simulada:** 21/10/2026 | **Duração prevista:** 75 min  
**Participantes:** Helena, Rafael, Camila, Beatriz e João.  
**Objetivo:** negociar escopo, riscos, prioridades e aceite.

**Entrevista simulada**

- **João:** “Entre dashboard visual e preservação histórica, o que é indispensável agora?”
- **Helena:** “Histórico confiável. A apresentação visual pode evoluir depois.”
- **João:** “Podemos iniciar com cinco localidades e 24 horas em vez de cobertura nacional?”
- **Rafael:** “Sim, para validar o uso antes de ampliar.”
- **João:** “Limiares de atenção são recomendação técnica ou política operacional?”
- **Camila:** “Devem ser discutidos conosco. Para teste, usem parâmetros demonstrativos claramente identificados.”
- **Beatriz:** “Também precisamos evitar credenciais no Git e custos de nuvem.”
- **João:** “O MVP não integrará dados de atrasos. Podemos excluir qualquer promessa de redução de SLA?”
- **Helena:** “Sim.”

**Priorização MoSCoW proposta**

- **Must:** cinco localidades; 24 horas; identificação de execução; histórico; idempotência; DQ; logs; consultas analíticas; execução local; documentação e testes.
- **Should:** comparativo entre versões e parametrização de limiares.
- **Could:** relatório visual estático e notificações em ambiente de demonstração.
- **Won't (MVP):** dados TMS/GPS, predição de atraso, roteirização, dashboard corporativo, cloud paga e SLA produtivo.

**Ponto de atenção:** não há comprovação de validade de um limiar climático para inferir risco. Usar a expressão **“condição de atenção meteorológica”**.

### Reunião 5 — Playback, validação e aprovação condicional

**Data simulada:** 23/10/2026 | **Duração prevista:** 60 min  
**Participantes:** Helena, Rafael, Camila, Beatriz e João.  
**Objetivo:** apresentar requisitos consolidados, critérios de aceitação, dependências e próximos marcos.

**Roteiro de playback e falas simuladas**

- **João:** “A entrega resolverá visibilidade e rastreabilidade de previsões. Não calculará impacto real sobre entregas.”
- **Helena:** “Essa delimitação está alinhada ao objetivo.”
- **João:** “Uma consulta deverá identificar localidade, horário previsto, métrica, instante de coleta e qualidade do dado.”
- **Camila:** “Esses elementos são fundamentais para o aceite.”
- **João:** “Ainda faltam a confirmação das localidades e a política final de limiares. Vamos tratá-las como pendências de negócio.”
- **Beatriz:** “Concordo com aprovação condicionada a essas definições e aos testes de falha.”

**Resultado da simulação:** recomendação de **aprovação condicional** do MVP, dependente da resolução de itens abertos. **Nenhuma aprovação real foi obtida.**

**Registros propostos:** ata de playback; backlog final; aceite formal a preencher; baseline a levantar no piloto.

---

## 3. Declaração consolidada do problema

**Problema de negócio:** o planejamento da AuroraLog carece de visão comparável, antecipada e rastreável das condições meteorológicas nas localidades de interesse, levando a consultas dispersas e pouco auditáveis.

**Problema de dados:** inexistência, no cenário, de pipeline sistemático que colete previsões horárias, preserve versões, garanta qualidade e disponibilize produtos analíticos.

**Pergunta norteadora:** “Como disponibilizar, com rastreabilidade e qualidade, previsões meteorológicas horárias para apoiar o planejamento preventivo nas localidades logísticas monitoradas?”

## 4. Objetivo, resultados e critérios de valor

**Objetivo geral:** entregar produto de dados meteorológicos reproduzível e auditável para apoiar avaliações humanas de atenção operacional.

**Resultados previstos:** base histórica de coletas; visão de 24h para cinco localidades; indicadores e consultas; testes, logs e processo de execução; documentação das limitações.

**Benefícios a investigar:** menor tempo para consolidar consultas, maior transparência das previsões utilizadas, melhor priorização das verificações operacionais. **Sem metas de economia ou ganhos de SLA neste ciclo.**

## 5. Escopo acordável do MVP

### 5.1 Incluído

1. Configurar **cinco localidades** identificadas por ID estável, nome e coordenadas aprovadas.
2. Extrair previsão **horária de 24 passos consecutivos** com definição inequívoca de início/fim da janela.
3. Validar contrato, unidades, valores nulos, cardinalidade temporal e dados obrigatórios.
4. Persistir dados das previsões junto com ID, data e status da execução, mantendo histórico entre coletas.
5. Garantir idempotência ao reprocessar a **mesma execução**; uma nova coleta constitui nova versão.
6. Produzir consultas por localidade/hora e indicadores de precipitação, vento, temperatura e duração de condições de atenção.
7. Registrar erros e métricas de processamento; cobrir cenários de falha com testes.
8. Executar localmente, sem infraestrutura paga; documentar execução e CI/CD básico.

### 5.2 Excluído

TMS, ERP, GPS, pedidos e entregas; cálculo de SLA e atrasos; correlação causal e previsão de impacto; recomendação automática de cancelamento ou mudança de rota; interface enterprise; contrato 24/7; provedores pagos.

### 5.3 Evolução futura condicionada

Integração com dados de viagens e entregas, observações meteorológicas para avaliar acurácia, dashboard operacional, alertas e estudos quantitativos de impacto.

## 6. Requisitos funcionais — baseline para aprovação

| ID | Requisito | Prioridade | Origem (reunião) | Evidência de aceite |
|---|---|---|---|---|
| RF-01 | Configurar e consultar cinco localidades | Must | R1/R4 | Cinco IDs e coordenadas válidos |
| RF-02 | Coletar 24 previsões horárias distintas por localidade | Must | R2/R3 | 24 períodos válidos consecutivos em uma execução bem-sucedida |
| RF-03 | Validar estrutura, obrigatoriedade e unidades | Must | R3 | Testes de payload ausente/inválido |
| RF-04 | Registrar ID, instante, origem e resultado de cada execução | Must | R3 | Auditoria de uma coleta reproduzível |
| RF-05 | Preservar diferentes versões de previsão entre coletas | Must | R3/R4 | Mesmo horário previsto possui versões associadas a execuções distintas |
| RF-06 | Reprocessar um mesmo lote sem duplicação | Must | R3/R4 | Contagem estável após replay |
| RF-07 | Consultar dados por localidade e hora prevista | Must | R2/R4 | Consulta funcional de demonstração |
| RF-08 | Calcular métricas e períodos de atenção mediante limiares explícitos | Must | R2/R4 | Consulta de cenário demonstrativo, sem inferir risco de atraso |
| RF-09 | Comparar previsões para um mesmo horário feitas em coletas distintas | Should | R3/R4 | Consulta de diferenças entre duas versões |
| RF-10 | Registrar falhas por localidade sem ocultá-las | Must | R3/R4 | Teste de indisponibilidade ou payload inválido |

## 7. Requisitos não funcionais

| ID | Dimensão | Exigência / teste esperado |
|---|---|---|
| RNF-01 | Confiabilidade | Falha HTTP, timeout ou JSON inválido tratados sem saída enganosa |
| RNF-02 | Qualidade | Completude de 24h, unicidade, tipagem, unidades e consistência temporal |
| RNF-03 | Temporalidade | UTC em timestamps persistidos; fuso de exibição explícito |
| RNF-04 | Auditabilidade | Fonte, data/hora da coleta, ID de execução e status recuperáveis |
| RNF-05 | Segurança | Segredos e arquivos locais privados fora do Git; dependências rastreadas |
| RNF-06 | Custo | MVP executável sem serviços de infraestrutura pagos |
| RNF-07 | Manutenibilidade | Código modular, configuração e documentação versionados |
| RNF-08 | Testabilidade | Testes automatizados e pipeline de CI mínimo |
| RNF-09 | Portabilidade | Setup local documentado, idealmente preparado para containerização posterior |

## 8. Contrato de dados conceitual (a detalhar no Data Contract)

**Entidade `forecast_snapshot`:** uma linha = uma previsão para `(location_id, forecast_time_utc, run_id)`.  
**Entidade `pipeline_run`:** metadados de cada execução (início, fim, status, fonte, contagens e falhas).  
**Entidade `location`:** catálogo versionado/administrado de localidades e coordenadas.

**Atributos candidatos:** `location_id`, `latitude`, `longitude`, `forecast_time_utc`, `collected_at_utc`, `run_id`, `precipitation_mm`, `wind_speed_kmh`, `temperature_c`, `source`, `quality_status`. Nomes definitivos serão alinhados ao payload e ao esquema real.

**Regra essencial:** `precipitation_mm = 0` (ausência prevista de precipitação) **não equivale** a dado ausente. **Previsão** não deve ser apresentada como medição observada.

## 9. Regras de negócio (propostas)

| ID | Regra | Situação |
|---|---|---|
| RN-01 | O horizonte é de 24 períodos horários consecutivos por localidade | Proposta para aprovação |
| RN-02 | Cada execução nova cria um snapshot rastreável | Proposta para aprovação |
| RN-03 | Uma mesma execução pode ser reprocessada sem acrescentar duplicatas | Proposta para aprovação |
| RN-04 | Horas acima de limites configurados são classificadas como “atenção meteorológica” | Limiares ainda pendentes |
| RN-05 | Um campo ausente não pode ser interpretado como zero meteorológico | Proposta para aprovação |
| RN-06 | Publicações analíticas precisam expor horário da última coleta válida e sua condição de qualidade | Proposta para aprovação |
| RN-07 | Decisões sobre rotas e transporte continuam com a operação | Proposta para aprovação |

## 10. Critérios de aceitação ponta a ponta

| ID | Cenário Gherkin resumido | Evidência requerida |
|---|---|---|
| CA-01 | Dadas cinco localidades válidas, quando a extração concluir com sucesso, então cada uma terá 24 períodos horários distintos | Contagem e horários por localidade |
| CA-02 | Dado o replay de um `run_id`, quando republicado, então não são inseridas duplicatas | Contagem antes/depois e teste |
| CA-03 | Dadas duas coletas distintas para a mesma hora-alvo, então as duas versões permanecem consultáveis | Consulta histórica |
| CA-04 | Dado um payload inconsistente, quando validado, então a ocorrência será registrada e não mascarada | Log e resultado de teste |
| CA-05 | Dado um limiar explicitamente configurado, então as horas de atenção são calculadas sem rotular impacto logístico real | Consulta e documentação de limiar |
| CA-06 | Dada uma execução, é possível identificar fonte, timestamp de coleta, status e total de registros | Evidência de auditoria |
| CA-07 | Dado um clone limpo do repositório, a pessoa executa testes e o fluxo local seguindo o README | Checklist de reprodução |
| CA-08 | Dado o workflow de CI, testes definidos passam em branch/PR sem dependência de cloud paga | Log de CI |

## 11. Matriz de rastreabilidade — problema → requisito → aceite

| Necessidade | Stakeholder | Requisitos | Aceite |
|---|---|---|---|
| Visão consolidada | Camila/Rafael | RF-01/02/07 | CA-01/07 |
| Histórico de consultas | Camila/Beatriz | RF-04/05/06 | CA-02/03/06 |
| Dados confiáveis | Bruno/Beatriz | RF-03/10 | CA-01/04 |
| Períodos de atenção | Rafael/Camila | RF-08/09 | CA-05 |
| Operação viável e econômica | Helena/Beatriz | RNF-05/06/08 | CA-07/08 |

## 12. Premissas, dependências e riscos

| Tipo | Item | Resposta prevista |
|---|---|---|
| Premissa | Open-Meteo disponibiliza dados necessários para as coordenadas escolhidas | Verificar contrato da API e testes reais |
| Premissa | MVP cobre cinco localidades sem necessidade de infraestrutura paga | Executar prova e inventário de custos |
| Dependência | Confirmação das cinco localidades e coordenadas | Aprovação por PO antes do aceite |
| Dependência | Limiares de atenção e responsáveis pela validação | Reunião curta de decisão com Planejamento |
| Risco | Mudanças de schema, limites de API, indisponibilidade | Validação, timeouts, retries controlados, logs |
| Risco | Erros de fuso/hora previstos | UTC, testes e contrato formal |
| Risco | Confusão entre alerta de clima e previsão de atraso | Linguagem prudente, legenda e escopo explícitos |
| Risco | Crescimento de arquivos históricos | Medir volume e aprovar retenção |
| Risco | Incompatibilidade entre proposta e código existente | Gap analysis e tarefas pequenas de adaptação |

## 13. Roadmap por entregáveis (sem prazos inventados)

| Marco | Entregável | Gate de aprovação |
|---|---|---|
| M0 — Discovery | Business Case + este documento + questões abertas | Validação formal dos stakeholders simulados |
| M1 — Data Contract | Schema, chaves, temporalidade, DQ e limites | Revisão técnica e de negócio |
| M2 — Ingestão | Extrator testado para localidades configuradas | CA-01/04 |
| M3 — Histórico e idempotência | Dados persistidos e replay | CA-02/03/06 |
| M4 — Analytics | Consultas e indicadores | CA-05 |
| M5 — Operação e entrega | Logs, testes, CI e documentação final | CA-07/08 |

**Situação de implementação conhecida (não simulada):** já houve execução local e validações iniciais do extrator no projeto. O estado de cada marco deve ser marcado com evidências, não inferido a partir destas atas ficcionais.

## 14. Registro de decisões (ADR de negócio)

| Decisão | Fundamentação | Estado |
|---|---|---|
| D-01 — Focar em previsões, não em atrasos | Não há integração de dados logísticos | Aprovada no Kickoff simulado |
| D-02 — 24 horas / cinco localidades | MVP controlável; localidades nomeadas no Kickoff | Aprovada no Kickoff simulado |
| D-03 — Histórico por execução | Permite rastreabilidade e comparação | Proposta |
| D-04 — UTC na persistência | Evita ambiguidades temporais | Proposta |
| D-05 — Custo de infraestrutura zero | Restrição inicial do projeto | Proposta |
| D-06 — Consultas primeiro, dashboard depois | Prioriza valor informacional e qualidade | Proposta |

## 15. Questões em aberto e responsáveis

| ID | Questão | Responsável pelo esclarecimento | Impacto | Estado |
|---|---|---|---|---|
| Q-01 | Localidades definidas no Kickoff; coordenadas e identificadores ainda precisam ser validados tecnicamente | Camila/João | Configuração e testes | Parcial — Reunião 3 |
| Q-02 | Qual horário e frequência de coleta devem ser adotados no piloto? | Camila | Agendamento/atualidade | Aberta |
| Q-03 | Quais métricas e limiares de atenção fazem sentido para a operação? | Rafael/Camila | Indicadores | Aberta |
| Q-04 | Quais usuários e formato de entrega (SQL, CSV, relatório)? | Camila/Bruno | Consumo | Aberta |
| Q-05 | Baseline conceitual de 20–30 min/ciclo fixado; metodologia de medição do esforço total | Bruno/Camila | Evidência de valor | Encaminhada — Reunião 2 |
| Q-06 | Qual política de retenção e publicação em erro parcial? | Beatriz/Camila | Persistência e qualidade | Aberta |
| Q-07 | Qual dataset e esquema efetivos já existem no repositório? | João | Gap analysis técnica | Aberta |

## 16. Governança, mudança de escopo e aceite

1. **Fonte única de definição:** este documento concentra o escopo aprovado/proposto; detalhes físicos pertencem ao futuro `03-data-contract-v1.0.md`.
2. **Controle de mudanças:** cada alteração relevante registra pedido, motivo, impacto em custo/tempo/qualidade, decisão e nova versão.
3. **Aceite por etapa:** João apresenta evidências; Camila verifica funcionalmente; Beatriz verifica critérios técnicos aplicáveis; Helena formaliza aprovação final do MVP.
4. **Status honesto:** na simulação, nenhuma assinatura/ata representa concordância real de pessoa ou empresa.


### 16.1 Arquitetura técnica de referência herdada do planejamento anterior

**Este registro não reinicia a seleção das ferramentas:** Open-Meteo (fonte) → Python / preservação de JSON bruto → PostgreSQL / SQL (persistência e transformações) → consultas analíticas; Docker (ambiente), Apache Airflow (orquestração), GitHub Actions (CI/CD), pytest (testes) e avaliação de Soda para qualidade. Implementação inicial local e de custo de infraestrutura zero como objetivo. **O desenho é planejado, não a declaração de implantação concluída.** A integração e os critérios físicos serão tratados em reuniões técnicas posteriores, sem substituição de componentes por conveniência.

### 16.2 Gate de saída de reunião

Toda reunião encerra com: (a) decisões vinculadas ao objetivo da reunião; (b) premissas rotuladas; (c) tarefas pendentes encaminhadas com responsável e reunião de destino; (d) evidências documentais; (e) registro de aceite *simulado* separado do aceite real. O fechamento do Kickoff está na ATA-KO-001. A abertura controlada da Reunião 2 está no arquivo `05-reuniao-02-abertura-e-agenda.md`.

### Quadro de aprovação simulada (não assinado)

| Função | Nome fictício | Situação |
|---|---|---|
| Patrocinadora | Helena Duarte | Aprovação **simulada apenas do Kickoff**; escopo final pendente |
| Product Owner | Camila Rocha | Pendente |
| TI/Segurança | Beatriz Nascimento | Pendente |
| Consultor responsável | Mr. João Caneca | Documento preparado para revisão |

---

## 17. Glossário

- **AS-IS / TO-BE:** processo atual e processo futuro desenhado.
- **Forecast:** previsão de condição futura, sujeita a atualizações e erro.
- **Snapshot:** fotografia de previsão obtida em determinada execução.
- **Idempotência:** o mesmo processamento/replay não provoca efeitos duplicados indevidos.
- **Data Contract:** acordo sobre forma, significado, qualidade e disponibilidade dos dados.
- **Critério de aceite:** teste verificável que indica conformidade com um requisito.
- **MVP:** entrega mínima que demonstra valor e viabilidade.

## 18. Referências internas

- `01-business-case-v1.1.md` — justificativa, problema, proposta e valor.
- `02-discovery-requisitos-escopo-v1.0.md` — este documento mestre de discovery e escopo.
- `03-data-contract-v1.0.md` — próximo documento, ainda não produzido.


---

## 17. Atualização de governança — Reunião 2 (v1.2)

**Documento detalhado:** [`06-ata-reuniao-02-processos-as-is-to-be.md`](06-ata-reuniao-02-processos-as-is-to-be.md).

Os dois desenhos editáveis do AS-IS e TO-BE foram validados pelo responsável do projeto no VS Code/Excalidraw. O TO-BE exigiu correção de `index` dos elementos para permitir carregamento na extensão; o candidato corrigido abriu, e o arquivo final foi validado após guardar e reabrir.

- **AS-IS:** consulta manual em fontes diversas → interpretação → consolidação → comunicação → planejamento → decisão humana.
- **TO-BE:** coleta e validação → preservação histórica → publicação estruturada → consultas comparáveis → decisão humana.
- **Questões PB-01 a PB-05:** prioridades e perguntas ratificadas na simulação; PB-05 mantém prioridade secundária.
- **Consumo mínimo aprovado na simulação:** consulta SQL / tabela consolidada reproduzível, sem dashboard obrigatório.
- **Medição de baseline:** metodologia aprovada na simulação; coleta dos dados permanece futura.
- **Decisões DEC-007 a DEC-011:** aprovadas expressamente pelo responsável no cenário simulado em 12/10/2026.
- **Gate R2:** APROVADO NA SIMULAÇÃO. A ata R2 formaliza as decisões; integração na `main` ainda pendente.

As decisões de projeto já estabelecidas no Kickoff (DEC-001 a DEC-006) permanecem vigentes. Não alterar a arquitetura aprovada conceitualmente nem afirmar implantação dos componentes futuros.

**Controle de versões:** as seções anteriores que apresentam a R2 como roteiro ou “a validar” refletem a preparação inicial. Para o estado final da R2 prevalecem a seção 17 desta versão e a ATA-R2-001. As reuniões 3–5 continuam propostas, sem aceite.