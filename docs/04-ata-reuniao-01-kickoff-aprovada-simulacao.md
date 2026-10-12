# ATA-KO-001 — Reunião 1 | Kickoff — APROVADA NA SIMULAÇÃO

**Projeto:** PHD-AL-2026-001 — Logistics Weather Data Pipeline
**Consultoria:** Phoenix Data | **Cliente fictício:** AuroraLog Transportes & Distribuição S.A.
**Reunião simulada para:** 13/10/2026, 60 minutos | **Consolidação documental:** 12/10/2026
**Condução:** Mr. João Caneca
**Status:** Encerrada e aprovada exclusivamente no exercício fictício. Não representa reunião realizada, assinatura ou consentimento de pessoas reais.

## 1. Participantes e autoridade

- Helena Duarte — Diretora de Operações, patrocinadora do cenário.
- Rafael Mendes — Gerente de Transportes, valida necessidade operacional.
- Camila Rocha — Coordenadora de Planejamento e Product Owner, valida utilidade e prioriza requisitos.
- João Caneca — Consultor Phoenix Data, conduz discovery e documenta.

## 2. Evidências narrativas da entrevista (todas simuladas)

1. O planejamento do dia seguinte começa aproximadamente às **15h**.
2. A equipe de planejamento tem oito pessoas, das quais quatro consultam previsões com regularidade.
3. Em dias de instabilidade, consolidar informações pode consumir de 20 a 30 minutos **decorridos por ciclo**, sem atribuir esse valor a cada pessoa.
4. Fontes e horários de consulta variam, dificultando comparação, histórico e auditoria.
5. Alterações de viagens dependem de avaliação humana e de fatores adicionais; o MVP não deve afirmar que prevê atrasos ou reduções de custos.

## 3. Declaração do problema validada

A AuroraLog carece de uma visão padronizada, histórica e rastreável das condições meteorológicas previstas nas regiões atendidas, disponível antes da tomada de decisão diária. O problema prioritário é a qualidade e acessibilidade da informação, não a inexistência de meteorologia e tampouco um nexo já comprovado com atrasos.

## 4. Decisões aprovadas no exercício

| ID | Decisão | Consequência |
|---|---|---|
| DEC-001 | Centralizar e estruturar previsões horárias para apoiar decisão humana | Foco informacional do MVP |
| DEC-002 | Localidades piloto: Campinas, São Paulo, Sorocaba, Jundiaí e Ribeirão Preto | Cinco regiões ficticiamente atendidas; coordenadas serão validadas |
| DEC-003 | Valor de 20–30 min significa tempo decorrido por ciclo de consolidação em dias instáveis | Hipótese; não converter em horas-pessoa ou economia sem medição |
| DEC-004 | Informações disponíveis e atualizadas antes das 15h, no fuso America/Sao_Paulo | Frequência, margem e regra de frescor serão operacionalizadas em etapa técnica |
| DEC-005 | Sem alteração automática de rotas, cancelamentos ou projeção de SLA | Limite funcional explícito |
| DEC-006 | Preservar arquitetura técnica de referência previamente planejada | Refinar detalhes, sem reiniciar seleção de stack |

## 5. Premissas, restrições e exclusões

**Premissas:** operações, equipe e tempos são fictícios; dados da API não garantem condições de rodovia; cinco localidades formam um piloto, não abrangência nacional; horizonte inicial de 24 passos horários.
**Restrições:** infraestrutura inicial local e sem custo recorrente planejado; rastreabilidade das extrações; versão e horário das previsões; entrega antes das 15h.
**Fora do MVP inicial:** previsão de atrasos, otimização/cancelamento automático de rotas, cálculo comprovado de economia, integração operacional obrigatória com TMS.

## 6. Referência técnica (não aceite de implantação)

Open-Meteo API → Python + JSON bruto → PostgreSQL / SQL / ELT → consultas analíticas; Docker; Apache Airflow; GitHub Actions; pytest; Soda em avaliação. A extração Python e validações iniciais de 24 passos já tiveram testes locais informados; **não** se declara que todos os componentes estejam operacionais.

## 7. Transferência de responsabilidades para as próximas reuniões

| Item | Dono | Destino | Estado |
|---|---|---|---|
| Mapear AS-IS, destinatários, perguntas de negócio e TO-BE operacional | Rafael, Camila, Bruno, João | Reunião 2 | Planejado, não pendência de Kickoff |
| Definir medição do tempo manual e esforço-pessoa | Camila e Bruno | Reunião 2 | Planejado |
| Confirmar identificadores e coordenadas e regras de timestamps | João e Camila | Reunião 3 | Planejado |
| Estabelecer frequência técnica, frescor e política de falhas | João, Beatriz e Camila | Reunião 3 | Planejado |
| Acordar limiares de atenção, prioridades e critérios de aceite | Rafael, Camila, Helena | Reuniões 3–5 | Planejado |

## 8. Aprovação e gate

**Decisão do patrocinador (simulação):** a AuroraLog reconhece o problema e autoriza a Phoenix Data a continuar o discovery. Não concede aceite final do MVP nem aprovação de orçamento.
**Registro de aceite da simulação:** quatro verificações de fechamento confirmadas pelo usuário em 12/10/2026.
**GATE-R1 = APROVADO NA SIMULAÇÃO.** Não há item de responsabilidade do Kickoff sem decisão ou encaminhamento.
**Próxima reunião:** Reunião 2 — Mapeamento AS-IS / TO-BE (roteiro separado).
