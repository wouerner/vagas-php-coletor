# Cronograma de divulgação — canal @vagas_php

**PM:** Hermes · **Data:** 22/10/2026 · **Status:** v1
**Objetivo:** levar o canal do Telegram de 2 inscritos a uma base que justifique a comunidade (meta de 90 dias: **200 inscritos**).
**Peça central:** o **resumo semanal** (imagem do dashboard + texto do LinkedIn), toda **segunda às 10h (Brasília)** — é o motivo de as pessoas entrarem e voltarem.

---

## 1. Premissas

- O canal é novo (2 inscritos) e não tem conteúdo próprio além do resumo semanal.
- O resumo semanal é o **produto mínimo** de valor: mostra números reais do mercado PHP e linka o site.
- Sem CTA, nada cresce. Toda peça de divulgação termina num convite para o canal.
- Divulgação em comunidade de terceiros só com **valor primeiro** — pedir para entrar em grupo de vagas sem contribuir queima credibilidade.

---

## 2. Canais e prioridade

| # | Canal | Ação | Prioridade | Esforço |
|---|---|---|---|---|
| 1 | **Post do LinkedIn** (9h diário) | acrescentar uma linha fixa com o convite para o canal | **P0** — é onde já há audiência | S |
| 2 | **Site** (`vagasphp.wouerner.dev`) | banner/CTA na home: "Receba o resumo semanal no Telegram" | **P0** | M |
| 3 | **Perfil do LinkedIn** | link do canal na bio/seção de contato | P1 | S |
| 4 | **Rede pessoal** | convite direto a 10–20 devs PHP e RHs que você conhece | **P1** — maior conversão | S |
| 5 | **GitHub** (`vagas-php-coletor`) | badge e link do canal no README | P2 | S |
| 6 | **Comunidades PHP** (Discord, Slack, Reddit r/brdev, grupos de Telegram) | post com o resumo da semana, não só link | P2 | M |
| 7 | **Newsletter do site** (quando existir) | CTA no fim de cada edição | P3 | S |

---

## 3. Cronograma semana a semana

### Semana 0 — preparação (23/10 a 25/10, sex a dom)

- [ ] Criar o cron do resumo semanal (segunda 10h)
- [ ] Fixar no canal uma **mensagem de boas-vindas** com: o que é o canal, quando sai o resumo (segunda 10h) e o link do site
- [ ] Adicionar o CTA do canal ao **texto do post do LinkedIn** (`VAGAS_LINKEDIN_POST_SIGNATURE` ou linha própria)
- [ ] Adicionar o **CTA na home do site**
- [ ] Adicionar o link do canal ao **perfil do LinkedIn** e ao **README do GitHub**

**Meta da semana:** tudo pronto antes da primeira segunda — o resumo de 26/10 já sai com divulgação junto.

### Semana 1 — 26/10 (1º resumo)

- **Seg 26/10, 9h:** post do LinkedIn diário (já com o CTA do canal)
- **Seg 26/10, 10h:** **1º resumo semanal** no canal
- **Seg 26/10:** convite direto a **10 pessoas** (devs PHP e RHs que você conhece) — mensagem pessoal, não em massa
- **Ter 27/10:** publicar no LinkedIn um post falando do **resumo semanal** (o que ele mostra, por que acompanhar)

**Meta:** 30 inscritos.

### Semana 2 — 02/11

- **Seg 02/11, 10h:** 2º resumo semanal
- Postar em **1 comunidade PHP** (Discord/Slack/Reddit) com o resumo da semana — trazer o dado ("Laravel foi X% das vagas PHP abertas"), não só o link
- Comentar em posts de vagas PHP no LinkedIn com o resumo

**Meta:** 60 inscritos.

### Semana 3 — 09/11

- **Seg 09/11, 10h:** 3º resumo semanal
- Publicar **2 comunidades** (diferentes)
- Pedir a 2 pessoas que já estão no canal para **compartilhar** o resumo com a rede delas

**Meta:** 100 inscritos.

### Semana 4 — 16/11

- **Seg 16/11, 10h:** 4º resumo semanal
- Enquete no canal: "qual stack você quer ver no resumo?" — engaja e dá conteúdo para a próxima semana
- Revisar: quais canais trouxeram mais inscritos? Dobrar a aposta neles

**Meta:** 150 inscritos.

### Semanas 5–8 — 23/11 a 14/12

- Resumo semanal toda segunda (10h)
- 2 comunidades por semana
- 1 ação nova por semana: entrevista com RH, vaga em destaque com comentário, dado salarial, etc.
- **Meta do período:** 200 inscritos e os primeiros sinais de retenção (pessoas reagindo/comentando)

---

## 4. Métricas

| Métrica | Como medir | Meta 30d | Meta 90d |
|---|---|---|---|
| Inscritos no canal | `getChatMembersCount` | 60 | 200 |
| Resumo semanal enviado | cron executado | 4/4 semanas | 12/12 |
| Origem dos inscritos | UTM/link dedicado por canal | — | saber os 2 melhores |
| Reações/comentários no canal | contagem manual por semana | 5 | 20 |

---

## 5. Regras

- **Nunca despejar vagas avulsas** no canal — só o resumo de segunda. O canal é um resumo, não um feed.
- Toda peça de divulgação termina com o convite: `t.me/vagas_php`.
- Em comunidade de terceiro, **valor primeiro**: traga um dado do resumo, não só o link.
- Se um canal não trouxer inscritos em 2 semanas, corta e tenta outro.
- O resumo é o embrião da **newsletter paga (M4)** — manter a cadência é o que sustenta as duas coisas.

---

*Os itens de código (cron do resumo, CTA na home, CTA no LinkedIn) estão no backlog principal (`plano-monetizacao-comunidade.md`) e no plano de 30 dias.*
