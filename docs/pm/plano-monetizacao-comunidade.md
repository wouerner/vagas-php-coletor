# Vagas PHP — Plano de Monetização e Comunidade

**PM:** Hermes · **Data:** 21/10/2026 · **Status:** rascunho v1 para validação
**Escopo:** como transformar o agregador curado de vagas PHP em produto com receita e comunidade.
**Fora de escopo:** reescrita da arquitetura; troca de stack.

---

## 1. Diagnóstico (o que a PM viu no produto real)

**Produção (Coolify):** `https://vagasphp.wouerner.dev` (Cloudflare → Traefik → serviço `web`)
**URL antiga:** `*.sslip.io` do Coolify — desativada, dá 404
**Dev local:** `http://localhost:8780` (containers `vagas-php-*`, MySQL 8.4) — **apenas ambiente de desenvolvimento**.

### 1.1 Produção está saudável

| Indicador | Valor (21/10/2026) |
|---|---|
| Vagas abertas (72 h) | **65** |
| Novas em 24 h / 24 h anteriores | 27 / 29 |
| Remotas | **35 (54%)** |
| Empresas distintas | 33 |
| Vagas com salário preenchido | **1 de 65** |
| Fontes com vaga aberta | 8 de 13 |
| Google Analytics | configurado (`G-47NEQJSJN8`) |

Distribuição das 65 vagas abertas:

- **Fonte:** LinkedIn 26, publicações 25, Gupy 5, Remotar 4, Catho 2, GitHub 1, Nerdin 1, Sólides 1 → **LinkedIn + posts = 78% da oferta** (concentração).
- **Modalidade:** Remoto 35, Híbrido 7, Presencial 8, sem classificação 15.
- **Senioridade:** Sênior 19, Especialista 8, Pleno 10, Júnior 2, Estágio 3, sem classificação 23 → **puxado para sênior**.
- **Stack:** PHP 26, PHP+Laravel 21, PHP+WordPress 4, demais variações pontuais.

### 1.2 Achados que importam

| Achado | Evidência | Impacto |
|---|---|---|
| **Sem domínio próprio** | URL é subdiretório `*.sslip.io` do Coolify | **Alto** — credibilidade fraca, SEO ruim, link de venda não passa profissionalismo |
| **Salário quase ausente** | 1 de 65 vagas com salário | **Médio** — limita o M1 (relatório de mercado); focar em volume/stack/senioridade/modalidade |
| **Concentração em LinkedIn + posts** | 51 de 65 vagas (78%) | **Médio** — se o LinkedIn bloquear, o produto cai junto |
| **5 fontes sem vaga aberta** | coodesh, inhire, programathor, recrutei, upvagas com `open: 0` | **Baixo** — coberturas caras que não estão rendendo; revisar termos/intervalo |
| **Repo não público** | `github.com/wouerner/vagas-php-coletor` → 404 | **Médio** — comunidade de código não existe |
| **Bot do LinkedIn quebrou no dev** | `linkedin_post.py:80`, seletor `#interop-outlet` → `TimeoutError` desde 16/out | **Médio** — confirmar se a produção também falha |
| **Coletor do dev local desligado** | `data/config.json` com 13/13 fontes `enabled: false` | **Baixo** — não afeta produção; higiene de dev |
| **Post sem URL na base** | vaga `post` "Estamos contratando na Leega!" com `url: null` | **Baixo** — post de divulgação sem link clicável; prejudica conversão |

**Leitura de PM:** a produção funciona e já tem 65 vagas curadas por dia — o que é mais difícil de construir está pronto. Os bloqueios de monetização são de **embalagem e alcance**: sem domínio próprio não há marca; sem salário na base o relatório de mercado perde a parte mais vendável; com 78% numa fonte só, a receita fica refém do LinkedIn. E sem captura de contato, cada visitante entra e sai sem deixar rastro.

---

## 2. Ativos e tese de valor

**O que é difícil de copiar:**

