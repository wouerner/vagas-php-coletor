# Vagas PHP — Plano de 30 dias (primeira receita + comunidade)

**PM:** Hermes · **Data:** 21/10/2026 · **Status:** v1 para execução
**Meta do mês:** site com marca própria, audiência chegando por canal próprio, e **primeira conversa de venda fechada**.
**Pergunta que o mês responde:** alguém paga por isso?

---

## 1. Domínio

Checado via RDAP do Registro.br em 21/out/2026:

| Domínio | Status | Recomendação |
|---|---|---|
**Domínio atual: `https://vagasphp.wouerner.dev`** — subdomínio da zona `wouerner.dev` (Cloudflare plano Free → Traefik do Coolify). A URL antiga (`*.sslip.io` gerada pelo Coolify) foi desativada e dá 404. Detalhes em [`../deploy.md`](../deploy.md).

Aproveitou-se a zona `wouerner.dev` que já existia, então o custo é **R$ 0/ano**. Os nomes `vagasphp.com.br` e `phpvagas.com.br` continuam livres, caso se queira um `.com.br` depois.

**Conferido em 22/10/2026:** `/` → 200 (server: cloudflare) · `http://` → 302 para `https://` · `/dashboard?print=1` → 200 · `/api/jobs` → 200 com vagas. `VBP-001` concluído.

---

## 2. Preço e ponto de equilíbrio

**Custo fixo:** R$ 200/mês (Coolify + MySQL) = **R$ 6,67/dia**.
**Recebimento:** Pix via CNPJ. Taxa típica de Pix empresarial ~0,5–3%; para valores pequenos, use **QR estático + confirmação manual** (zero taxa de gateway).

| Produto | Preço | O que inclui | Vendas pra cobrir a infra |
|---|---|---|---|
| **Vaga patrocinada (M2)** | R$ 197 / 7 dias | topo + selo + repost no Telegram | 2 vendas/mês |
| **Relatório de mercado (M1)** | R$ 297 / mês | PDF + planilha | 1 venda/mês |
| **Slot na newsletter (M4)** | R$ 97 / edição | 1 edição | 2–3 edições |
| **Licença de API (M3)** | R$ 97 / mês | acesso estendido | 3 clientes |

**Piso de preço:** nunca abaixo de **R$ 97** por venda. Abaixo disso o volume não cobre a operação.
**Combinação alvo do mês:** 1 M1 (R$ 297) + 1 M2 (R$ 197) = **R$ 494/mês** → infra coberta + ~R$ 294 de margem.

**Regra de PM:** com R$ 200/mês de custo fixo, "cobrar barato pra começar" é erro. Quem cobra R$ 47 por vaga patrocinada precisa vender 5 pra empatar — e o produto vira bicos.

---

## 3. As 4 semanas

### SEMANA 1 (D1–D7) — Marca e verdade
**Objetivo:** o produto deixa de ser um link feio e a PM passa a enxergar o funil.

| Dia | Ação | Backlog | Dono |
|---|---|---|---|
| D1 | Comprar domínio e apontar DNS | `VBP-001` | você |
| D1 | Reativar o coletor do dev local (higiene) | `VBP-007` | Hermes |
| D2 | Auditoria das 13 fontes em produção (quem rende, quem está `open: 0`) | `VBP-002` | Hermes |
| D2 | Confirmar se o post diário está saindo em produção | `VBP-003` | Hermes |
| D3 | Corrigir o seletor do composer do LinkedIn (`linkedin_post.py:80`) | — | Hermes |
| D4 | Funil no GA: origem, páginas, termos buscados | `VBP-004` | Hermes |
| D5 | Revisar termos/intervalo das fontes que não rendem | `VBP-005` | Hermes |
| D6 | Subir a captura de salário (meta > 20%) | `VBP-006` | Hermes |
| D7 | **Revisão de semana:** números do dashboard + GA; ajustar plano | — | você + Hermes |

**Saída da semana 1:** domínio no ar, GA medindo, fontes com dono definido, post diário confirmado.

---

### SEMANA 2 (D8–D14) — Canal próprio
**Objetivo:** parar de alugar audiência do LinkedIn. Quem visita passa a ter onde voltar.

