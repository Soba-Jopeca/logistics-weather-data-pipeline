# Matriz de Data Quality meteorológica — v0.1

**PHD-AL-2026-001 | Status:** baseline aprovado na R3 simulada; testes a implementar.

| ID | Regra de qualidade | Reação esperada |
|---|---|---|
| DQ-01 | Estrutura JSON, séries, campos e unidades obrigatórias | Rejeitar payload inválido e auditar |
| DQ-02 | Cobertura de todos os horários exigidos por ciclo e `collected_at` | Não publicar produto de janela integral incompleta |
| DQ-03 | Unicidade por run e horário UTC; replay sem multiplicação | Bloquear duplicações |
| DQ-04 | Tipos numéricos finitos, timestamps válidos, °C/mm/km/h | Rejeitar valores inválidos |
| DQ-05 | Precipitação e vento não negativos | Rejeitar valor inválido |
| DQ-06 | Horários consecutivos, normalizados UTC e timezone IANA | Rejeitar sequência incoerente |
| DQ-07 | Versão até três horas de idade no instante do uso | Fallback apto ou indisponibilidade |
| DQ-08 | Linhagem: batch/run/attempt, parâmetros, hash Raw, coleta e publicação | Não declarar aptidão sem rastreabilidade |
| DQ-09 | Falha local não bloqueia as demais localidades | Rodada parcial e resultados individuais |
| DQ-10 | Nulos ≠ zero; soma/média/máximo integrais exigem todas horas/métricas | Exibir parcial rotulado ou não publicar total |
| DQ-11 | Fallback para versão anterior integralmente apta e publicada, sem mescla | Identificar versão e motivo |
| DQ-12 | Mesmo run com bytes/contrato conflitantes | Preservar original e registrar incidente |

## Testes de aceite — pendentes de execução

1. Cinco cidades válidas com rastreabilidade e publicação até 14h30.
2. Timeout individual e nulos por métrica: demais cidades e produtos continuam disponíveis.
3. Versão recente incompleta: fallback fresco e apto, com `run_id` e justificativa.
4. Todas versões expiradas: indisponibilidade explícita.
5. Replay repetido: contagem idêntica; conflito no mesmo run: rejeição.
6. Virada de dia e ciclo, 32 horas iniciais e redução por horas passadas; sobreposição de ciclos sem duplicação artificial.
7. Coleta 18:07 exige horas a partir de 19:00; consulta histórica exclui publicação futura.
8. Cada retry HTTP tem tentativa, duração e resultado; encerramento até 14h15; atraso após 14h30 é sinalizado.
9. Falha de persistência não registra publicação bem-sucedida; status de rodada e disponibilidade separados.

**Severidade:** falha estrutural/tempo/unicidade/valores obrigatórios bloqueia o produto afetado; nulidade em métrica não requerida apenas sinaliza; expiração sem fallback significa indisponibilidade. Ver [Contrato v0.1](08-contrato-dados-weather-v0.1.md).