1. **Curadoria** (`vagas_php/php.py`, ~10 regras em `php.RULES`). Agregador comum lista tudo; este filtra PHP de verdade, recusa cargo não-dev, post de quem procura emprego e divulgação de grupos sem curadoria. Isso é o produto — não o scraper.
2. **Transparência** (página `/regras` gerada de `GET /api/rules`, com os padrões, quantos itens cada regra decidiu e o que foi descartado). Nenhum concorrente mostra as regras. É alavanca de confiança e de comunidade.
3. **Cobertura** — 13 fontes, incluindo portais onde a busca é proibida por robots.txt (Recrutei via sitemap) e posts de recrutadores no LinkedIn.
4. **Frescor** — janela de 72 h, com precisão de data por fonte documentada.
5. **Dados históricos** — 5.745 vagas com timestamp = série temporal de contratações PHP no Brasil.
6. **Canais prontos** — API JSON, servidor MCP, post diário com imagem de dashboard, Docker + Coolify.

**Tese:** ninguém paga por "lista de vagas". Paga-se por *confiança na lista* e por *alcance garantido*. Os dois ativos acima vendem isso.

---

## 3. Modelos de monetização

Avaliação em ICE (Impact × Confidence × Ease, 1–10) e receita potencial a 12 meses.

| # | Modelo | Como cobra | ICE | Receita 12m | Por quê |
|---|---|---|---|---|---|
| **M1** | **Relatórios de mercado para RHs** | relatório mensal/trimestral (quantas vagas PHP, stacks, senioridade, modalidade, salários citados, velocidade de fechamento) — PDF + planilha | **8.4** | Alta | Usa ativo que já existe (base histórica). Comprador tem budget. Nenhum concorrente publica isso. Começa com 1 cliente. |
| **M2** | **Vaga patrocinada / destaque** | empresa paga para fixar a vaga no topo + selo "Patrocinada" + repost nas redes | **8.0** | Alta | Modelo clássico e de maior intenção de compra. O comprador é o recrutador, não o candidato. |
| **M3** | **API/feed licenciado** | acesso à API MCP/JSON em volume, webhooks de vaga nova, histórico além de 72 h, SLA | **7.2** | Média-alta | Baixo custo marginal. Compradores: bootcamps, comunidades de nicho, ATS pequenos, sites irmãos. |
| **M4** | **Newsletter patrocinada** | slot de patrocínio em "Vagas PHP da Semana" (lista própria) | **6.5** | Média | Escala com a lista; lista escala com tráfego. Segundo passo natural do M2. |
| **M5** | **Assinatura para candidatos (freemium)** | alertas personalizados por stack/senioridade (push/WhatsApp/e-mail), "vagas exclusivas", score de match | **5.8** | Média | Precisa de conta e lista; entrada mais lenta. Bom para retenção, não para primeiro real. |
| **M6** | **Licenciamento do motor** | "Vagas <Niche>" branco para outros nichos (Python, .NET, dados) ou board interno de empresa | **5.5** | Alta (ticket) | Ticket alto, venda longa, ops pesada. Só depois de produto estabilizado. |
| **M7** | **Afiliados e anúncios** | cursos PHP, hosts, ferramentas, tools de AI | **4.5** | Baixa | Fácil de começar, ticket baixo. Receita de caixinha, não de negócio. |
| **M8** | **Marketplace de contratação** | fee por contratação concluída | **3.0** | Imprevisível | Ops de headhunting, ciclo longo, conflita com o agregador aberto. Só com tração grande. |

**Recomendação:** **M1 → M2 → M4**, com **M3** como produto técnico natural e **M5** como retenção. M6 e M8 ficam para 12+ meses.

**Sequência de caixa:** M1 é o primeiro real porque não exige mudar o produto — exige empacotar o que já existe. M2 exige pagamento e onboarding de empresa, mas é onde o volume está. M4 exige lista, que é o objetivo da fase de comunidade.

---

## 4. Comunidade

O flywheel tem 4 anéis, nesta ordem:

**Anel 1 — Canal próprio (semana 1–4)**
Grupo no **Telegram ou Discord** com bot que posta as vagas novas automaticamente (o coletor já tem os dados; falta o envio). É retenção, é gratuito, e transforma visitante de 1 vez em recorrente. O Discord tem melhor busca/SEO; o Telegram tem alcance no Brasil. **Recomendo Telegram primeiro pelo alcance, Discord em paralelo se aparecer tráfego de conteúdo.**

