# Contrato de dados meteorológicos — v0.1

**Projeto:** PHD-AL-2026-001 | **Status:** aprovado apenas como baseline documental na simulação R3; implementação pendente.

## Domínio e grãos
- Fonte Open-Meteo; cinco localidades SP (Campinas, São Paulo, Sorocaba, Jundiaí, Ribeirão Preto), IDs a cadastrar.
- Métricas: temperatura °C, precipitação mm, vento km/h. Valores ausentes permanecem `null`.
- `locations(location_id, name, latitude, longitude, timezone)`: dimensão estável, não SCD; geografia histórica preservada por coleta.
- `weather_batches(batch_id, scheduled_at, started_at, ended_at, batch_status, is_late)`: uma rodada de cinco localidades.
- `weather_runs(run_id, batch_id, location_id, requested_at, collected_at, source, endpoint, request_params, raw_path, raw_sha256, run_status)`: uma solicitação lógica por localidade, com parâmetros congelados.
- `weather_attempts(attempt_id, run_id, attempt_no, started_at, ended_at, duration_ms, http_status, error_category, error_message)`: tentativas individuais de HTTP.
- `weather_forecasts(run_id, location_id, forecast_time_utc, temperature_2m_c, precipitation_mm, wind_speed_10m_kmh)`: previsão horária versionada; unicidade por `(run_id, forecast_time_utc)` caso cada run corresponda a uma única localidade; validar vínculo por FK.
- `planning_cycles(planning_cycle_id, cycle_date_local, window_start_utc, window_end_utc, timezone)`: contextos imutáveis das reuniões de planejamento.
- `publication_events(publication_id, batch_id, location_id, run_id, product_type, published_at, status, fallback_used, fallback_reason)`: registro de disponibilidade efetiva, incluindo versões utilizadas.

Nomes lógicos; a modelagem SQL definitiva será validada na implementação.

## Temporalidade
- Ciclo D, reunião 15h São Paulo: janela fixa `[D 16:00, D+2 00:00)` no timezone `America/Sao_Paulo`, normalmente 32 horários.
- `collected_at` é a referência imutável de completude. O primeiro horário elegível é a primeira hora cheia **igual ou posterior** à coleta, limitado ao início da janela do ciclo; se coleta 18:07, começa 19:00. Antes do início do ciclo, exigir a janela inteira.
- Armazenar instantes normalizados em UTC. Não presumir offset -03:00 eternamente; tratar regras reais de timezone e possível variação na contagem de horas.
- Consultas operacionais mostram horários ainda futuros no instante da consulta e versões aptas, frescas e já publicadas. Consulta histórica com `as_of_at` não pode usar versões com `published_at > as_of_at`.
- Agenda a cada duas horas nas horas pares; rodada pré-planejamento 14h00, tentativas concluídas/canceladas até 14h15, publicação-limite 14h30. Frescor máximo 3 horas calculado no uso.

## Qualidade, fallback e integridade
- Estados de rodada `success`, `partial_success`, `failed`; atraso sinalizado separadamente. Estado de cada localidade/produto distinto.
- `validated_with_nulls` não equivale a aptidão universal; publicar agregado integral apenas quando métricas e horários necessários estiverem completos.
- Falhas em uma cidade não bloqueiam outras. Fallback escolhe uma **versão inteira** anterior publicada, fresca e integralmente apta ao produto; identificar versão e motivo. Nunca misturar dados de runs diferentes silenciosamente.
- Preservar Raw e `raw_sha256` dos bytes realmente gravados. Replay do mesmo Raw e `run_id` mantém contagens; conteúdo conflitante com o mesmo ID: bloquear e auditar; nova solicitação HTTP ≠ replay.
- Falhas, retentativas e `published_at` reais são auditáveis; publicação tardia não deve reescrever disponibilidade histórica.

## Dependências
Este contrato NÃO comprova funcionamento no PostgreSQL, Airflow ou cinco localidades. Validar limites/parâmetros Open-Meteo, coordenadas/IDs, cobertura UTC/fuso, desempenho sob a agenda, controles de concorrência, backup/retenção e testes descritos na [Matriz DQ](09-matriz-qualidade-weather-v0.1.md). Nada disso está implementado pelo simples aceite simulado.
