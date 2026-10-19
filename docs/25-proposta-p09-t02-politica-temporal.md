# P09-T02 — Especificação proposta de política temporal e controle de slot

## 1. Identificação, estado e limites

- **Projeto:** Logistics Weather Data Pipeline.
- **Checkpoint:** CP-2026-10-13 v2.
- **Documento:** P09-T02-P02, versão proposta 0.1.
- **Data:** 18/10/2026.
- **Baseline de referência:** `b437d67`.
- **Responsável:** Airflow — Seção 4.
- **Apoio técnico:** Custos e APIs Gratuitas.
- **Estado:** DIFF PROPOSTO, AGUARDANDO APROVAÇÃO DE JOÃO.

P09-T02-P01 foi aceite como arquitetura conceitual, condicionado à abrangência do controle de slot, à separação entre admissão e prontidão e à revisão do frescor.

Esta especificação descreve comportamento futuro. Não comprova sua implementação, funcionamento operacional ou cumprimento de SLA.

P09-T01 está validado e integrado. P09-T02 e passo 09 permanecem não validados. Implementação, testes, E3, agenda e passos 10–11 não estão liberados.

## 2. Requisitos aprovados, hipóteses e decisões pendentes

| Classe | Conteúdo |
|---|---|
| Requisito aprovado | Uma coleta principal diária para apoiar a decisão logística |
| Requisito aprovado | Ciclo D determinado pela data local do slot em `America/Sao_Paulo` |
| Requisito aprovado | Janela `[D 16h, D+2 00h)` preservada |
| Requisito aprovado | Cadência de duas horas excluída do MVP |
| Hipótese operacional | Slot 13h45; último início 14h00; prontidão 14h15; consumo 14h30 |
| Proposta técnica | `CronDataIntervalTimetable`, claim persistente e recuperação conservadora |
| Proposta de qualidade | Cinco cidades, cobertura integral e zero nulos |
| Proposta revisada de frescor | Referência nominal de 45 minutos; limite máximo candidato de 60 minutos no consumo |
| Proposta de fallback | Indisponibilidade explícita, sem substituição automática |

Os valores e mecanismos propostos dependem de ratificação central. Aprovar a publicação deste documento não equivale a autorizar sua implementação.

## 3. Diagnóstico da baseline e referências

A leitura de `b437d67` identificou:

- DAG manual, com `schedule=None`, `catchup=False` e `retries=0`.
- Concorrência configurada em uma run e uma task.
- Preparação com `cycle_date` explícito.
- Identidade de contexto baseada em `dag_id + airflow_run_id`.
- Reivindicação de início por batch, sem reivindicação de slot diário.
- Replay íntegro sem nova coleta.
- Bloqueio quando há início sem conclusão ou artefatos incompatíveis.
- Possibilidade de `batch_status=success` com cidades `validated_with_nulls`.
- Reconciliação sem exigência explícita de `null_count=0`.
- Persistência imutável por temporário, sincronização do arquivo e publicação por `os.link`.

O estado operacional da DAG não é inferido apenas de seu código.

Referências do projeto:

