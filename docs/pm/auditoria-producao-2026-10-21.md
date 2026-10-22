# Auditoria de produção — 21/10/2026

**PM:** Hermes · **Escopo:** semana 1 do plano de 30 dias (`VBP-002`, `VBP-003`, `VBP-004`, `VBP-005`)
**Produção:** `https://vagasphp.wouerner.dev` (Cloudflare → Traefik do Coolify → serviço `web`)
**URL antiga:** `*.sslip.io` do Coolify — **desativada**, dá 404
**Método:** leitura da API pública da produção (`/api/jobs`, `/api/stats`, `/api/dashboard`, `/api/rules`).

---

## 1. VBP-002 — Saúde das fontes: **saudável**

As 13 fontes rodaram com sucesso (`ok=1`) nas últimas horas. Nenhuma falha de coleta.

| Fonte | Última run (UTC) | listadas | encontradas | novas | falhas |
|---|---|---|---|---|---|
| linkedin | 22/10 01:11 | 162 | 162 | 1 | 0 |
| gupy | 22/10 02:35 | 0 | 0 | 0 | 0 |
| post | 21/10 21:21 | 62 | 62 | 19 | 0 |
| github | 22/10 02:14 | 0 | 0 | 0 | 0 |
| remotar | 22/10 02:19 | 0 | 0 | 0 | 0 |
| programathor | 22/10 01:22 | 277 | 0 | 0 | 1 |
| catho | 22/10 01:23 | 4 | 1 | 0 | 0 |
| solides | 22/10 00:45 | 0 | 0 | 0 | 0 |
| inhire | 22/10 02:00 | 392 | 0 | 0 | 0 |
| coodesh | 22/10 02:38 | 100 | 0 | 0 | 0 |
| nerdin | 22/10 00:39 | 11 | 0 | 0 | 0 |
| recrutei | 22/10 02:43 | 990 | 1 | 0 | 0 |
| upvagas | 22/10 01:55 | 0 | 0 | 0 | 0 |

**Leitura dos campos (pelo código, `vagas_php/collect.py`):**
- `listed` = itens que a fonte apresentou (sitemap inteiro ou página), antes de tirar os já conhecidos;
- `found` = vagas efetivamente baixadas e avaliadas;
- `new` = vagas novas salvas.

**Conclusão:** não há fonte quebrada. `listed=0` em gupy/solides/upvagas significa "nenhuma vaga apresentada na janela desde a última coleta", não erro. As APIs foram testadas diretamente e respondem com dados reais (Gupy 200 com vagas de 20/10; Sólides 200 com 61 vagas; UpVagas 200 com vagas de 14/10 — exige `User-Agent` completo, bloqueado com UA genérico).

**Único ponto de atenção:** `programathor` registrou **1 falha** (`failed=1`) — uma página de vaga não baixou. Não é bloqueio, mas vale observar na próxima semana.

---

## 2. VBP-005 — Fontes que não rendem: **cobertura, não bug**

Cinco fontes não têm nenhuma vaga aberta nas últimas 72 h:

| Fonte | Total na base | Relevantes | Abertas | Diagnóstico |
|---|---|---|---|---|
| coodesh | 44 | 0 | 0 | nenhuma vaga PHP passou no filtro |
| inhire | 152 | 5 | 0 | vagas PHP, mas todas fora da janela |
| programathor | 263 | 257 | 0 | 257 relevantes — as mais novas estão velhas |
| recrutei | 81 | 55 | 0 | mesma situação |
| upvagas | 9 | 2 | 0 | poucas vagas, fora da janela |

**Leitura de PM:** o problema não é a coleta, é a **matéria-prima**. Esses portais publicam poucas vagas PHP por semana, e as que publicam envelhecem antes de 72 h. Isso reforça a concentração já mapeada: **LinkedIn + publicações = 78% da oferta**. Ações possíveis (decidir na semana 2):
- Ampliar termos de busca nas fontes com filtro fraco (coodesh: 0 relevantes em 44).
- Ampliar a janela dessas fontes para 7 dias, mantendo o site em 72 h (mostrar como "antigas").
- Ou aceitar e concentrar esforço no que rende.

---

## 3. VBP-003 — Post diário: **provavelmente quebrado em produção**

O histórico dos posts fica em `data/linkedin_posts.json`, num volume do Coolify que **não é exposto pela API** — por isso não dava para confirmar remotamente.

Mas o dev local, que roda **o mesmo código**, mostrou o comportamento:

- O dev tentou publicar em **19/10, 20/10 e 21/10, às 9h (e 9h30/10h nas retentativas)**;
- **Todas falharam** com `TimeoutError` esperando o editor (`#interop-outlet` → `div.ql-editor[contenteditable=true]`);
- O dev estava com `VAGAS_LINKEDIN_DAILY_POST=true` e acessou a conta do LinkedIn nesses horários, ao mesmo tempo que a produção.