**Anel 2 — Lista e digest (mês 2–4)**
Newsletter semanal "Vagas PHP da semana": topo da semana + vaga em destaque + dado de mercado (ex.: "Laravel foi 41% das vagas PHP abertas essa semana"). Captura na home com um campo de e-mail. O dado de mercado é o que faz a newsletter ser diferente de um spam de link — e é o embrião do M1.

**Anel 3 — Conteúdo e SEO (mês 2–6)**
Blog curto com páginas de cauda longa: "vagas PHP remoto", "salário desenvolvedor Laravel 2026", "como conseguir vaga PHP júnior". Cada página é tráfego orgânico perpétuo. O `/regras` já é uma página de conteúdo que ninguém mais tem — promovê-la.

**Anel 4 — Open source e contribuição (mês 2–6)**
Publicar o repo. Adicionar `CONTRIBUTING.md`, templates de issue, e uma issue recrutando fontes novas ("adicionar fonte X"). O motor é reutilizável e a curadoria é feita pela comunidade. Isso atrai dev PHP, que é exatamente o público-alvo, e reduz seu custo de manutenção para quase zero. **Cuidado:** abrir o código não entrega a receita; é a alavanca de custo e de comunidade.

**Anéis 5 e 6 (12m+):** eventos mensais com RHs (roda de contratação), programa de embaixadores (devs que divulgam), e spin-offs de nicho (M6).

**Regra de PM:** comunidade não se compra, se cultiva com cadência. Toda peça de comunidade tem que terminar em um canal próprio (grupo, lista, repo). Se a peça só existe na timeline do LinkedIn, você aluga a audiência.

---

## 5. Roadmap

### Fase 0 — Embalagem e instrumentação (semana 1) · *pré-requisito de tudo*
- Registrar domínio próprio e apontar para o Coolify (hoje é `*.sslip.io`).
- Confirmar que as 13 fontes rendem em produção e medir o funil real no GA.
- Confirmar que o bot do LinkedIn está publicando em produção.
- Atacar a concentração: revisar fontes que não rendem e a captura de salário.

### Fase 1 — Produto saudável e audiência (semana 2–6)
- Site com vagas, post diário voltando, GA lendo.
- Grupo Telegram/Discord com bot de vagas novas.
- Captura de e-mail na home.
- Primeira newsletter manual.

### Fase 2 — Primeira receita (mês 2–4)
- Empacotar e vender **M1** (relatório de mercado) para 3–5 RHs/recrutadores.
- Implantar **M2** (vaga patrocinada): checkout Pix/cartão, selo, fixação no topo, repost.
- **M4** nasce junto: slot de patrocínio na newsletter.

### Fase 3 — Flywheel (mês 4–8)
- Publicar o repo + contribuição.
- Blog/SEO com páginas de cauda longa.
- **M3** (API licenciada) para bootcamps/comunidades.
- **M5** (alertas premium) como retenção.

### Fase 4 — Escala (mês 8–14)
- **M6** licenciamento do motor / spin-offs de nicho.
- Eventos, embaixadores.
- Avaliar **M8**.

---

## 6. Backlog

Prioridade: **P0** = destrava o produto · **P1** = primeira receita · **P2** = flywheel · **P3** = escala.
Esforço: **S** < 1 dia · **M** 1–3 dias · **L** 1–2 semanas.

### Épico 0 — Embalagem e instrumentação (P0)

| ID | História | Esforço | Aceite |
|---|---|---|---|
| `VBP-001` | Registrar domínio próprio e apontar para o Coolify com HTTPS | M | Site acessível por `https://<dominio>`; `*.sslip.io` redireciona |
| `VBP-002` | Auditoria das 13 fontes em produção (quais rendem, quais estão `open: 0`) | S | Relatório por fonte; decisão de ligar/ajustar/desligar cada uma |
| `VBP-003` | Confirmar publicação do post diário em produção | S | Post publicado no dia; histórico sem `TimeoutError` |
| `VBP-004` | Validar o funil no GA (origem, páginas, conversão de busca) | S | Dashboard de audiência com origem e páginas |
| `VBP-005` | Revisar termos/intervalo das fontes que não rendem (coodesh, inhire, programathor, recrutei, upvagas) | M | Cada fonte com vaga nova em 7 dias, ou justificativa para desligar |
| `VBP-006` | Captura de salário nas fontes que permitem (meta: > 20% das vagas) | M | % de vagas com salário medido; regra de extração documentada |
| `VBP-007` | Higiene do dev local (reativar coletor) | S | Dev com vagas; dev/prod emparelhados |

