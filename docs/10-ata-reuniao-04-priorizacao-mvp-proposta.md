# ATA-R4-001 — Priorização e critérios de aceite do MVP

**Projeto:** PHD-AL-2026-001 | Phoenix Data × AuroraLog (ambas entidades do exercício fictício)  
**Data prevista da reunião simulada:** 21/10/2026 | **Documento preparado em:** 12/10/2026  
**Participantes do cenário:** Helena Duarte (patrocínio), Rafael Mendes (operações), Camila Rocha (PO), Beatriz Nascimento (TI) e João Caneca (consultoria).  
**Estado:** proposta executiva da R4, preparada pelo consultor na simulação; **aguarda validação do usuário e gate R5**. Não representa reunião real nem aceite real do cliente.

## 1. Objetivo e antecedentes
Transformar as decisões R1–R3 em backlog executável, critérios de aceite observáveis e fronteiras de escopo, mantendo MVP local de infraestrutura zero e decisão operacional humana.

**Controle de versões:** a documentação anterior (discovery v1.2) descreve em partes horizonte de 24 horas. O contrato R3 v0.1 formaliza **janela fixa por ciclo de D 16h até D+2 00h exclusivo (32 horários usuais em São Paulo)**; esta decisão **substitui 24h para o MVP alvo**. O script atualmente extrai 24 horários para Campinas e será evoluído; não declarar implementado.

## 2. Priorização MoSCoW proposta
| Classe | Itens |
|---|---|
| Must | Cadastro estável das cinco localidades; configuração de geografia por coleta; extração Open-Meteo de janela por ciclo; Raw imutável; horário UTC; PostgreSQL; histórico de versões; batch/run/attempt; auditoria de tentativas; DQ seletiva por métrica; nulos explícitos; replay idempotente e detecção de conflito; disponibilidade por localidade; fallback de versão inteira; consultas SQL; Docker local; Python/SQL testes; Airflow com agendamento nas horas pares; GitHub Actions; documentação e logs |
| Should | Comparação de versões; limiares demonstrativos parametrizáveis de atenção meteorológica, sem inferir impacto de entrega |
| Could | Relatório visual estático; notificações demonstrativas |
| Won't | TMS/ERP/GPS, previsões de atraso, classificação causal de risco, roteirização, ação automática de transporte, dashboard empresarial, cloud paga, SLA/monitoramento 24x7 |

### Dependências / escolhas técnicas
- O pipeline de 32 horários requer parâmetros de consulta API e validação de cobertura além do extrator de 24 passos atual.
- `collected_at` define completude: primeira hora cheia >= instante de coleta, dentro da janela fixa; consulta corrente exclui horários já passados.
- Publicação até 14h30 com tentativas terminadas até 14h15 é **alvo a comprovar**, não garantia.
- Identificar localidades/parametrizar coordenadas corretas; sem SCD no MVP.
- Camila/Rafael devem validar limiares de atenção; parâmetros de demo nunca equivalem a risco de atraso.
- Não há baseline medido de 20–30 minutos de economia; trata-se de hipótese de tempo decorrido de consolidação, a confirmar no piloto.

