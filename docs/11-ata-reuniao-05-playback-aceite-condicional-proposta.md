# ATA-R5-001 — Playback e aceite condicional do MVP

**PHD-AL-2026-001 | Phoenix Data × AuroraLog — simulação didática**  
**Reunião prevista no cenário:** 23/10/2026 | **Proposta elaborada antecipadamente:** 12/10/2026  
**Participantes fictícios:** Helena Duarte, Rafael Mendes, Camila Rocha, Beatriz Nascimento, Bruno Tavares e João Caneca.  
**Estado:** minuta para revisão e confirmação do usuário. **Nenhum aceite real, reunião efetiva ou implementação são alegados.**

## 1. Playback executivo
**Problema:** meteorologia consultada de modo disperso, sem histórico de versões e sem rastreabilidade do que estava disponível no planejamento. A hipótese de consolidação manual de 20–30 minutos por ciclo em dias instáveis **não foi medida**.

**Solução delimitada:** pipeline local que coleta previsões Open-Meteo por cinco localidades, guarda Raw e histórico, aplica qualidade por produto, registra falhas e versões, publica resultados analíticos via SQL para apoiar **decisões humanas**. Não infere atrasos de entregas, não altera roteiros e não calcula causalidade operacional.

**Localidades do piloto:** Campinas, São Paulo, Sorocaba, Jundiaí e Ribeirão Preto. IDs estáveis; coordenadas e parâmetros precisam de validação técnica.

**Arquitetura-alvo:** API Open-Meteo → Python Raw/validação → PostgreSQL e transformações SQL → consultas analíticas; Docker local, Airflow, pytest/DQ e GitHub Actions. Arquitetura é **plano de implementação**, não entrega concluída.

## 2. Contrato e decisões aprovadas em exercícios anteriores
- R1: problema, papéis, cinco localidades e planejamento das 15h; tempo manual é hipótese.
- R2: AS-IS/TO-BE, perguntas e priorização; SQL mínimo viável sem dashboard.
- R3: ciclo D 16h a D+2 00h (32 horários usuais), coleta a cada 2h, rodada 14h e corte 14h15, publicar até 14h30 como meta a demonstrar; janela estável, UTC, histórico e consulta point-in-time, fallback rastreável, DQ seletiva, auditabilidade batch/run/attempt e idempotência. **Este contrato de 32 horas substitui o horizonte anterior de 24h para o alvo MVP.**
- R4: MoSCoW e AC-01..AC-12; exclusões de TMS, GPS, atrasos previstos, roteirização, dashboard empresarial e serviços pagos.

## 3. Recomendações de decisão para o gate R5 (simuladas, aguardam confirmação)
| ID | Recomendação | Condição |
|---|---|---|
| G5-01 | Aceitar escopo do MVP para início da implementação | Conforme Must da R4, sujeito a AC-01..AC-12 |
| G5-02 | Autorizar desenvolvimento incremental, por PR e testes | Não confundir entrega de etapa com aceite final |
| G5-03 | Manter limiares meteorológicos apenas demonstrativos | Camila/Rafael validam interpretação operacional antes de uso real |
| G5-04 | Exigir evidência para agenda 14h/14h15/14h30 e frescor 3h | Medir desempenho, casos de falha e atrasos |
| G5-05 | Priorizar solução local sem recursos de nuvem pagos | Monitorar custos indiretos/armazenamento e limitações |
| G5-06 | Preservar fronteira do escopo | Nenhuma promessa de melhoria de SLA/atrasos |
| G5-07 | Rever baseline mestre para consistência 24h→32h | Atualização documental controlada no próximo PR |
| G5-08 | Registrar responsável por aceite do MVP | PO simulada: Camila; patrocínio simulado: Helena |

**Decisão simulada ainda não formalizada:** proposta de **aprovação condicional do escopo para desenvolver**, NÃO aceite do produto pronto.

## 4. Pendências / riscos que não bloqueiam iniciar o desenvolvimento
1. Confirmar IDs, coordenadas e fuso de cada localidade; documentar alterações preservando parâmetros históricos.
2. Experimentar parâmetros da Open-Meteo para cobertura completa do ciclo, inclusive virada de dia e timezone; adaptar extrator atual de 24h.
3. Implementar, testar e medir etapas antes de afirmar que publicação até 14h30 é viável; manter timeout/corte de tentativas como critérios a demonstrar.
4. Definir valores e interpretação de limiares operacionais; durante desenvolvimento usar exemplos rotulados como demonstração.
5. Validar retenção/backup, controle do disco, segurança de variáveis e credenciais, consistência da publicação e teste de concorrência.
6. Levantar baseline manual real apenas em eventual piloto, sem contabilizar benefício antes da medição.

## 5. Plano executivo de transição para engenharia
| Marco | Entrega | Evidência / gate |
|---|---|---|
| E1 — Fundação | Ambientes, configs/cidades, janela, normalização UTC e fixtures | Testes do contrato temporal; comandos reproduzíveis |
| E2 — Coleta | Cinco localidades, rodada/coleta/tentativa, falhas, Raw/hash | Testes de erro/retentativa/rastreabilidade |
| E3 — Persistência | Docker PostgreSQL, tabelas, versões, replay idempotente | Testes de integridade, duplicação e conflitos |
| E4 — Consumo | Regras DQ, atual/histórico, fallback, SQL de negócio | Evidências AC por produto e exemplos |
| E5 — Orquestração | Airflow, horários pares, publicação, logs, CI/CD | Testes de agenda, prazo, recuperação e execução ponta a ponta |

Sequenciar do simples ao complexo; revisão de código por PR e demonstração prática a cada etapa. Projeto existente: `scripts/extract_weather.py` manual Campinas/24 horas com Raw local e validações; todas as demais capacidades acima permanecem pendentes.

## 6. Critérios de aceite e limites do documento
A avaliação final do MVP utilizará [AC-01..AC-12 da R4](10-ata-reuniao-04-priorizacao-mvp-proposta.md) e a [Matriz DQ v0.1](09-matriz-qualidade-weather-v0.1.md). Aceite do escopo para desenvolvimento não certifica operação, dados históricos gerados, SLA, performance nem indicadores de negócio.

## 7. Registro de aceite do exercício
- **Status atual:** proposta R5 pronta para revisão.
- **Se o usuário confirmar esta minuta:** registrar aceite condicional **somente dentro da simulação** e encerrar o discovery, abrindo a fase E1.
- **Sem confirmação:** permanecer como proposta. Não atribuir falas ou assinaturas reais à AuroraLog.

**Referências:** [Discovery v1.2](02-discovery-requisitos-escopo-v1.2.md) · [Ata R3](07-ata-reuniao-03-contrato-dados-aprovacao-simulada.md) · [Contrato v0.1](08-contrato-dados-weather-v0.1.md) · [R4](10-ata-reuniao-04-priorizacao-mvp-proposta.md).