### Épico 1 — Canal próprio (P1)

| ID | História | Esforço | Aceite |
|---|---|---|---|
| `VBP-101` | Bot que envia vagas novas para grupo Telegram/Discord | M | Vaga nova aparece no grupo em < 15 min da coleta |
| `VBP-102` | Campo de captura de e-mail na home (LGPD, duplo opt-in) | M | E-mail grava; confirmação enviada |
| `VBP-103` | Newsletter semanal manual (vagas + dado de mercado) | S | Primeira edição enviada com métricas de abertura |
| `VBP-104` | Página "Sobre / Regras / Contato" como peça de conteúdo | S | Página publicada e linkada no rodapé |

### Épico 2 — Receita M1: relatório de mercado (P1)

| ID | História | Esforço | Aceite |
|---|---|---|---|
| `VBP-201` | Script que gera o relatório a partir do MySQL (vagas por stack, senioridade, modalidade, empresas, salários citados) | M | PDF + CSV gerados localmente |
| `VBP-202` | Definir preço e formato do relatório | S | Página/ficha de venda com preço e escopo |
| `VBP-203` | Prospeção de 20 RHs/recrutadores com o relatório | M | 20 contatos; meta de 3–5 conversas |
| `VBP-204` | Entregar relatório 1.0 e coletar feedback | S | Relatório entregue; NPS/feedback registrado |

### Épico 3 — Receita M2: vaga patrocinada (P1)

| ID | História | Esforço | Aceite |
|---|---|---|---|
| `VBP-301` | Modelo de dados: `sponsored`, `sponsor_name`, `sponsor_url`, `sponsor_until` | S | Migração aplicada; coluna no MySQL |
| `VBP-302` | Checkout (Pix/cartão) e confirmação de pagamento | M | Pagamento testado em sandbox e produção |
| `VBP-303` | Vaga patrocinada fixada no topo + selo "Patrocinada" | S | Ordem de exibição correta; selo visível |
| `VBP-304` | Repost automático da vaga patrocinada no canal próprio | S | Post sai no dia da contratação |
| `VBP-305` | Página de venda da vaga patrocinada com métricas (estimativa de alcance) | S | Página com preço, formato e estimativa |
| `VBP-306` | Contrato/termo simples de prestação de serviço | S | Documento assinado no primeiro pedido |

### Épico 4 — Receita M4: newsletter patrocinada (P2)

| ID | História | Esforço | Aceite |
|---|---|---|---|
| `VBP-401` | Slot de patrocínio no template da newsletter | S | Edição com slot renderizado |
| `VBP-402` | Página de mídia/Anuncie com audiência e preço | S | Link público com métricas |

### Épico 5 — Flywheel: open source e SEO (P2)

| ID | História | Esforço | Aceite |
|---|---|---|---|
| `VBP-501` | Tornar o repo público | S | `github.com/wouerner/vagas-php-coletor` acessível |
| `VBP-502` | `CONTRIBUTING.md` + templates de issue + `CODE_OF_CONDUCT` | S | Arquivos no repo |
| `VBP-503` | Issue recrutando fontes e melhorias de filtro | S | Issues abertas e rotuladas |
| `VBP-504` | Blog com 5 páginas de cauda longa (SEO) | M | Páginas indexadas; tráfego medido |
| `VBP-505` | `sitemap.xml` + meta tags sociais no site | S | Sitemap válido; preview de link correto |

### Épico 6 — Flywheel: API licenciada (P2)

| ID | História | Esforço | Aceite |
|---|---|---|---|
| `VBP-601` | Documentar a API/MCP pública (OpenAPI ou README) | M | Documento publicado |
| `VBP-602` | Camada de histórico além de 72 h para licenciados | M | Endpoint com janela estendida |
| `VBP-603` | Chave de acesso e limite de uso por cliente | M | Cliente testa com chave |

### Épico 7 — Retenção: assinatura de candidatos (P2)

