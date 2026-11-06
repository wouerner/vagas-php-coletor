# Site Ruby separado do Vagas PHP

**PM:** Hermes · **Data:** 04/11/2026 · **Status:** rascunho v1
**Escopo:** criar um site público separado para Ruby, mantendo a regra de 72h e a mesma base multi-tenant.

---

## 1. Diagnóstico

A base já é multi-tenant.

- O coletor já suporta `VAGAS_TENANT=ruby`.
- O site já lê `VAGAS_TENANT` e filtra `jobs`, `runs` e `site_meta` por tenant.
- A regra de 72 horas já está no contrato do site e do coletor.

Ou seja: **não precisa criar um sistema novo**. Precisa separar a camada pública: marca, domínio, navegação e deploy.

---

## 2. Recomendação

**Fazer um segundo site com o mesmo código, mas com tenant Ruby e identidade própria.**

Isso evita duplicar filtro, coleta, API e manutenção. O que muda é:

- domínio
- branding
- textos da home
- fontes e temas exibidos
- lista de rota / nome público do produto

---

## 3. O que muda de fato

### Backend / dados
- `VAGAS_TENANT=ruby` no site Ruby.
- `collector-ruby` continua alimentando a mesma base, mas gravando no tenant Ruby.
- `openCount`, `dashboard`, `/api/jobs`, `/api/companies`, `/api/recruiters` passam a olhar só Ruby.
- mantém a janela de **72 horas**.

### Frontend / marca
- trocar `Vagas PHP` por `Vagas Ruby` em título, descrição, header e metadados.
- trocar ícone, og image e textos do Telegram/Instagram se houver canal próprio.
- manter a mesma estrutura de páginas.

### Infra
- adicionar um serviço/site Ruby no deploy.
- apontar um domínio separado para o Ruby.
- manter o PHP como produto principal atual.

---

## 4. Opções de arquitetura

### Opção A — mesmo código, dois deployments separados
**Recomendação.**

- `web` atual continua PHP.
- novo `web-ruby` aponta para `VAGAS_TENANT=ruby`.
- novo domínio: algo como `vagasruby.wouerner.dev`.

**Prós:** simples, barato, quase zero retrabalho.  
**Contras:** duas deploys para manter.

### Opção B — um site único com toggle de linguagem
- uma UI só, alternando PHP/Ruby.

**Prós:** menos infra.  
**Contras:** pior para marca, confunde usuário, mistura públicos.

**Recomendação:** Opção A.

---

## 5. Backlog

| ID | Prioridade | Esforço | Item | Aceitação |
|---|---|---|---|---|
| RUBY-001 | P0 | M | Criar identidade do site Ruby | título, descrição, header e footer sem PHP no branding |
| RUBY-002 | P0 | S | Subir deploy do site Ruby com `VAGAS_TENANT=ruby` | home, dashboard, empresas e vagas mostram só Ruby |
| RUBY-003 | P0 | S | Definir domínio do Ruby | domínio funcionando e apontando para o novo site |
| RUBY-004 | P1 | M | Ajustar textos e SEO do Ruby | metadados e Open Graph específicos para Ruby |
| RUBY-005 | P1 | S | Verificar dados do Ruby em produção | home mostra vagas recentes e `/api/jobs` retorna só Ruby |
| RUBY-006 | P1 | S | Revisar Telegram/CTA do Ruby | se existir canal próprio, manter o mesmo padrão curto e direto |

---

## 6. Métricas iniciais

- vagas abertas Ruby nas últimas 72h
- sessões na home Ruby
- cliques em vagas Ruby
- crescimento do canal/CTA Ruby, se existir

Baseline a medir antes de divulgar.

---

## 7. Riscos

| Risco | Sintoma | Plano B |
|---|---|---|
| Misturar Ruby com PHP no branding | visitante cai no site errado | separar domínio e assets logo na primeira entrega |
| Duplicar esforço operacional | dois sites viram duas bases | manter o mesmo código e a mesma infra multi-tenant |
| Poucas vagas Ruby | site parecer vazio | manter a janela de 72h e medir cobertura antes de divulgar |
| Confusão de SEO | Google indexar errado | revisar títulos, canonical e sitemap do novo site |

---

## 8. Decisões que você precisa tomar

1. Qual será o domínio do site Ruby?
2. O site Ruby vai ter **marca própria** ou só uma submarca do projeto atual?
3. Quer que eu implemente primeiro o **deploy Ruby** ou primeiro os **textos/branding**?
