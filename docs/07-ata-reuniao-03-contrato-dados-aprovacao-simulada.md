# ATA-R3-001 — Reunião 3 | Contrato, qualidade e governança

**Projeto:** PHD-AL-2026-001 | **Phoenix Data × AuroraLog:** cenário fictício  
**Reunião prevista no cenário:** 19/10/2026 | **Registro antecipado do exercício:** 12/10/2026  
**Participantes simulados:** João Caneca, Camila Rocha, Beatriz Nascimento, Bruno Tavares; Rafael Mendes consultado no aspecto operacional.  
**Status:** **ENCERRADA E APROVADA SOMENTE NA SIMULAÇÃO**, como baseline documental v0.1; não é aceite de cliente real nem certificação da implementação.

## Diagnóstico anterior à reunião
O `scripts/extract_weather.py` já extrai manualmente Campinas via Open-Meteo, solicita 24 passos horários, valida estrutura/unidades/tempos, preserva nulos e Raw JSON, `run_id`, `requested_at` e `collected_at`. PostgreSQL, Airflow, automação, cinco cidades, janela de 32h e publicação operacional continuam **planejados**.

## Decisões da R3
| ID | Tema | Decisão |
|---|---|---|
| R3-01 | Identidade | `location_id` estável e dimensão simples; coordenadas solicitadas preservadas em cada coleta; sem SCD no MVP |
| R3-02 | Grão e histórico | Uma previsão por `run_id`, localidade e hora UTC; preservar cada versão |
| R3-03 | Entidades | Separar rodada `batch_id`, coleta local `run_id`, tentativa HTTP `attempt_id` e ciclo `planning_cycle_id` |
| R3-04 | Auditoria | Registrar cada tentativa HTTP, tempos, duração, status, erro e vínculo à coleta |
| R3-05 | Idempotência | Replay do mesmo Raw não duplica; mesmo `run_id` com conteúdo divergente bloqueia e gera incidente |
| R3-06 | Ciclo | Janela fixa de D 16:00 até D+2 00:00 exclusivo, em São Paulo, normalmente 32 horários |
| R3-07 | Completude | Em coleta intermediária contar só horas a partir de `ceil_hour(collected_at)`, limitadas à janela do ciclo; preservar passado no histórico |
| R3-08 | Frequência | Coletas em horas pares a cada 2 horas |
| R3-09 | Pré-planejamento | Rodada às 14h; todas as tentativas devem terminar até 14h15; publicação até 14h30 |
| R3-10 | Frescor | Máximo de 3 horas no instante da consulta |
| R3-11 | Nulos | Preservar `null`; indicadores completos exigem métricas completas nos horários requeridos |
| R3-12 | Publicação | Parcial por localidade/produto, sem bloquear cidades saudáveis |
| R3-13 | Fallback | Última versão integralmente apta para a consulta, fresca e publicada; sinalizar `run_id` e motivo |
| R3-14 | Histórico point-in-time | Jamais apresentar como disponível antes de `published_at`; preservar versões anteriores |
| R3-15 | Retenção | Preservar Raw e histórico no MVP local enquanto houver capacidade; monitorar disco e revisar retenção/backups antes de produção |

## Gate e riscos
- **P01:** agenda, cortes, atraso e independência entre localidades especificados; performance e timeout a validar em testes.
- **P02:** janela fixa por ciclo e completude a partir da coleta aprovadas na simulação; considerar conversão IANA/UTC.
- **P03:** modelo lógico e auditoria individual aprovados como contrato conceitual; migração física pendente.
- **P04:** qualidade seletiva, falhas, fallback, publicação parcial e retenção inicial definidos; testes pendentes.
- **Dependências:** cadastro real das cinco localidades, comportamento temporal da API, medição de duração de rodada, políticas de backup, testes DQ e eventual ajuste de horário âncora.

**Responsáveis simulados:** Camila aprova critérios de consumo e prazos; Rafael orienta necessidades de transportes; Beatriz valida integridade/segurança; Bruno valida consultas; João elabora implementação e testes; Helena aprova escopo nas R4–R5.

**Artefatos associados:** [Contrato v0.1](08-contrato-dados-weather-v0.1.md) e [Matriz DQ v0.1](09-matriz-qualidade-weather-v0.1.md). **Nenhum código foi alterado nesta reunião.**
