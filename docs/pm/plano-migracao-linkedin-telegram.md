# Plano — levar a audiência do LinkedIn para o Telegram

**PM:** Hermes · **Data:** 22/10/2026 · **Status:** v1 pronto para executar
**Objetivo:** transformar os seguidores do LinkedIn (e a rede do Wouerner) em **inscritos do canal @vagas_php**, onde o produto constrói audiência própria.
**Metas:** 50 inscritos em 30 dias · **200 em 90 dias**.

---

## 1. Por que o Telegram (a proposta de valor)

A pessoa não troca o feed pelo canal à toa. O que ela ganha:

| No feed do LinkedIn | No canal do Telegram |
|---|---|
| Algoritmo decide o que você vê | **Tudo chega** — vaga nova em tempo real |
| Vaga envelhece e some | Resumo semanal com o panorama |
| Não tem histórico organizado | As vagas ficam lá, com link |
| Ruído de todo tipo | Só vaga de PHP |

O argumento central: **o canal entrega o que o feed não entrega — previsibilidade.** O resumo de segunda é o motivo de voltar.

---

## 2. O funil

```
post do LinkedIn (9h, com CTA) ──┐
comentários em posts de vagas  ──┤
mensagem direta                 ──┼──▶ clica em t.me/vagas_php ──▶ entra no canal
bio do perfil                   ──┤        │
site / README / e-mail          ──┘        ▼
                              recebe o resumo de segunda ◀── volta sempre
```

O CTA já está no texto do post do LinkedIn desde 22/10.

---

## 3. Estratégia LinkedIn → Telegram

### Peças e quando usar

| # | Peça | Frequência | Esforço | Conversão |
|---|---|---|---|---|
| 1 | **CTA fixo no post diário** | todo dia (9h) | zero (já feito) | baixa, constante |
| 2 | **Post de anúncio fixado** | 1 vez + repost mensal | S | média |
| 3 | **Comentário com dado** em posts de vagas PHP | 3–5 por semana | M | média-alta |
| 4 | **Mensagem direta** personalizada | 10–20 pessoas na semana 1 | M | **alta** |
| 5 | **Link na bio** do perfil | 1 vez | S | baixa |
| 6 | **Artigo/carrossel** "por que um canal de vagas" | 1 vez no mês 2 | M | média |
| 7 | **Post cruzado do resumo** | toda segunda | S | baixa |

### Regras (não negociáveis)

- **Valor primeiro, link depois.** No comentário, traga um dado do resumo ("Laravel foi 41% das vagas PHP abertas essa semana") — o link vem no fim.
- **Mensagem direta é pessoal, não em massa.** 20 mensagens escritas uma a uma convertem mais que 200 iguais.
- **Nunca spam em grupo de terceiro.** Comentário útil em comunidade de vagas é aceitável; "entra no meu canal" solto não.
- **O canal é o destino, não o site.** O site é o respaldo; o canal é onde a pessoa fica.

---

## 4. SEO do canal no Telegram

**Feito (22/10):**

- **Título:** `Vagas PHP — Laravel, Symfony, WordPress`
- **Descrição:** `Vagas de PHP, Laravel, Symfony e WordPress publicadas nas últimas 72h. Alertas em tempo real e resumo semanal às segundas, 10h. Curadoria e regras abertas: vagasphp.wouerner.dev`
- **Username:** `@vagas_php` (público) → `t.me/vagas_php`

**O que falta:**

- [ ] **Foto do canal** — logo/elefante (BotFather ou `setChatPhoto`); canal sem foto perde cliques nos resultados de busca
- [ ] **Backlinks** — `t.me/vagas_php` na home do site, no README do GitHub, no perfil do LinkedIn e em todo e-mail
- [ ] **Mensagens com palavra-chave** — os posts já trazem (título da vaga + stack + "Remoto"), que é o que o índice lê
- [ ] **Link canônico no site** — uma seção fixa "Canal no Telegram" com o link, para o Google associar os dois

**Nota:** canais públicos do Telegram são indexáveis pelo Google. O que aparece no resultado é o título + descrição + as mensagens — por isso os dois campos foram preenchidos com palavras-chave.

---

## 5. Cronograma

### Semana 0 — 23/10 a 25/10 (sex a dom)

- [ ] Fixar a **mensagem de boas-vindas** no canal (texto abaixo)
- [ ] Publicar o **post de anúncio** no LinkedIn e **fixar** no perfil
- [ ] Adicionar `t.me/vagas_php` na **bio do LinkedIn**
- [ ] Adicionar o link no **README do GitHub** (já está) e confirmar o banner na **home do site** (no ar desde 22/10)
- [ ] Definir a **foto do canal**

**Saída da semana:** tudo pronto antes do primeiro resumo.

### Semana 1 — 26/10 (segunda)

- [ ] 1º resumo semanal no canal (10h, automático)
- [ ] Post do LinkedIn do dia com o CTA (9h, automático)
- [ ] **10 mensagens diretas** personalizadas (devs PHP e RHs que você conhece)
- [ ] Comentar em 3 posts de vagas PHP com dado + link

**Meta:** 30 inscritos.

### Semana 2 — 02/11

- [ ] 2º resumo (automático)
- [ ] Comentar em 5 posts
- [ ] 10 mensagens diretas (segunda leva)

**Meta:** 60 inscritos.

### Semana 3 — 09/11

