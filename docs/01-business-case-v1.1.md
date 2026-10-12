# Business Case v1.1 — Logistics Weather Data Pipeline

**Cliente requisitante (fictício):** AuroraLog Transportes & Distribuição S.A.
**Empresa executora (fictícia):** Phoenix Data
**Consultor responsável:** Mr. João Caneca
**Referência:** PHD-AL-2026-001
**Data:** 11/10/2026
**Status:** Caso de negócio simulado, sujeito à validação fictícia de stakeholders
**Histórico:** v1.0 = definição independente; v1.1 = contextualização cliente-consultoria e vinculação ao discovery.

## 1. Resumo executivo

A AuroraLog Transportes & Distribuição S.A., organização fictícia de transporte e distribuição, solicitou à Phoenix Data um MVP de dados meteorológicos para apoiar a leitura antecipada de condições climáticas nas localidades atendidas. Mr. João Caneca foi designado consultor responsável pelo entendimento do negócio, formalização de requisitos e evolução técnica.

O problema é que o planejamento consulta fontes meteorológicas dispersas e não dispõe de histórico estruturado e auditável das previsões. A proposta é construir um pipeline local, reproduzível e de custo de infraestrutura zero que consulte a Open-Meteo, colete 24 períodos horários para cinco localidades, valide os dados, preserve versões de cada coleta e ofereça consultas que sinalizem **condições de atenção meteorológica**.

**A entrega não pretende estimar atrasos, impacto em SLAs ou economia financeira**, pois esses resultados exigiriam dados operacionais ainda fora do escopo.

## 2. Problema e oportunidade

**Problema de negócio:** baixa padronização e comparabilidade das previsões consultadas por Planejamento e Operações.
**Problema de dados:** ausência de ingestão, validação, persistência histórica e rastreabilidade sistemáticas.
**Oportunidade:** habilitar leitura consistente de localidade/hora e comparar previsões feitas em momentos distintos para melhorar a qualidade das conversas de planejamento.

**Pergunta de negócio:** Como antecipar condições meteorológicas potencialmente adversas de forma consistente e auditável, sem confundir previsão do tempo com previsão de atraso logístico?

## 3. Necessidades expressas no discovery simulado

1. Comparar cinco localidades em janela de 24 horas.
2. Visualizar os períodos previstos de maior precipitação e vento.
3. Identificar horas acima de limiares ajustáveis, claramente declarados.
4. Recuperar a versão consultada anteriormente e o momento da coleta.
5. Identificar coleta incompleta, atraso de atualização e falhas técnicas.

As entrevistas, perguntas, atas, matrizes e pendências estão registradas em `02-discovery-requisitos-escopo-v1.0.md`.

## 4. Objetivo e proposta

**Objetivo:** disponibilizar um produto de dados meteorológicos estruturado, confiável e rastreável para apoio a decisões humanas de planejamento preventivo.

**Cadeia de valor:** Open-Meteo → ingestão → validação/DQ → snapshots históricos + auditoria → consultas/indicadores → análise por Planejamento.

**Por que Engenharia de Dados:** o diferencial não é chamar uma API, mas construir confiabilidade, semântica temporal, idempotência, observabilidade, documentação e um contrato claro de publicação.

## 5. Escopo executivo do MVP

**Incluído:** cinco localidades, 24 passos horários, histórico por execução, modelagem temporal explícita, regras de qualidade, tratamento de falhas, consultas analíticas, execução local, testes, documentação e CI básico.

**Excluído:** integração TMS/GPS/ERP, modelagem causal de impacto meteorológico, predição de atrasos, alertas críticos de segurança, roteirização automática, produção 24/7 e recursos cloud pagos.

**Futuro possível:** enriquecer com viagens, ocorrências, entregas e observações meteorológicas para estimar exposição real e estudar eventual associação com desempenho logístico.

## 6. Stakeholders e responsabilidade

| Ator | Responsabilidade no cenário |
|---|---|
| Helena Duarte, Diretoria de Operações (fictícia) | Patrocínio e aceite de negócio |
| Camila Rocha, Planejamento / PO (fictícia) | Prioriza requisitos e valida consultas |
| Rafael Mendes, Transportes (fictício) | Contexto e regras operacionais |
| Bruno Tavares, Operações (fictício) | Cenários de uso e baseline |
| Beatriz Nascimento, TI (fictícia) | Critérios técnicos e restrições |
| Mr. João Caneca, Phoenix Data | Discovery, solução, qualidade, implementação e evidências |

## 7. Métricas de sucesso (metas, não resultados medidos)

| Dimensão | Alvo do MVP | Método de verificação |
|---|---|---|
| Cobertura | Cinco localidades | Configuração e execução |
| Completude temporal | 24 passos consecutivos por localidade em execução válida | Teste de cardinalidade/tempo |
| Idempotência | Nenhuma duplicata em replay do mesmo lote | Comparação antes/depois |
| Rastreabilidade | Registros publicados vinculados à coleta e à fonte | Consulta de auditoria |
| Transparência de falhas | Falhas explicitadas | Testes negativos |
| Consumo | Consultas respondem às perguntas prioritárias | Demonstração ao PO simulado |
| Custo | Nenhum recurso de infraestrutura pago exigido | Inventário técnico |

**Medição de valor futuro:** tempo para obter relatório consolidado (baseline a levantar). Não será declarado ROI na ausência de evidência.

## 8. Restrições, premissas e riscos

- Fonte: disponibilidade e contrato da Open-Meteo dependem de verificação e manutenção.
- Tempo: armazenar instantes em UTC e explicitar a janela horária e fuso de exibição.
- Semântica: valores ausentes não são zero; previsões não são observações.
- Operação: limites meteorológicos ainda precisam de validação por stakeholders fictícios.
- Infraestrutura: projeto local e gratuito, sem promessa de serviço produtivo contínuo.
- Escalabilidade: volumes e política de retenção serão validados na modelagem.

## 9. Gates do projeto

1. **Discovery:** problema, escopo, dúvidas e regras de negócio validados.
2. **Contrato de dados:** grão, esquema, horários, chaves e DQ acordados.
3. **Ingestão:** extração e testes com casos de falha.
4. **Persistência:** snapshots históricos e idempotência demonstrados.
5. **Analytics:** consultas e indicadores conferidos.
6. **Entrega:** reprodução local, logs, CI e documentação revisada.

## 10. Decisão solicitada

**Aprovar condicionalmente** o investimento de esforço no MVP, condicionado à identificação das cinco localidades, definição da frequência de coleta, limites de atenção e formato inicial de consumo. Essa é uma **decisão encenada** no contexto do estudo de caso, não aprovação concedida por empresa real.

## 11. Fontes internas e controle de versões

- `01-business-case-v1.1.md`: justificação e proposta de valor.
- `02-discovery-requisitos-escopo-v1.0.md`: simulações completas das cinco reuniões, requisitos, escopo mestre, rastreabilidade, aceites e pendências.
- `03-data-contract-v1.0.md`: próximo documento a preparar após decisões pendentes.

**Nota:** os resultados reais do repositório devem ser comprovados por testes/execuções; não devem ser confundidos com as falas simuladas.