| Dia | Ação | Backlog | Dono |
|---|---|---|---|
| D8 | Bot que empurra vaga nova para grupo Telegram/Discord | `VBP-101` | Hermes |
| D9 | Criar o grupo e o material de entrada (Boas-vindas, regras) | `VBP-101` | você |
| D10 | Campo de captura de e-mail na home (opt-in LGPD) | `VBP-102` | Hermes |
| D11 | Página "Sobre / Regras / Contato" | `VBP-104` | Hermes |
| D12 | Primeira newsletter manual (topo da semana + dado de mercado) | `VBP-103` | Hermes |
| D13 | Divulgar o grupo e a newsletter (seu LinkedIn, comunidades PHP) | — | você |
| D14 | **Revisão de semana:** crescimento de e-mails e grupo; taxa de abertura | — | você + Hermes |

**Saída da semana 2:** grupo com bot ativo, primeira newsletter enviada, base de e-mails começando.

---

### SEMANA 3 (D15–D21) — Embalagem da receita
**Objetivo:** transformar o que já existe em produto vendável. Sem isso, não há conversa de venda.

| Dia | Ação | Backlog | Dono |
|---|---|---|---|
| D15 | Script do relatório de mercado a partir do MySQL (M1) | `VBP-201` | Hermes |
| D16 | Definir preço/formato do relatório + página de venda | `VBP-202` | você + Hermes |
| D17 | Montar a lista de leads da própria base (empresas que estão contratando PHP agora) e abordar as 30 primeiras com a vaga delas | `VBP-203` | Hermes gera a lista / você aborda |
| D18 | Modelo de dados da vaga patrocinada (M2) | `VBP-301` | Hermes |
| D19 | Checkout Pix/cartão e confirmação | `VBP-302` | Hermes |
| D20 | Fixar patrocinada no topo + selo "Patrocinada" | `VBP-303` | Hermes |
| D21 | Página de venda da vaga patrocinada com estimativa de alcance | `VBP-305` | Hermes |

**Saída da semana 3:** relatório pronto pra vender, vaga patrocinada comprável e exibindo.

---

### SEMANA 4 (D22–D30) — Fechar e aprender
**Objetivo:** dinheiro no bolso (ou um "não" bem explicado) e a decisão sobre open source.

| Dia | Ação | Backlog | Dono |
|---|---|---|---|
| D22 | Entregar o primeiro relatório M1 e coletar feedback | `VBP-204` | você |
| D23 | Fechar a primeira vaga patrocinada (M2) | `VBP-306` | você |
| D24 | Repost da vaga patrocinada no canal próprio | `VBP-304` | Hermes |
| D25 | Tornar o repo público + `CONTRIBUTING.md` + templates de issue | `VBP-501` a `503` | Hermes |
| D26 | Blog: 5 páginas de cauda longa (SEO) + `sitemap.xml` | `VBP-504`, `VBP-505` | Hermes |
| D27 | Slot de patrocínio na newsletter (M4) + página de mídia | `VBP-401`, `VBP-402` | Hermes |
| D28 | Documentar a API/MCP (M3) | `VBP-601` | Hermes |
| D29 | **Revisão do mês:** o que vendeu, o que não vendeu, por quê | — | você + Hermes |
| D30 | Decidir próximo trimestre (M3/M5/M6, eventos, embaixadores) | — | você |

**Saída da semana 4:** primeira receita (ou diagnóstico claro do porquê não), repo público, blog no ar, newsletter com slot de patrocínio.

---

## 4. Cadência diária (10 min)

Mesma rotina todos os dias — é o que impede o produto de morrer de novo:

1. Dashboard: vagas abertas, novas em 24 h, fontes com vaga (meta: nenhuma `open: 0` sem justificativa).
2. Post diário: publicado? Se falhou, corrigir no mesmo dia (hoje falha em silêncio).
3. GA: visitas, origem, páginas mais vistas.
4. E-mail/grupo: novos contatos e perguntas não respondidas.
5. Vendas: responder proposta pendente. **Venda parada é a única coisa que mata o mês.**

---

## 5. Métricas do mês (linha de base 21/out → D30)