- [ ] 3º resumo
- [ ] Pedir a 2 inscritos que compartilhem o resumo
- [ ] 1 comunidade de PHP (Discord/Slack/Reddit) com o resumo da semana

**Meta:** 100 inscritos.

### Semana 4 — 16/11

- [ ] 4º resumo
- [ ] Enquete no canal: "qual stack você quer no resumo?"
- [ ] Revisar de onde vieram os inscritos e dobrar a aposta

**Meta:** 150 inscritos.

### Meses 2 e 3

- Resumo semanal toda segunda + CTA diário (automáticos)
- 1 artigo/carrossel por mês explicando o projeto
- 2 comunidades por semana
- **Meta:** 200 inscritos e sinais de retenção (reacoes e comentarios)

---

## 6. Métricas

| Métrica | Como medir | Hoje | 30 dias | 90 dias |
|---|---|---|---|---|
| Inscritos no canal | `getChatMembersCount` | 2 | 50 | 200 |
| Resumos enviados | cron executado | 0 | 4/4 | 12/12 |
| Alertas enviados | logs do cron | — | 100% | 100% |
| Origem dos inscritos | pergunta no convite / link dedicado | — | top 2 | top 2 |
| Reações no canal | contagem semanal | 0 | 5 | 20 |

---

## 7. Textos prontos

### 7.1 Post de anúncio no LinkedIn

```
🐘 Lancei o canal Vagas PHP no Telegram

Todo dia o site lista vagas de PHP, Laravel e Symfony publicadas nas últimas 72h. Mas o feed não avisa quando sai vaga nova — e a vaga envelhece.

O canal resolve isso:

• 🔔 alerta de vaga nova em tempo real
• 📊 resumo semanal toda segunda às 10h — quantas vagas abriram, quantas remotas, de quais empresas

É gratuito e a curadoria é aberta: as regras de filtro ficam públicas no site.

Entra: t.me/vagas_php
```

### 7.2 Mensagem direta (personalize o nome e o gancho)

```
Oi [nome], tudo bem?

Montei um canal no Telegram com vagas de PHP — Laravel, Symfony, WordPress — atualizado em tempo real, mais um resumo semanal às segundas com o panorama do mercado (quantas vagas abriram, quantas remotas, de quais empresas).

Se fizer sentido pra você, o convite: t.me/vagas_php
```

### 7.3 Comentário em post de vaga PHP

```
Boa — se quiser acompanhar o panorama, o canal Vagas PHP resume toda semana quantas vagas de PHP abrem e de quais empresas: t.me/vagas_php
```

### 7.4 Mensagem de boas-vindas do canal (fixar)

```
👋 Bem-vindo ao Vagas PHP

O que você recebe aqui:

• 🔔 alerta de vaga nova em tempo real — PHP, Laravel, Symfony, WordPress
• 📊 resumo semanal toda segunda às 10h — vagas abertas, remotas, empresas e stacks do período

A curadoria e as regras de filtro são abertas:
vagasphp.wouerner.dev/regras

Site com todas as vagas: vagasphp.wouerner.dev
```

---

## 8. Riscos

| Risco | Sintoma | Plano B |
|---|---|---|
| Canal parado assusta quem entra | 0 posts na semana | O resumo de segunda + o alerta horário garantem no mínimo 8 posts/semana |
| Mensagem direta vira spam | resposta ou bloqueio | Parar na hora; reduzir pra 10/semana |
| Crescimento lento no LinkedIn | < 5 inscritos/semana | Dobrar mensagens diretas; testar carrossel |
| Pessoal confunde o canal com outro | pergunta recorrente | O título e a descrição do canal já deixam claro o que é |

---

## 9. Futuro (fora do escopo atual)

**Decisão (22/10/2026):** a mensagem direta no LinkedIn **não entra agora**. Fica registrada aqui para quando fizer sentido.

| Peça | Por que ficou de fora | Quando revisar |
|---|---|---|
| **DM no LinkedIn** | É a maior alavanca de conversão e a única 100% manual. O bot não tem ferramenta de DM — implementar é código novo (abrir a conversa, achar o contato, escrever). | Quando o canal passar de ~50 inscritos (aí a DM deixa de ser "convite frio" e vira follow-up) |
| **Comentários no feed** | Cortado: o feed do Wouerner não tem vagas de PHP (46 posts lidos, 2 menções, 0 vagas). O script `~/.hermes/linkedin/promote.py` existe mas não tem material. | Só se o feed mudar |
| **Comentários em comunidades de PHP** (Discord, Slack, Reddit r/brdev) | Fora do LinkedIn; não há bot pra isso. Ação manual ou projeto novo. | Sem data — depende de tração |
| **Repost mensal do anúncio** | Dá pra automatizar com `create_post` (o texto está no plano). | Mês 2 |
| **Newsletter paga (M4)** | O resumo semanal é o embrião: mesma audiência, mesmo conteúdo, slot de patrocínio. | Quando o canal tiver retenção (reacoes/comentarios) |
| **Anúncio pago** | Só com tração e métrica de conversão. | Meses 4+ |

**O que não muda:** o funil continua sendo **anúncio → canal → resumo semanal → volta**. Enquanto a DM não existe, a conversão depende do **convite pessoal manual** — por isso ele é a peça número 1 da semana 1.

---

*Os itens de código estão no plano principal (`plano-monetizacao-comunidade.md`) e no de 30 dias. O cronograma de divulgação está em `cronograma-divulgacao-telegram.md`.*