| ID | História | Esforço | Aceite |
|---|---|---|---|
| `VBP-701` | Conta mínima (login por e-mail) | L | Login funciona; LGPD ok |
| `VBP-702` | Alertas por stack/senioridade via e-mail/Telegram | M | Alerta chega na vaga nova |
| `VBP-703` | Plano premium e checkout | M | Assinatura ativa |

### Épico 8 — Escala (P3)

| ID | História | Esforço | Aceite |
|---|---|---|---|
| `VBP-801` | Licenciamento branco do motor para outro nicho | L | 1 piloto pagante |
| `VBP-802` | Evento mensal com RHs | M | 1 edição realizada |
| `VBP-803` | Programa de embaixadores | M | 5 embaixadores ativos |

---

## 7. Métricas

**North star:** vagas curadas únicas entregues a um canal próprio por semana (visitante que voltou ou assinou algo).

**Cascata:**

- **Saúde:** vagas abertas no site (meta > 30/dia), fontes ativas (meta 13/13), post diário publicado (meta 7/7 dias)
- **Audiência:** visitas/mês (GA), novos e-mails/mês, assinantes do grupo, taxa de retenção semanal
- **Receita:** MRR, nº de clientes pagantes, ticket médio, custo de aquisição, tempo até o primeiro real
- **Comunidade:** contribuições externas no repo, issues fechadas pela comunidade, embaixadores ativos

**Metas de 90 dias:** site com vagas todos os dias · post diário 5/7 · 500 e-mails · 200 no grupo · 1 cliente M1 · 1 cliente M2.

---

## 8. Riscos

| Risco | Severidade | Mitigação |
|---|---|---|
| LinkedIn muda o HTML e quebra o bot de novo | Alta | Seletores isolados e testados a cada post; alerta quando o post falha (hoje falha em silêncio) |
| Termos de uso dos portais | Alta | Respeitar robots.txt e intervalos; já documentado no README; não repassar vagas como próprias |
| Automação viola ToU do LinkedIn | Alta | Conta dedicada; intervalos longos; `VAGAS_POSTS_ENABLED=false` em produção |
| Curadoria gera falso negativo e perde vaga boa | Média | `/regras` com contadores por regra; `dismiss_job` com auditoria; revisão mensal |
| LGPD com captura de e-mail | Média | Opt-in explícito, política de privacidade, exclusão sob pedido |
| Monetização antes de tráfego | Média | Roadmap já coloca receita na Fase 2; M1 não depende de tráfego |
| Open source entrega o motor e um concorrente copia | Baixa | Curadoria e dados são o ativo, não o código; licença pode reservar o nome |
| Marca hospedada em `*.sslip.io` | Média | Domínio próprio na Fase 0; sem isso, venda e SEO perdem credibilidade |
| Receita refém do LinkedIn (78% da oferta) | Média | Diversificar fontes (VBP-005); alerta de queda por fonte no dashboard |
| Salário ausente limita o relatório de mercado | Média | VBP-006 eleva a captura; relatório v1 foca volume/stack/senioridade |

---

## 9. Decisões que preciso de você

1. **Domínio** — hoje é `*.sslip.io` do Coolify. Você vai registrar um domínio próprio? Recomendo algo curto e memorável (ex.: `vagasphp.com.br`, ~R$ 40/ano). Sem isso, a venda e o SEO ficam amarrados.
2. **Prazo para o primeiro real** — 30, 60 ou 90 dias? Define se o M1 sai em paralelo com a Fase 0 ou depois.
3. **Open source agora ou depois?** Publicar o repo é barato e destrava a comunidade, mas expõe o motor antes da receita.
4. **Canal da comunidade** — Telegram (alcance no Brasil) ou Discord (busca e conteúdo)? Recomendo Telegram.
5. **Você tem um CNPJ/meio de recebimento?** M1 e M2 precisam emitir nota ou receber como pessoa física.
6. **Quem é o comprador do M1?** Você tem contato com RHs/recrutadores hoje, ou a prospecção seria fria?
7. **Quem paga a infra?** Coolify + MySQL hoje têm custo? Isso define a margem do M2.

---

*Próximo passo sugerido: eu executo a Fase 0 (Épico 0) e te trago o domínio apontado, a auditoria das fontes e o funil medido, enquanto você responde as decisões acima. O backlog vira issues no GitHub assim que o repo for público.*