| Métrica | Hoje | Meta D30 |
|---|---|---|
| Vagas abertas/dia | 65 | 60+ todos os dias |
| Post diário publicado | incerto | 25/30 dias |
| Domínio próprio | não | `https://vagasphp.com.br` |
| Visitas/mês (GA) | desconhecido | baseline medido |
| E-mails capturados | 0 | 300 |
| Grupo Telegram | 0 | 150 |
| Newsletter enviada | 0 | 4 edições |
| Empresas abordadas (M2) | 0 | 30 |
| Clientes pagantes | 0 | **1** |
| MRR | R$ 0 | ≥ R$ 297 (cobre os R$ 200 de infra) |

**Critério de sucesso do mês:** pelo menos 1 cliente pagante **ou** um "não" com motivo documentado que mude o plano. Os dois valem.

---

## 6. O que pode dar errado (e o plano B)

| Risco | Sintoma | Plano B |
|---|---|---|
| LinkedIn bloqueia o bot | post falha todo dia | Grupo Telegram e e-mail viram o canal principal; post fica manual até o seletor voltar |
| Ninguém compra M1 em 20 dias | 0 respostas na prospecção | Muda pra M2 (vaga patrocinada) — compra por intenção, não por projeto |
| Sem contato com RH (rede fria) | resposta < 5% | Usar a **própria base como lista de leads**: as 33 empresas que estão contratando PHP hoje são o contato. Abordagem personalizada com a vaga deles |
| Fontes continuam `open: 0` | coleta parada de novo | Desligar as que não rendem e concentrar nas que rendem; simplicidade > cobertura |
| Cobrar barato demais | 5 vendas e prejuízo | Respeitar o piso de R$ 97 (seção 2); infra de R$ 200 não tolera ticket baixo |
| Tempo curto (você trabalha em outras coisas) | semana atrasada | Cortar M2 da semana 3 e entregar só M1 + canal próprio; o mês continua válido |
| Pix sem automação | confirmação manual atrasada | QR estático + confirmação em até 24 h; registrar o pagamento em planilha |

---

## 7. Decisões tomadas (21/out)

| Decisão | Escolha |
|---|---|
| Domínio | **`vagasphp.wouerner.dev`** — no ar (Cloudflare + Coolify); `.sslip.io` antigo desativado |
| Canal da comunidade | **Telegram** |
| Recebimento | **Pix**, com CNPJ |
| Infra | Coolify + MySQL = **R$ 200/mês** (custo fixo) |
| Contato com RH | **Nenhum** → prospecção fria, usando a própria base como lista de leads |
| Prazo do primeiro real | **30 dias** |
| **Post diário no LinkedIn** | **Roda local** (IP residencial), print e números de produção. **Produção não posta.** |

### Post diário — como ficou

- **Onde roda:** máquina local, pelo cron da Hermes (todo dia às **9h**, horário de Brasília), script `~/.hermes/scripts/vagas_post.sh`.
- **Print e números:** vêm do dashboard de **produção** (`VAGAS_DASHBOARD_URL` no `.env` do dev), então o post sempre mostra os números reais do site.
- **Comando:** `docker compose run --rm vagas-php post` (`--dry-run` monta sem publicar; `--probe` inspeciona a caixa de publicação do LinkedIn).
- **Proteções:** não publica duas vezes no mesmo dia; se o histórico de posts estiver ilegível, **se recusa a publicar** em vez de sobrescrevê-lo.
- **Por que não em produção:** o IP do datacenter aumenta o risco de bloqueio do LinkedIn. O seletor do composer foi corrigido (a caixa virou `<dialog open>` com o editor em shadow DOM).
- **Pendência em produção:** garantir `VAGAS_LINKEDIN_DAILY_POST=false` no Coolify — a produção ainda tenta postar do IP de datacenter e falha.

**Semana 1 — status:** domínio no ar ✅ · post diário rodando localmente (cron 9h) ✅ · falta confirmar o funil no GA e revisar as fontes que não rendem.

---

*O plano de fundo continua em [`plano-monetizacao-comunidade.md`](plano-monetizacao-comunidade.md). Os IDs `VBP-*` são as mesmas histórias do backlog.*
