# Níveis de confiança — empresa e tech recruiter

**PM:** Hermes · **Data:** 03/11/2026 · **Status:** rascunho validado em produção
**Objetivo:** classificar internamente empresas e tech recruiters em três níveis antes de qualquer ban público: **confiante**, **neutro** e **desconfiado**.

## 1. Problema

Hoje o produto já distingue quem contrata de quem só divulga vaga, mas ainda não tem uma camada simples de confiança para separar:

- empresa/recrutador com histórico confiável;
- fonte sem evidência suficiente;
- fonte que merece revisão antes de virar ban.

Sem isso, o site só tem dois extremos: entra ou sai. Falta um meio-termo para revisão interna.

## 2. Proposta

Criar uma classificação **interna** por entidade, não por vaga:

- **confiante** — fonte com histórico limpo e repetido de vagas reais;
- **neutro** — sem sinal forte o bastante para subir ou descer;
- **desconfiado** — fonte com sinais de risco, mas ainda sem ban.

### Entidades

- **Empresa**: chave por `company_key`.
- **Tech recruiter**: chave por `author_url` / identidade do perfil.

### Regra de ouro

**Desconfiado não é ban.**

O estado só sinaliza que a fonte precisa de mais evidência, revisão manual ou futura votação da comunidade.

## 3. Critérios práticos

### Confiante
Sobe quando houver combinação de:

- empresa clara e recorrente;
- vagas consistentes da mesma fonte;
- pouco ruído de duplicação ou republicação;
- pouca ambiguidade entre fonte e contratante.

### Neutro
É o padrão.

Entra aqui quando ainda não existe base suficiente para julgar, ou quando os sinais se anulam.

### Desconfiado
Entra aqui quando houver sinais como:

- republicação recorrente da mesma vaga em massa;
- empresa/recrutador com comportamento de agregador;
- descrição ou perfil com sinais fracos de contratação misturados com divulgação;
- fonte com muito volume e pouca clareza de contratação;
- divergência frequente entre empresa, autor e contexto.

## 4. Uso no produto

Fase 1 — **interno apenas**

- a classificação aparece só para manutenção e moderação;
- não muda o feed público ainda;
- não bane automaticamente ninguém.

Fase 2 — **revisão e comunidade**

- a comunidade vota na classificação;
- o estado manual vira base para decisão mais aberta;
- o ban só vem depois de regra clara e evidência suficiente.

## 5. Validação em produção

A base atual já mostra candidatos claros para essa camada:

### Empresas com volume suficiente para observação

Do `/api/companies?limit=20` em produção:

- **BairesDev** — 31 vagas
- **Digisystem** — 10 vagas
- **Curotec** — 5 vagas
- **Bionic Talent** — 4 vagas
- **Estuda.com** — 4 vagas
- **NOUS LATAM** — 3 vagas
- **New Rizon** — 3 vagas
- **First Decision** — 3 vagas

### Tech recruiters com volume suficiente para observação

Do `/api/recruiters?limit=20` em produção:

- **Gabriely Avila** — 3 vagas
- **Carla Farias** — 2 vagas
- **Ana Carolina Fernandes** — 2 vagas
- **Jordana Souza** — 2 vagas

### Leitura de PM

A produção já tem volume suficiente para uma classificação manual inicial sem inventar regra nova:

- empresas com burst claro, como a BairesDev, viram casos de teste naturais;
- recruiters com múltiplas vagas viram o primeiro grupo de observação;
- o sistema pode começar com poucos rótulos e crescer com voto da comunidade.

## 6. Implementação sugerida

### Modelo mínimo

- `trust_level` com valores: `confiante`, `neutro`, `desconfiado`.
- `trust_reason` para justificar a marcação.
- `trust_updated_at` para auditoria.
- `trust_source` para saber se veio de moderação interna ou voto futuro.

### Comportamento inicial

- default: `neutro`;
- etiqueta manual para casos óbvios;
- nenhuma exclusão automática só por nível.

### Evolução futura

- página interna para revisar fontes;
- página pública para votação;
- contagem de votos por fonte;
- ban só depois de limiar definido.

## 7. Critérios de aceite

- existe um rótulo interno para empresa e recruiter;
- o rótulo tem os três estados definidos;
- `desconfiado` não remove vaga sozinho;
- o histórico da mudança fica registrado;
- a classificação pode ser preenchida manualmente agora;
- a futura votação comunitária cabe no mesmo modelo.

## 8. Backlog

- `VBP-013` — Níveis de confiança para empresa e tech recruiter.
- Status: pronto para implementação.