- [Documento 23](https://github.com/Soba-Jopeca/logistics-weather-data-pipeline/blob/b437d67/docs/23-proposta-p09-p01-resiliencia-agendamento.md).
- [Documento 24](https://github.com/Soba-Jopeca/logistics-weather-data-pipeline/blob/b437d67/docs/24-evidencias-p09-t01-offline.md).
- [DAG](https://github.com/Soba-Jopeca/logistics-weather-data-pipeline/blob/b437d67/dags/weather_extract.py).
- [Interface](https://github.com/Soba-Jopeca/logistics-weather-data-pipeline/blob/b437d67/scripts/weather_interface.py).
- [Janela](https://github.com/Soba-Jopeca/logistics-weather-data-pipeline/blob/b437d67/scripts/weather_window.py).
- [Manifesto e persistência](https://github.com/Soba-Jopeca/logistics-weather-data-pipeline/blob/b437d67/scripts/weather_manifest.py).

## 4. Timetable e semântica temporal

| Elemento | `CronDataIntervalTimetable` | `CronTriggerTimetable`, intervalo zero |
|---|---|---|
| Expressão candidata | `45 13 * * *` | `45 13 * * *` |
| Intervalo | Entre duas ocorrências de 13h45 | Pontual |
| `logical_date` | Início do intervalo | Instante nominal |
| `data_interval_end` | Fim do intervalo | Instante nominal |
| `scheduled_slot` proposto | `data_interval_end` | `data_interval_end` |
| Vantagem | Continuidade com a v0.2 | Data lógica mais intuitiva |
| Limitação | Data lógica normalmente pertence a D−1 | Retomada não deve ser presumida como “somente próximo disparo” |

**Recomendação:** `CronDataIntervalTimetable` explícita, com timezone `America/Sao_Paulo`, `catchup=False` e controle temporal independente.

Na versão 2.9.2, há divergência entre exemplos narrativos da documentação de retomada e o código de `CronTriggerTimetable`: com `catchup=False`, o código considera a ocorrência anterior ao relógio atual, além do histórico e das restrições. Não se deve escolher essa alternativa supondo que ela sempre descartará o slot vencido.

Essa conclusão é estática. A caracterização futura deverá exercitar as funções da versão efetivamente utilizada, sem scheduler operacional.

Referências:

- [Timetables — Airflow 2.9.2](https://airflow.apache.org/docs/apache-airflow/2.9.2/authoring-and-scheduling/timetable.html).
- [Implementação de intervalo](https://airflow.apache.org/docs/apache-airflow/2.9.2/_modules/airflow/timetables/interval.html).
- [Implementação de trigger na tag 2.9.2](https://github.com/apache/airflow/blob/2.9.2/airflow/timetables/trigger.py).

Regras propostas:

1. `scheduled_slot` representa o instante nominal, não o início real da task.
2. `cycle_date` é a data desse instante em `America/Sao_Paulo`.
3. Datas lógicas e intervalos servem à orquestração; não representam a janela meteorológica.
4. O relógio atual decide elegibilidade, mas nunca redefine D.
5. Timestamps sem timezone ou contexto incompatível são rejeitados.
6. Uma execução manual não infere D de seu intervalo Airflow.

## 5. C01 — Identidade e serialização canônica do slot

A identidade lógica será composta por:

- pipeline estável;
- finalidade;
- instante nominal em UTC.

Exemplo de conteúdo canônico, em uma única linha:

```json
{"pipeline":"logistics-weather-data-pipeline","purpose":"daily-logistics-decision","scheduled_slot_utc":"2026-10-19T16:45:00Z"}
```

Serialização proposta:

- UTF-8;
- chaves ordenadas;
- sem espaços opcionais ou quebra de linha final;
- timestamp UTC com segundos, sem fração, terminado em `Z`;
- campos exatos, sem atributos adicionais;
- SHA-256 dos bytes canônicos como identificador do slot.

Representações equivalentes, como `13:45:00-03:00` e `16:45:00Z`, devem produzir a mesma identidade após normalização.

Não entram na chave:

- Airflow run ID;
- batch ID;
- tentativa;
- commit;
- versão de configuração;
- proprietário.

A versão da política e o fingerprint da configuração ficam no registro de controle. Divergência não cria outro slot: gera conflito.

Caminho candidato:

`data/orchestration/slots/<slot_sha256>/claim.json`

Esse caminho e seu conteúdo constituem uma **nova especificação de controle**, ainda sujeita a aprovação.

Mudanças de horário, finalidade ou namespace exigem plano de transição. Não podem liberar automaticamente duas rodadas principais para o mesmo D.

## 6. C01 — Participantes e abrangência

| Caminho | Política futura proposta |
|---|---|
| Airflow agendado | Participação obrigatória no protocolo |
| Airflow manual para a finalidade diária | Resolver o slot diário de D e disputar a mesma chave |
| CLI para a finalidade diária | Participar do mesmo protocolo e usar o mesmo armazenamento |
| Replay | Consultar o slot e o batch original; não adquirir nova rodada |
| Testes offline | Usar raízes sintéticas separadas |
| Coleta extraordinária | Fora do MVP; exige autorização e desenho próprio |
| Código antigo ou chamada direta ao coletor | Caminho não protegido; impede declaração de unicidade global |

Informar `cycle_date` manualmente não autoriza ignorar prazo ou claim.

Antes de qualquer agenda futura, será necessário inventariar os pontos de entrada de produção e:

- integrar os produtores autorizados ao protocolo;
- impedir que caminhos de produção suportados façam coleta diária sem controle;
- documentar os caminhos residuais e seus limites.

A garantia proposta é:

> No máximo uma rodada admitida por slot entre produtores participantes, que compartilhem a mesma identidade, protocolo e armazenamento.

Não é garantia de unicidade global contra execução arbitrária de código, acesso direto à API ou produtores que contornem o mecanismo. Também não limita a rodada a uma única tentativa HTTP.

## 7. C01 — Claim atômico, estados e recuperação

O claim proposto é imutável e contém, no mínimo:

- identidade e hash do slot;
- versão do registro e da política;
- proprietário e token exclusivo;
- contexto original de origem;
- batch ID e IDs meteorológicos por cidade;
- fingerprint da configuração e localidades;
- instante da reivindicação.

Sequência:

1. Validar contexto e admissão temporal.
2. Gerar identidades e token em memória.
3. Gravar documento completo em temporário no mesmo filesystem.
4. Sincronizar o arquivo e publicar exclusivamente no destino.
5. Distinguir criação bem-sucedida, destino existente e falha.
6. Somente o vencedor prossegue para o manifesto.
7. Revalidar o prazo antes da extração.
8. Manter a barreira existente de `started.json` por batch.

O helper atual aceita um destino existente com bytes idênticos. Portanto, seu retorno isolado não comprova aquisição inédita de propriedade.

O claim não deve ser sobrescrito para representar progresso. Estados são derivados dos artefatos e de registros adicionais imutáveis.

| Estado observado | Interpretação | Conduta |
|---|---|---|
| Ausente | Slot ainda não reivindicado | Admitir disputa se temporalmente elegível |
| Reivindicado | Claim íntegro, execução ainda não concluída | Somente fluxo proprietário original pode avançar |
| Em execução | `started.json` presente, sem conclusão | Outros participantes bloqueados |
| Concluído | Conclusão e artefatos íntegros | Permitir verificação/replay, sem HTTP |
| Conflito | Outra propriedade ou configuração incompatível | Preservar original e bloquear |
| Corrompido | Registro ilegível, chave ou referências incoerentes | Bloquear; não reconstruir automaticamente |
| Interrompido/ambíguo | Claim existente sem continuidade comprovada | Inspeção autorizada; sem tomada automática |
| Expirado antes da extração | Claim adquirido, prazo perdido em fila | Preservar reserva e registrar inelegibilidade |

A ausência de heartbeat não comprova morte do proprietário. Não haverá TTL, expiração de propriedade ou substituição automática no MVP.

Uma execução reiniciada após interrupção não recupera autorização para HTTP apenas por possuir o mesmo Airflow run ID. Se houver conclusão íntegra, pode verificar/reproduzir o resultado. Nos demais casos, aplica-se recuperação conservadora.

Dependências:

- namespace realmente compartilhado entre produtores;
- semântica de publicação exclusiva suportada pelo filesystem;
- visibilidade consistente;
- permissões adequadas;
- preservação dos registros.

Sincronizar o arquivo não comprova durabilidade integral do diretório ou resistência a falha física. O comportamento em volume Windows/Docker permanece uma dependência a validar posteriormente.

## 8. Compatibilidade com identidades e contratos existentes

| Artefato | Relação proposta |
|---|---|
| Manifesto | Preservar contrato e preencher `scheduled_slot`, já permitido |
| Batch | Um batch proprietário por slot admitido |
| Run meteorológico | Uma identidade por cidade dentro do batch |
| Attempt | Identidade própria para cada tentativa HTTP |
| `started.json` | Segunda barreira de execução, por batch |
| `completed.json` | Conclusão técnica verificável, inclusive quando parcial |
| Claim | Novo controle externo aos contratos meteorológicos |
| Avaliação operacional | Novo registro externo, ligado ao batch e à política |

Uma run Airflow posterior que encontre conclusão íntegra deverá referenciar o manifesto original. Não deve reconstruí-lo usando seu próprio contexto e apresentá-lo como o mesmo artefato.

Manifestos históricos com `scheduled_slot=None` permanecem válidos para seus contratos originais. Não serão associados retroativamente a slots por inferência.

Nenhum estado Raw/run/batch será renomeado ou promovido pela avaliação operacional.

## 9. C02 — Admissão, início e prontidão

| Marco | Definição proposta |
|---|---|
| Slot nominal | D às 13h45 |
| Admissão | Aprovação preliminar para disputar o slot |
| Reivindicação | Aquisição exclusiva da propriedade |
| Início efetivo | Entrada na extração imediatamente antes do primeiro transporte |
| Conclusão técnica | Artefatos e conclusão persistidos segundo o contrato |
| Reconciliação | Verificação de referências, hashes, identidades e resultados |
| Prontidão operacional | Avaliação concluída e recibo persistido |
| Elegibilidade logística | Todos os critérios operacionais atendidos |
| Disponibilização | Entrega ao consumidor; não implementada neste escopo |

Fronteiras propostas:

| Horário local | Regra |
|---|---|
| Antes de 13h45 | Não admitir antecipação |
| 13h45 até 14h00 inclusive | Admitir, se demais condições forem satisfeitas |
| Após 14h00 | Não iniciar nova rodada |
| Até 14h15 inclusive | Concluir a prontidão operacional |
| Após 14h15 | Resultado tardio para a decisão diária |
| 14h30 | Referência pretendida de consumo |

A verificação inicial não concede autorização duradoura. Deve haver revalidação junto ao transporte; atraso em fila pode invalidar a execução.

O limite de início vale para a rodada. As tentativas HTTP internas continuam distintas e seguem sua política própria.

A definição instrumental do início deverá posicionar a verificação no ponto mais próximo possível do transporte. Isso não constitui garantia de precisão física absoluta do relógio ou do envio de pacotes.

Uma rodada iniciada antes do limite pode terminar depois do corte. Nesse caso, os artefatos são preservados e a avaliação registra atraso.

Recomendação: permitir conclusão dentro dos limites técnicos existentes, sem encerramento forçado às 14h15. Se o negócio exigir parada absoluta, será necessário outro desenho.

## 10. Avaliação operacional independente

Aptidão operacional exige cumulativamente:

1. Slot e D corretos.
2. Propriedade e referências coerentes.
3. Integridade de manifesto, início, conclusão, relatórios e Raw.
4. Cinco localidades aprovadas.
5. Cobertura integral da janela.
6. Zero nulos nas variáveis exigidas.
7. Prontidão até 14h15.
8. Frescor aprovado no consumo.

O recibo proposto deverá registrar:

- slot e batch;
- versão da política;
- referências e hashes verificados;
- instantes de avaliação;
- resultado e motivos;
- `collected_at` por cidade;
- idades calculadas e referência de consumo.

Não utilizar mtime de arquivo como prova de prontidão. O registro deve ser produzido no fluxo real de avaliação, sem retrodatação.

O instante persistido dentro do documento é anterior à confirmação final de sua gravação. Portanto, a implementação futura deverá verificar também o relógio após a persistência: conclusão da escrita depois do corte torna a avaliação tardia. Um timestamp interno anterior não basta para aceitar o resultado.

Falha ao persistir ou confirmar a avaliação significa **prontidão não comprovada**.

A aptidão para as 14h30 é provisória até o consumo: integridade e idade devem ser reavaliadas se a disponibilização ocorrer depois.

## 11. Cobertura, nulos e qualidade

Proposta de aceite:

- exatamente as localidades aprovadas;
- conjunto completo de horários de `[D 16h, D+2 00h)`;
- sem duplicações ou horários externos;
- 32 horários por cidade e 160 registros na janela vigente;
- zero nulos nas variáveis meteorológicas exigidas;
- consistência entre payload, relatórios, manifesto e conclusão.

A função atual de cobertura reduz os horários exigíveis conforme `collected_at`. A avaliação diária não deverá usar essa redução para aceitar uma coleta tardia com janela menor.

Se uma alteração de regras de timezone produzir janela diferente da duração contratual esperada, bloquear para revisão.

`success`, `validated_with_nulls` e conclusão técnica não comprovam aptidão logística. Um batch com nulos pode permanecer tecnicamente `success` e ser operacionalmente inelegível.

## 12. C03 — Frescor e recomendação revisada

Define-se idade da coleta por cidade:

`idade_i(T) = T − collected_at_i`

A idade consolidada é a maior idade individual. Médias não podem ocultar uma cidade antiga.

Essa medida informa quando a resposta foi obtida. Não informa quando o modelo meteorológico foi atualizado ou a qualidade preditiva da previsão.

Exemplos sintéticos:

| Situação | Instantes de coleta | Idade no consumo | Interpretação |
|---|---|---|---|
| Rodada nominal | 13h45:10 a 13h46 | Às 14h30: 44min50s a 44min | Compatível com 45 minutos |
| Rodada atrasada | 13h59 a 14h02 | Às 14h30: 31 a 28 minutos | Mais fresca, mas ainda depende de prontidão até 14h15 |
| Cinco cidades em momentos distintos | 13h46, 13h48, 13h51, 13h55 e 14h01 | 44, 42, 39, 35 e 29 minutos | Usar 44 minutos, não a média |
| Replay às 14h10 | Coleta original às 13h46 | Às 14h30: 44 minutos | Replay não renova `collected_at` |
| Disponibilização atrasada | Coleta às 13h46; consumo 14h40 | 54 minutos | Falha com 45; pode passar com 60 |
| Uma cidade muito antiga | Uma às 13h20; demais às 13h50 | Às 14h30: pior idade de 70 minutos | Rejeição por frescor; origem anterior ao slot também exige rejeição/coerência |
| Consumo muito atrasado | Coleta às 13h46; consumo 14h47 | 61 minutos | Rejeição com limite de 60 |

Uma cidade com coleta anterior ao slot não é normal em um novo batch diário conforme o protocolo. O exemplo caracteriza uma anomalia ou candidato inadequado; não autoriza misturar resultados.

Comparação:

| Limite | Benefício | Limitação |
|---|---|---|
| 45 minutos | Alinha-se ao intervalo nominal 13h45–14h30 | Quase nenhuma margem para consumo atrasado |
| 60 minutos | Admite até 15 minutos adicionais em relação ao intervalo nominal | Aceita coleta mais antiga; exige ratificação de negócio |
| 90 minutos | Maior tolerância | Enfraquece o objetivo de atualização próxima da decisão |

**Recomendação revisada:** manter 45 minutos como referência nominal e propor **60 minutos inclusive como limite máximo no instante efetivo de consumo**, usando a pior cidade.

Justificativa: a coleta das 13h45 já precede o consumo em 45 minutos. Um limite rígido igual a esse intervalo pode rejeitar dados por pequeno atraso de disponibilização, mesmo quando a coleta e a prontidão cumpriram seus marcos. A margem proposta trata atraso de consumo; não relaxa início até 14h00 ou prontidão até 14h15.

Os 60 minutos são uma escolha operacional candidata, não uma conclusão sobre precisão meteorológica. Nem 45 nem 60 minutos constituem SLA aprovado.

Rejeitar idade negativa, timestamp ausente ou sem timezone. Registrar também a dispersão entre cidades, inicialmente sem inventar um novo limite obrigatório para ela.

## 13. Retomada, indisponibilidade e fallback

Na retomada do scheduler:

- resolver o candidato conforme timetable e histórico;
- preservar seu slot/D;
- admitir somente se estiver na janela temporal;
- bloquear coleta de slot vencido;
- verificar resultado existente sem novo HTTP;
- não recuperar automaticamente dias perdidos.

Antes das 13h45, um eventual candidato do dia anterior continua vencido. Sua rejeição não deve reservar ou invalidar o slot futuro do dia atual.

O MVP não fará substituição automática por:

- batch de D−1;
- mistura de cidades de batches diferentes;
- resultado parcial;
- resultado com integridade não comprovada.

A indisponibilidade deve informar ciclo, slot, motivo, batch quando conhecido e instante da avaliação.

A ausência de resultado exige detecção independente na futura camada de consumo/monitoramento. Uma DAG parada não consegue garantir que emitirá seu próprio aviso. Essa integração permanece fora deste escopo.

## 14. Estratégia futura de testes offline — T01–T20

Todos os cenários abaixo são especificações, não testes executados.

| ID | Cenário | Critério de aceite |
|---|---|---|
| T01 | Duas timetables | Slot/D e semântica dos intervalos corretos |
| T02 | Retomada com/sem histórico | Candidatos caracterizados; vencidos sem HTTP |
| T03 | Fronteiras 13h45/14h00 | Inclusão/exclusão exatas |
| T04 | Atraso entre preparação e transporte | Revalidação bloqueia início vencido |
| T05 | Viradas de dia, mês e ano | D estável |
| T06 | Fuso ausente/contexto inválido | Bloqueio anterior à coleta |
| T07 | Disputa entre processos | Um proprietário e nenhuma coleta pelo perdedor |
| T08 | Airflow manual, agendado e CLI no mesmo slot | Mesma chave e mesma proteção |
| T09 | Interrupção em torno do claim/manifesto | Sem tomada automática; identidades preservadas |
| T10 | `started` sem conclusão | Bloqueio conservador |
| T11 | Replay íntegro | Zero HTTP adicional; IDs, bytes e tempos preservados |
| T12 | Prontidão na fronteira 14h15 | Persistência confirmada no prazo ou classificação tardia |
| T13 | Resposta pontual, reconciliação tardia | Inelegível |
| T14 | Limites de frescor | Casos de 45/60 minutos e idade negativa, conforme política ratificada |
| T15 | Cidade mais antiga e consumo atrasado | Pior idade prevalece |
| T16 | Nulos, parcialidade e corrupção | Nenhuma promoção de aptidão |
| T17 | Fallback incompatível | Rejeição explícita |
| T18 | Falha de filesystem/registro | Bloqueio sem mecanismo alternativo inseguro |
| T19 | Política/configuração alterada | Conflito não libera segunda rodada |
| T20 | Resultado ausente | Avaliação de indisponibilidade; silêncio não significa sucesso |

T08 deverá incluir inventário estático dos pontos de entrada. Enquanto houver produtor suportado capaz de contornar o protocolo, não haverá aceite de abrangência global.

Condições futuras:

- relógio controlado;
- rede desativada;
- diretórios temporários;
- subprocessos coordenados por eventos;
- nenhuma task, DAG run ou serviço operacional;
- dependências já aprovadas;
- evidências por cenário, hashes e códigos de saída.

A simulação da timetable deve chamar funções de cálculo, sem executar o scheduler. Testes em diretório temporário não comprovam automaticamente as garantias do volume operacional.

## 15. Impactos futuros em arquivos e contratos

| Componente | Impacto previsto |
|---|---|
| DAG | Contexto manual/agendado e integração temporal; cron em gate separado |
| Interface | Controle de slot e revalidação |
| Novo módulo temporal | Resolução e avaliação pura |
| Novo módulo de slot | Claim, conflito e inspeção |
| Manifesto | Reutilização de `scheduled_slot`; preservação histórica |
| Extrator/CLI | Integração dos pontos de entrada suportados |
| Persistência | Eventual diferenciação explícita entre criação e existência |
| Testes | Cenários T01–T20 |
| Documentação | Política, evidências e recuperação |

Os nomes e assinaturas dos novos módulos deverão constar de uma futura proposta de implementação.

Raw/run/batch permanecem inalterados. Claim e avaliação operacional são formatos novos de controle e exigem aprovação própria antes do desenvolvimento.

## 16. Critérios de aceite e rollback

Aceite futuro exige:

- decisões pendentes ratificadas;
- cobertura dos participantes declarados;
- um proprietário por slot nos cenários concorrentes;
- nenhuma coleta após reprovação temporal;
- replay sem renovação de frescor;
- ausência de promoção de parcialidade ou nulos;
- prontidão distinta de conclusão técnica;
- preservação das evidências;
- limites e falhas do filesystem documentados;
- nenhum cenário crítico omitido ou tratado como aprovado por ausência de execução.

Rollback futuro:

1. Conter produtores antes de retornar a código que desconhece slots.
2. Reverter somente commits autorizados.
3. Preservar claims, manifestos, incidentes e resultados.
4. Não apagar marcas nem criar identidades para contornar bloqueios.
5. Não usar `clear` como recuperação.
6. Tratar runs já ativas em procedimento próprio, quando houver autorização operacional.

A reversão de código não desfaz chamadas HTTP ou artefatos já produzidos.

## 17. Riscos e decisões centrais pendentes

| Decisão | Recomendação |
|---|---|
| Timetable | Intervalo diário explícito |
| Horários | Ratificar 13h45, 14h00, 14h15 e 14h30 |
| Abrangência | Todos os pontos de entrada suportados da coleta diária |
| Claim | Imutável e exclusivo em filesystem compartilhado |
| Recuperação | Sem expiração/tomada automática |
| Corte | Prontidão, sem parada forçada |
| Qualidade | Cobertura integral e zero nulos |
| Frescor | 45 minutos nominal; máximo candidato de 60 no consumo |
| Fallback | Indisponibilidade explícita |
| Novos controles | Aprovar schemas de claim e avaliação antes de implementar |

Riscos ainda não resolvidos:

- garantias reais do volume Windows/Docker;
- durabilidade perante falha física;
- processos externos ao protocolo;
- relógios incorretos ou divergentes;
- latência de persistência no corte;
- indisponibilidade do próprio monitoramento;
- diferença entre idade de coleta e atualização meteorológica;
- comportamento operacional do scheduler ainda não ensaiado.

**Estado desta versão:** especificação proposta para revisão. Nenhuma implementação, teste ou ativação operacional é autorizada por este documento.

**P09-T02 e passo 09 permanecem NÃO VALIDADOS.**