## 3. Critérios de aceite (evidência obrigatória)
| ID | Critério | Evidência |
|---|---|---|
| AC-01 | Cinco localidades configuradas e extraídas, com IDs estáveis | Run de teste, registros por localidade e parâmetros |
| AC-02 | Janela inicial do ciclo: 32 horários esperados sem lacunas ou duplicatas | SQL de cobertura / testes temporalidade |
| AC-03 | Atualizações a cada 2h, hora par; corte 14h15; publicação-alvo 14h30 | Histórico de scheduler, attempts, publish timestamps e teste de atraso |
| AC-04 | Raw íntegro, rastreável, imutável por run; conflito de hash bloqueado | Arquivo, hash, teste de conflito |
| AC-05 | Replay da mesma execução sem duplicação; nova coleta cria nova versão | Teste duas execuções de replay e SQL count |
| AC-06 | Nulos não viram zero; métricas incompletas não produzem totais falsamente completos | Testes DQ e consultas |
| AC-07 | Falha em uma cidade não bloqueia outras; fallback identificado e dentro de frescor de 3h | Testes com erro HTTP, fallback e indisponível |
| AC-08 | Consulta histórica as-of retorna apenas versões publicadas até instante pedido | SQL e fixtures de timestamps |
| AC-09 | Consultas respondem por cidade/hora, precipitação, vento, temperatura, qualidade, atualização e janelas demonstrativas de atenção | Queries e resultados documentados |
| AC-10 | Execução local reproduzível e sem cloud paga, com Docker/PostgreSQL/Airflow, automação de teste e documentação | README, comandos de execução, testes e pipeline GitHub Actions |
| AC-11 | Erros, tentativas HTTP, durações e status por localidade auditáveis | Tabelas e logs de execução |
| AC-12 | Consulta apresenta as limitações: dado meteorológico, não previsão de atraso | README/documentação e resultado SQL com status |

**Aceite:** Must + AC-01..12 sem bloqueios críticos, ou exceções explicitamente aceitas pela PO fictícia no playback. Performance da agenda não validada implica pendência de aceite desse requisito, não declaração de sucesso. Critérios operacionais de limiar ainda exigem aprovação de negócio.

## 4. Riscos e mitigação
| Risco | Mitigação |
|---|---|
| 32 horas não cobertas por parâmetros Open-Meteo atuais | POC de janela, testes API e UTC antes de modelagem definitiva |
| Falha de API, limite de tempo, atualização atrasada | Timeouts, tentativas até 14h15, publicação independente, status/fallback explícitos |
| Mudança de coordenadas ou metadados | location_id estável e request_params por execução |
| Conflito de replay e concorrência | hash Raw, restrições SQL, transações e testes |
| Dados parciais/nulos | DQ por métrica/produto, evitar tratar nulo como zero |
| Custos/complexidade local | Docker e APIs gratuitas; evitar cloud paga; medir uso de disco |
| Baseline de produtividade não medido | Cronometrar processo manual no piloto; não prometer ganhos |
| Agenda não cumprir prazo | Testes com métricas de duração, sem tratar alvo como SLA contratual |
| Documento v1.2 desatualizado em relação a R3 | Registrar supersessão expressa neste documento; atualizar baseline mestre no gate de R5 |

## 5. Plano incremental proposto para engenharia
1. **Fundação:** configuração das cinco localidades, decisões de fuso/janela, contratos, fixtures e testes Python.
2. **Ingestão:** extração com separação batch/run/attempt, arquivo Raw e auditoria robusta.
3. **Persistência:** Docker PostgreSQL, schema, cargas idempotentes e regras de integridade.
4. **Qualidade/consumo:** DQ por produto, queries SQL, atual/histórico, indicadores de atenção demonstrativos.
5. **Orquestração/entrega:** Airflow agenda e retentativas, testes de prazo, logs, CI/CD e README reprodutível.

Cada etapa exige teste de aceite e PR; não implementar tudo de uma vez. Escolhas comerciais/operacionais são aprovadas no cenário por Camila/Helena, não assumidas como fatos reais.

## 6. Gate
**R4 proposta estruturada pelo consultor para validação:** não foi aprovado nem mergeado automaticamente. Próximo: revisão do usuário, integração GitHub, playback R5 e aprovação condicional simulada para iniciar implementação.

**Referências:** [Discovery v1.2](02-discovery-requisitos-escopo-v1.2.md), [Ata R3](07-ata-reuniao-03-contrato-dados-aprovacao-simulada.md), [Contrato R3](08-contrato-dados-weather-v0.1.md), [Matriz DQ](09-matriz-qualidade-weather-v0.1.md).