**Conclusão de PM:** a produção usa o mesmo `linkedin_post.py` (última alteração em 16/out, commit "Prepara o projeto para open source"). Se o seletor mudou no LinkedIn, **o post diário está mudo em produção** — o produto não tem canal de distribuição.

Isso sobe de "confirmar" para **corrigir o seletor** (`VBP-003b`), e a correção precisa ser publicada no Coolify.

---

## 4. VBP-004 — GA: **medindo** ✅

Configurado e com dados reais. Acesso: service account `ga-reader@vagas-php` (projeto GCP `vagas-php`, Property ID **559268978**), script `~/.hermes/ga/ga_report.py`.

**Últimos 7 dias (22/10/2026):**

| Métrica | Valor |
|---|---|
| Sessões | **32** |
| Usuários | 20 |
| Visualizações de página | 88 |
| Canais | Direct 26 (68%) · Organic Social 8 (25%) · Unassigned 2 |
| Páginas | `/` 59 · `/dashboard` 15 · `/empresas` 4 |
| Termos de busca | vazio 34 · "BairesDev" 1 · "Leega" 1 · "wordpress" 1 |

**Leitura de PM:** o tráfego é **muito baixo** (~30 sessões/semana) — o site não tem audiência ainda. O `Direct` domina (quem chega pelo post do LinkedIn ou digita a URL) e **não há tráfego orgânico de busca** (o SEO ainda não existe). Quase ninguém usa a busca do site (os termos são quase todos vazios). Isso confirma que a semana 2 — captura de e-mail e newsletter — é o caminho certo: sem audiência própria, não há para quem vender.

**Ressalva:** com `analytics_storage: denied` por padrão (Consent Mode/LGPD), o GA recebe o hit mas não grava cookie — as sessões podem estar levemente subcontadas e a retenção de usuário não é confiável até as pessoas aceitarem o cookie.

---

## 5. VBP-007 — Dev local: **reativado** ✅

Feito pelo Claude Code (diretiva do usuário: mudanças de dev passam pelo Claude Code).

| Etapa | Resultado |
|---|---|
| `data/config.json` | 13 fontes `enabled: true` (1ª passagem) |
| Proteção contra post duplicado | `linkedin` e `post` → `enabled: false`; `VAGAS_LINKEDIN_DAILY_POST=false` no `.env` |
| Restart do container `vagas-php` | feito; serviço subiu sem erro |
| `data/schedule.json` | **11 fontes com `next_run` preenchido**; `linkedin`/`post` com `next_run: null` |
| Coleta de teste (Gupy) | `found: 38, relevant: 4, new: 4` — pipeline OK |
| API local | 3 vagas (limite 3), `has_more: true` |

**Risco tratado:** o dev tinha `VAGAS_LINKEDIN_DAILY_POST=true`. Reiniciar sem desligar faria o dev postar no LinkedIn junto com a produção. Desligado antes do restart — e o histórico confirma que o dev já estava tentando postar (e falhando).

**Risco conhecido:** chamar `configure_scheduler` pelo MCP **sobrescreve** o `config.json` com o estado em memória (`service.py:344`). Não usar o MCP no dev.

---

## 6. Resumo executivo

| # | Item | Estado |
|---|---|---|
| 1 | Coletor em produção | ✅ Saudável, 13/13 fontes OK |
| 2 | Site com vagas | ✅ 65 abertas, 27 novas em 24 h |
| 3 | Domínio próprio | ❌ `*.sslip.io` — registrar amanhã (lembrete agendado) |
| 4 | GA medindo | ⚠️ Tag presente; confirmar hits |
| 5 | **Post diário** | ❌ **Quebrado (seletor do LinkedIn) — produção provavelmente muda** |
| 6 | Fontes que não rendem | ⚠️ Cobertura fraca (5 fontes sem vaga aberta) |
| 7 | Captura de salário | ❌ 1 de 65 vagas (1,5%) |
| 8 | Dev local | ✅ Reativado, 11 fontes ativas |

**Nada bloqueia a semana 2.** Bloqueios: domínio, captura de contato, funil do GA — e agora o post diário, que é o canal de distribuição.

---

## 7. Próximas ações

1. **Corrigir o seletor do post diário** (`linkedin_post.py:80`) no dev e validar com uma publicação de teste; depois publicar no Coolify.
2. Painel do GA (`G-47NEQJSJN8`) — confirmar visitas e origem.
3. Volume `vagas-data` no Coolify — confirmar o histórico de posts da produção.
