# Search Console / indexação — diagnóstico 27/10/2026

## Como ler os dados (acesso direto, sem depender do painel)

A propriedade existe e a conta de serviço do projeto tem acesso:

- Propriedade: `sc-domain:vagasphp.wouerner.dev` (propriedade de **domínio** do subdomínio)
- `ga-reader@vagas-php.iam.gserviceaccount.com` → permissão **siteFullUser**
- Leitura por API: Search Console API (`webmasters.readonly`) — script de apoio em
  `~/.hermes/cache/scratch/sttenv` (venv) + `~/.hermes/ga/service-account.json`

## O que os dados dizem (27/10)

| Item | Estado |
| --- | --- |
| Cliques / impressões desde 21/10 (criação da propriedade) | **0 / 0** em todos os dias; nenhuma consulta, nenhuma página |
| Home `/` | **Indexada** (`Enviada e indexada`), rastreada em **25/10 00:58**, canônica correta, robots ALLOWED, rastreada como celular |
| `/vagas/laravel`, `/vagas/symfony`, `/mercado-php` e demais | **O Google não reconhece o URL** (nunca rastreadas) |
| Sitemap | Enviado **22/10 18:34**, baixado **uma vez** (22/10 18:34), 0 erros, 0 avisos; 84 URLs na época, 74 hoje — o Google não voltou |
| robots.txt | `Allow: /` + linha do Sitemap (correto) |
| `/api/*` | `X-Robots-Tag: noindex` (correção de 27/10 no ar) |
| Googlebot na home | 200, 144.900 bytes de HTML renderizado no servidor |

**Conclusão: não é falta de dado nem propriedade errada — é falta de presença.** O Google conhece
uma única página do site e não mostra nenhuma delas para nenhuma consulta.

## Causas

1. **Subdomínio novo, praticamente sem link externo.** O Google descobriu a home (pelo sitemap) e
   parou aí; nenhuma página foi rastreada em 5 dias.
2. **O rastreio da home (25/10) é anterior à correção do robots (27/10).** Naquele rastreio o
   renderizador estava bloqueado de `/api/`, então o Google viu a home sem conseguir carregar os
   dados das vagas. Precisa de novo rastreio para ver a versão certa.
3. **As 32 páginas de vaga abertas já estão no sitemap** (74 URLs = 8 institucionais + 34 de tema +
   32 de vaga). Elas dependem só de link interno para serem descobertas — e como o Google nunca
   rastreou nada além da home, nenhuma delas é conhecida. O caminho aqui não é mexer no sitemap: é
   **empurrar** as vagas pela Indexing API.

## Achados que abrem porta (não estavam no radar)

1. **As páginas de vaga têm JSON-LD `JobPosting` completo e válido** (`datePosted`, `description`,
   `hiringOrganization`, `jobLocation`, `title`, `validThrough`, `employmentType`, `identifier`).
   Isso habilita o **Google Jobs** (a experiência de vagas dentro da busca) — para um site de vagas,
   a fonte de tráfego mais importante que existe — e habilita a **Indexing API**, a via rápida que o
   Google oferece justamente para `JobPosting`.
2. **`validThrough` = publicação + 72 h**, que é exatamente a janela em que a vaga é considerada
   aberta no site (depois disso a página vira 200 com `noindex` e sem o markup). Ou seja: **está
   coerente com o ciclo de vida da página** — não é furo. (Correção de 28/10: a primeira leitura deste
   documento dizia para estender para 30–60 dias; isso criaria a contradição de a página deixar de ser
   `JobPosting` no dia 3 e o markup afirmar validade até o dia 30.) O que resolve a janela curta é
   anunciar a vaga ao Google **na hora** pela Indexing API, em vez de esperar rastreio.
3. **Indexing API habilitada pelo dono em 28/10**, mas a chamada ainda devolve
   `403 Permission denied. Failed to verify the URL ownership`: a conta de serviço está como
   **Full** na propriedade e a Indexing API exige **Owner**. Ação do dono: Search Console →
   Configurações → Usuários e permissões → `ga-reader@vagas-php.iam.gserviceaccount.com` → Proprietário.
4. O `gcloud` local está autenticado como a conta de serviço (sem permissão de `serviceusage`), então
   ligar API no projeto é sempre ação do dono.

## Plano de correção, em ordem de impacto

1. **[dono, 1 minuto]** Trocar a permissão da conta de serviço para **Proprietário** na propriedade.
2. **[código, feito]** Publicar cada vaga nova/atualizada pela Indexing API
   (`urlNotifications.publish`, tipo `URL_UPDATED`), com teto diário de 150 (quota do projeto: 200/dia)
   e registro em `indexing_log` para não repetir URL. Resolve o "não reconhece o URL" em horas.
3. **[dono, painel]** Reenviar o sitemap e pedir indexação manual da home e das 8 institucionais
   (Inspeção de URL → Solicitar indexação) — o atalho manual que ainda vale para as páginas fixas.
4. **[monitoramento]** Relatório semanal: URLs conhecidas x indexadas x impressões. Indexação leva
   dias a semanas — o primeiro sinal a esperar é **impressão**, não clique.

## Leitura de produto

O pilar de SEO do plano ainda **não produziu nada**: o tráfego de hoje (~28 sessões/dia) vem de
LinkedIn e direto. Isso é normal para subdomínio novo com 17 dias, mas o gargalo não é conteúdo nem
sitemap — é **descoberta**: sem link externo, sem empurrão da Indexing API e com o único rastreio da
home feito antes da correção do robots (27/10).
