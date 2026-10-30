# vagas-php

Coleta e lista **vagas de engenharia de software com PHP** (PHP, Laravel, Symfony,
CodeIgniter, Hyperf...). Monorepo com duas partes que conversam só pelo MySQL 8:

| Pasta | Linguagem | O que faz |
|---|---|---|
| [`web/`](web/) | **PHP 8.5** (sem framework, PDO, Pest) | o site, a API JSON, o sitemap e as páginas para buscadores |
| [`collector/`](collector/) | Python + Playwright | coleta agendada das fontes, filtro de PHP, servidor MCP, post diário, alertas do Telegram e Google Indexing API |

**Por que duas linguagens?** O site é PHP, como o público dele. O coletor ficou em Python
por causa do navegador automatizado: o Playwright não tem binding oficial para PHP, e é ele
que lê as publicações do LinkedIn (seletores por papel de acessibilidade, perfil
persistente do Chromium). As outras fontes são HTTP puro e poderiam ser portadas; PRs são
bem-vindos. O contrato entre as duas partes (tabelas, colunas e `site_meta`) está em
[docs/contrato-base.md](docs/contrato-base.md).

Canal no Telegram: [t.me/vagas_php](https://t.me/vagas_php) — alertas de vagas em tempo real
e um resumo semanal toda segunda às 10h.

## Fontes

| Fonte | Como | Login | Intervalo padrão |
|---|---|---|---|
| `linkedin` | busca pública de vagas (`php`, `laravel`, `symfony`) + descrição de cada vaga nova | não | 3 h |
| `gupy` | API pública do portal da Gupy: `php`, `laravel`, `symfony` e termos amplos (`desenvolvedor`, `backend`, `full stack`) | não | 2 h |
| `post` | busca de publicações (`vaga php`, `vaga laravel`, `desenvolvedor php`, `pessoa desenvolvedora php`, `oportunidade php`) | sim | 8 h, das 8 às 22 h |
| `github` | issues de `phpdevbr/vagas`, `backend-br/vagas` | não | 1 h |
| `solides` | API pública do portal da Sólides (vagas.solides.com.br): `php`, `laravel`, `symfony`, `codeigniter` (a busca olha título e descrição) | não | 2 h |
| `catho` | busca da Catho (`/vagas/<termo>/`, mais recentes primeiro, últimos N dias): `php`, `laravel`, `symfony`, `codeigniter`; página de cada vaga nova com título de desenvolvimento (JSON-LD `JobPosting`) | não | 3 h |
| `remotar` | API pública da Remotar (vagas 100% remotas): `php`, `laravel`, `symfony`, data/hora exata | não | 2 h |
| `programathor` | listas da Programathor (`/jobs-php`, `/jobs-laravel`, `/jobs-symfony`, `/jobs-codeigniter`) + JSON-LD `JobPosting` da página de cada vaga nova | não | 3 h |
| `coodesh` | sitemap de vagas da Coodesh (`/sitemaps/jobs.xml`) + JSON-LD `JobPosting` das vagas novas alteradas na janela com título de desenvolvimento | não | 3 h |
| `nerdin` | busca da Nerdin (portal de vagas de TI, `vagas.php?busca=<termo>`) + JSON-LD `JobPosting` da página de cada vaga nova | não | 3 h |
| `recrutei` | sitemap do portal da Recrutei (`empregos.recrutei.com.br/sitemap-vagas-N.xml`; a busca do site é proibida no robots.txt) + JSON-LD `JobPosting` das vagas novas alteradas na janela com título de desenvolvimento | não | 3 h |
| `upvagas` | API do WordPress da UpVagas (`/wp-json/wp/v2/job-listings?search=`, vagas remotas, muitas internacionais abertas ao Brasil), data/hora exata | não | 2 h |
| `inhire` | API pública das páginas de carreira de empresas na InHire (`<empresa>.inhire.app/vagas`): lista de empresas em `VAGAS_INHIRE_TENANTS` + empresas descobertas em links `.inhire.app` nas vagas e posts coletados | não | 2 h |

**Só valem vagas publicadas há no máximo 72 horas** (`VAGAS_MAX_AGE_HOURS`). Cada
coleta busca desde a última coleta OK da fonte, nunca antes desse limite, e site, API e
MCP só mostram o que está dentro dele. As datas ficam em UTC na base e aparecem no
horário de Brasília no site. Precisão de cada fonte:

- **GitHub**, **Gupy**, **Remotar**, **UpVagas** e **InHire**: data/hora exata;
- **Sólides**, **Catho**, **Programathor**, **Coodesh**, **Nerdin** e **Recrutei**: só o dia (em Brasília); contamos
  desde 00:00 daquele dia;
- **vagas do LinkedIn**: a página pública dá o dia (em Brasília) e um texto relativo; com
  "há 7 horas" usamos a hora, com "há 2 dias" contamos desde 00:00 daquele dia — a
  hipótese mais antiga, para nada com mais de 72 h aparecer como recente;
- **publicações**: o LinkedIn mostra "18 h", "2 d"...; "3 d" já fica de fora.

Tudo vai para o MySQL (`DATABASE_URL`), mas só aparece no site o que passa no filtro de PHP
(`collector/vagas_php/php.py`):

- **vagas de portais e issues**: PHP/framework no título ou nas etiquetas; ou título de
  desenvolvimento com PHP citado 2+ vezes na descrição (uma menção só costuma ser
  "PHP, Python, Java ou Go" ou "PHP é diferencial");
- **publicações**: PHP no texto (hashtags não contam) com cargo de desenvolvimento,
  sinal claro de contratação e sem ser alguém procurando emprego (`#opentowork`,
  "estou em busca"...). Sinais fortes ("vaga para", "estamos buscando", "candidate-se"...)
  bastam; sinais fracos ("oportunidade de", "vagas de", "processo seletivo", `#vagas`) só
  valem com estrutura de vaga (2+ de requisitos, benefícios, CLT/PJ, remuneração...) ou num
  post curto com `#vagas`, e nunca com contexto de outro assunto (`NOT_HIRING`: projeto
  pessoal, "encerro minha jornada", certificados). Divulgação de grupos e canais de vagas
  sem curadoria (`AGGREGATOR`: Discord, Telegram, "nossos grupos", "Vagas T.I. -"...; 3 ou
  mais padrões diferentes) é barrada mesmo com sinal forte. Para barrar um novo tipo de
  post, acrescente um padrão em `NOT_HIRING` ou `AGGREGATOR`; ao reiniciar, o serviço
  reaplica o filtro às publicações já salvas.

O que ainda escapar pode ser descartado à mão com a ferramenta MCP `dismiss_job` (id, URL
ou número do post): a vaga sai do site, da API e do MCP e não volta em novas coletas.

**Transparência**: a página `/regras` do site mostra todas as regras de filtro (vagas e
publicações), na ordem em que são aplicadas, com as expressões usadas, quantos
itens da base cada uma decidiu e a lista do que foi descartado à mão, com o motivo. Ela é
gerada de `php.RULES` (`GET /api/rules`), que lê as mesmas constantes do filtro: ao mudar
uma regra, atualize o texto dela em `RULES`. O coletor grava as regras e a contagem na
base (`site_meta`) na subida e depois de cada coleta; o site só as mostra.

Issues fechadas no GitHub ficam marcadas como encerradas e saem do site.

## Configuração

Copie `.env.example` para `.env` e ajuste: credenciais do LinkedIn (só para a fonte
`post` e o post diário) e as configurações das fontes. Ajustes feitos pela ferramenta MCP
`configure_scheduler` ficam em `data/config.json` e têm precedência sobre o `.env`.

## Serviço (Docker)

```bash
docker compose up -d --build   # coletor + site
docker compose logs -f         # acompanha as coletas
docker compose down
```

Portas (por padrão tudo só em `127.0.0.1`; o site pode ser aberto na rede):

| | porta | variável |
|---|---|---|
| site | `8780`: http://localhost:8780 (aberto na rede com `WEB_BIND=0.0.0.0` no `.env`) | `WEB_PUBLISH_PORT`, `WEB_BIND` |
| MCP | `8766`: http://localhost:8766/mcp | `MCP_PUBLISH_PORT` |
| noVNC | `6081`: http://localhost:6081/vnc.html | `NOVNC_PUBLISH_PORT` |
| VNC | `5901` | `VNC_PUBLISH_PORT` |
| MySQL | `3307` | `MYSQL_PUBLISH_PORT` |

### Sessão do LinkedIn

O container monta `./.session`, o perfil do Chromium com o login do LinkedIn (mude com
`LINKEDIN_SESSION_PATH`). Só a fonte `post` e o post diário usam a sessão. No primeiro
uso, ou se o LinkedIn pedir verificação (2FA/captcha), conclua o login pelo noVNC:
http://localhost:6081/vnc.html.

### Usar no Claude Code

```bash
claude mcp add --transport http vagas-php http://localhost:8766/mcp   # ou use o .mcp.json
```

| Ferramenta | |
|---|---|
| `list_jobs(q, source, workplace, seniority, stack, hours, include_closed, limit, offset)` | consulta a base local (máx. 72 h) |
| `collect_now(source)` | coleta agora `linkedin`, `gupy`, `remotar`, `programathor`, `catho`, `solides`, `inhire`, `coodesh`, `nerdin`, `recrutei`, `upvagas`, `github` ou `post` |
| `check_post(url)` | confere um post do LinkedIn pelo link (inclusive `lnkd.in`): qual regra decidiu e se aparece no site; guarda na base se falar de PHP |
| `get_status()` | configuração, próximas coletas, totais, últimas execuções |
| `configure_scheduler(source, enabled, interval_hours, active_hours)` | ajusta a coleta de uma fonte |
| `dismiss_job(ref, reason, undo)` | marca uma vaga/publicação como "não é vaga" (id, URL ou número do post) |

## Post diário no LinkedIn

Com `VAGAS_LINKEDIN_DAILY_POST=true`, o serviço publica todo dia às `VAGAS_LINKEDIN_POST_TIME`
(horário de Brasília, padrão 09:00), nos dias de `VAGAS_LINKEDIN_POST_DAYS` (0 = segunda ...
6 = domingo), um post na conta da sessão do bot (`collector/vagas_php/linkedin_post.py`):

- imagem: print do topo do dashboard (números, vagas por site e vagas novas por dia);
- texto: resumo do dia (vagas abertas, novas em 24 h, remotas, empresas), fontes, filtro,
  convite para o canal do Telegram (`VAGAS_LINKEDIN_POST_TELEGRAM`, padrão
  `https://t.me/vagas_php`; vazia, sem a linha), hashtags e, se definida, a assinatura
  `VAGAS_LINKEDIN_POST_SIGNATURE` no fim.

O resumo semanal do [canal do Telegram](https://t.me/vagas_php) (`telegram-digest`) é este
mesmo post: o mesmo print do dashboard e o mesmo texto.

Os alertas de vagas novas do canal saem de `python -m vagas_php telegram-alert`, que lê a
API pública do site e envia, por padrão, uma mensagem por vaga (no máximo `--limit`, 5).
Com `--batch`, todas as vagas pendentes vão numa mensagem só (título em negrito e, abaixo,
empresa · local · modalidade · senioridade · stack e o link); se a mensagem passar do limite
de 4096 caracteres do Telegram, as mais antigas ficam para a próxima execução. A janela
`VAGAS_TELEGRAM_ACTIVE_HOURS` (padrão `8-19`, horário de Brasília) e o `--force` valem nos
dois modos; `--dry-run` só imprime, sem enviar nem gravar o estado.

Antes de publicar, confere se o texto aparece uma vez só (o LinkedIn pode restaurar um
rascunho) e se a imagem foi anexada; se não, não publica. No máximo um post por dia: se
falhar, tenta de novo a cada 30 min, até 3 vezes, nas 3 h seguintes ao horário. Prévia,
imagem, texto e confirmação de cada dia ficam em `data/linkedin_posts/AAAA-MM-DD/`, e o
histórico em `data/linkedin_posts.json`.

## Site (PHP)

O site fica em [`web/`](web/): PHP 8.5 sem framework (um roteador pequeno, PDO e templates
HTML com marcas `<!--ssr:nome-->`), servido por Apache na imagem Docker. Para rodar fora do
Docker, com o MySQL do compose no ar:

```bash
cd web
composer install
DATABASE_URL=mysql://vagas:vagas@127.0.0.1:3307/vagas composer serve   # http://127.0.0.1:8780
composer test                                                         # Pest
```

| Arquivo | |
|---|---|
| `web/src/Site.php` | rotas, home, temas, empresas, recrutadores, regras, sitemap, `/out` |
| `web/src/Vaga.php` | página de cada vaga (`/vaga/<número>-<título>`) e o JSON-LD `JobPosting` |
| `web/src/Mercado.php` | `/mercado-php` e `/llms.txt` |
| `web/src/Repo.php` | as consultas SQL |
| `web/src/Seo.php` | `<head>` (título, canonical, Open Graph, JSON-LD) e o endereço das vagas |
| `web/templates/` | as páginas (HTML, CSS e JavaScript de cada uma) |

`http://localhost:8780`: busca por texto e filtros de fonte, modalidade, senioridade,
stack e período (1, 4, 6, 24, 48 ou 72 h; os filtros ficam na URL, para compartilhar). API em JSON:

- `GET /api/jobs?q=laravel&source=github&workplace=Remoto&seniority=Pleno&stack=Laravel&hours=24&limit=30&offset=0`
- `GET /api/stats`
- `GET /api/companies`
- `GET /api/recruiters`
- `GET /api/clicks?days=7`: cliques nos anúncios originais dos últimos `days` dias (1-365):
  `{"total": N, "by_job": [[job_id, url, n], ...], "by_source": [[fonte, n], ...],
  "by_day": [[dia, n], ...]}` (dia em UTC)

**Cliques**: os links para o anúncio original (LinkedIn, Gupy...) nos cards da home, das
páginas de tema e da página da vaga não apontam direto para a fonte, e sim para
`/out?url=<url codificada>&job=<id>&page=<caminho>&source=<fonte>`. O `/out` grava o clique
e responde `302` para `url` (com `Cache-Control: no-store`); `url` vazia ou que não começa com
`http://`/`https://` volta para a home. Cada clique vira uma linha na tabela `clicks`: quando
(`at`, ISO UTC), id da vaga (`job_id`), destino (`url`), página do site de onde saiu
(`page`) e fonte da vaga (`source`). Nada identifica quem clicou (sem IP nem user agent).
Quem cria a tabela é o coletor; até ele subir com a versão nova, os cliques só geram um
aviso no log e o redirecionamento funciona igual.

**Empresas** (`/empresas`): empresas que mais anunciaram vagas PHP nos portais nos últimos 90
dias (2 ou mais vagas). Nomes escritos de jeitos diferentes são agrupados (`php.company_key`);
vagas confidenciais e sites que repostam vagas (`php.NOT_EMPLOYER`) ficam de fora.

**Recrutadores** (`/recrutadores`): tech recruiters que mais publicaram vagas PHP no LinkedIn
nos últimos 90 dias, reconhecidos pelo headline do autor do post (`php.RECRUITER`). Só entra
quem tem `VAGAS_RECRUITERS_MIN` vagas ou mais (padrão 2). Quem pedir para sair vai em
`VAGAS_RECRUITERS_HIDE` (URLs dos perfis, separadas por vírgula), configurada só no servidor.

**Busca (Google e assistentes de IA)**: as páginas saem já renderizadas no servidor (robôs
que não executam JavaScript leem as vagas), com título, descrição, canonical, Open Graph e
JSON-LD (`web/src/Seo.php`). Páginas para buscadores:

- `/vagas` e `/vagas/<tema>`: vagas abertas por stack, modalidade, senioridade e algumas
  combinações (`/vagas/laravel-remoto`, `/vagas/php-junior`...), com um resumo em números;
  os temas saem da taxonomia do filtro (`php.py`), que o coletor grava em `site_meta`
  (`web/src/Themes.php`).
- `/vaga/<número>-<título>`: uma página por vaga de portal, com JSON-LD `JobPosting` (Google
  for Jobs) enquanto está aberta; depois de 72 h ela fica com `noindex` e sugere vagas
  parecidas (`web/src/Vaga.php`). Posts do LinkedIn não ganham página. O endereço é
  contrato com o coletor, que o anuncia ao Google (Indexing API): os dois lados testam
  contra `contracts/job_paths.json`.
- `/mercado-php`: números do mercado PHP em texto, para citar (`web/src/Mercado.php`).
- `/sitemap.xml`, `/robots.txt` e `/llms.txt`.

O endereço público usado no canonical e no sitemap vem de `VAGAS_SITE_URL` ou, sem ela, dos
cabeçalhos `X-Forwarded-*` do proxy. As ferramentas do WebMCP (`/webmcp.js`) só rodam no
Chrome com o token do *origin trial* da sua origem em `VAGAS_ORIGIN_TRIAL`.

**Preview social** (LinkedIn, Telegram, WhatsApp): todas as páginas saem com `og:image` e
`twitter:image` (card `summary_large_image`) apontando para `/og.png`, que serve
`web/assets/og.png` (1200x630). O LinkedIn guarda o preview em cache; depois de trocar a imagem, force a releitura no
[Post Inspector](https://www.linkedin.com/post-inspector/).

**Google Analytics**: com `VAGAS_GA_ID=G-XXXXXXXXXX` as páginas recebem a tag do GA
(`web/templates/analytics.html`) com aviso de cookies (LGPD, *Consent Mode*): sem aceite,
o GA não grava cookies. Sem a variável (padrão local), nada é carregado. O print do
dashboard para o post diário abre `?print=1`, que fica sem a tag.

## Dashboard

`http://localhost:8780/dashboard` (ou o link no topo do site): vagas abertas,
novas nas últimas 24 h, remotas e empresas; **pizza de vagas por site**; **vagas novas
por dia** (colunas empilhadas por fonte, 7/14/30 dias, dia de Brasília); modalidade,
senioridade, contratação, frameworks e empresas com mais vagas; e a saúde da coleta
de cada fonte. Os números vêm de `GET /api/dashboard?days=14`.

Para mostrar a defasagem dos dados, o topo do dashboard traz a
**última e a próxima captura**, e a tabela de saúde mostra a próxima coleta de cada fonte,
já ajustada à janela de horário. O coletor grava a agenda na base (`site_meta`, nome
`schedule`) a cada minuto. Se ela ficar mais de 5 min sem atualizar, o dashboard avisa que
o coletor parece parado.

## Base de dados (MySQL 8)

As vagas e as execuções ficam num MySQL 8.0.19+ apontado por
`DATABASE_URL=mysql://usuario:senha@host:3306/base` (senha com caracteres especiais vai
codificada, ex.: `@` -> `%40`). Bancos gerenciados (Vultr, RDS...) exigem TLS: acrescente
`?ssl-mode=REQUIRED` (cifra a conexão) ou `?ssl-mode=VERIFY_CA&ssl-ca=/caminho/ca.pem`
(também valida o certificado). O coletor cria as tabelas na subida e espera até 2 min o
banco aceitar conexões; o site só lê (e grava os cliques). Em `data/` continuam só os
arquivos do coletor (`config.json`, posts diários).

No `docker-compose.yml` local o MySQL sobe junto (serviço `mysql`, volume `mysql-data`,
porta `127.0.0.1:3307` para inspecionar) e a `DATABASE_URL` já vem pronta.

Para trazer uma base SQLite antiga (`data/vagas.db`), com o coletor parado:

```bash
docker compose stop vagas-php
docker compose run --rm --no-deps vagas-php migrate-sqlite data/vagas.db   # --force apaga o que já houver no MySQL
docker compose up -d
```

## Produção (Coolify)

A instalação atual (domínio, Cloudflare e Coolify) está descrita em [docs/deploy.md](docs/deploy.md).

Use `docker-compose.coolify.yml`:

1. Use este repositório (ou um fork). O `.gitignore` já tira `.env`, `.session/` e `data/`.
2. No Coolify: *New Resource → Public Repository* (ou *Private Repository*, num fork privado), build pack **Docker Compose**,
   *Docker Compose Location* `/docker-compose.coolify.yml`.
3. Crie no MySQL 8 do outro servidor a base e um usuário com permissão total nela
   (`CREATE DATABASE vagas CHARACTER SET utf8mb4; CREATE USER 'vagas'@'%' IDENTIFIED BY '...';
   GRANT ALL ON vagas.* TO 'vagas'@'%';`) e libere a porta 3306 para o servidor do Coolify.
4. Em *Environment Variables* preencha `DATABASE_URL` (obrigatória), `LINKEDIN_EMAIL`, `LINKEDIN_PASSWORD` e o
   que quiser mudar (os padrões são os do `.env.example`). As publicações (`post`)
   começam **desligadas** (`VAGAS_POSTS_ENABLED=false`).
5. No serviço `web` (o site em PHP), defina o domínio com `https://` (ex.:
   `https://vagas.seudominio.com`). A porta interna 8000 vem de `SERVICE_URL_WEB_8000` no
   compose. O site precisa de `DATABASE_URL` e, se usar, `VAGAS_GA_ID`, `VAGAS_SITE_URL` e
   `VAGAS_ORIGIN_TRIAL`.
6. Deploy. As vagas ficam no MySQL; a sessão do LinkedIn e os arquivos do coletor nos
   volumes `linkedin-session` e `vagas-data`.

Migrando uma instalação que já usava SQLite (a base antiga continua no volume
`vagas-data`): logo depois do deploy, no terminal do serviço `vagas-php` no Coolify, rode
`python -m vagas_php migrate-sqlite /app/data/vagas.db --force`. A cópia é uma transação
só: se falhar (por exemplo, uma coleta gravando ao mesmo tempo), nada muda e basta repetir.
O `--force` descarta só o que o serviço novo gravou desde a subida.

Em produção o servidor MCP começa desligado (`VAGAS_MCP_ENABLED=false`): o serviço só
faz a coleta agendada. Para ligar, defina `VAGAS_MCP_ENABLED=true` e faça novo deploy.

MCP e noVNC não têm senha e ficam só no `127.0.0.1` do servidor. Para entrar no LinkedIn
(fonte `post`), faça `ssh -L 6081:127.0.0.1:6081 servidor`, abra
http://localhost:6081/vnc.html e conclua o login. Depois ligue `VAGAS_POSTS_ENABLED=true`.

## Linha de comando

```bash
docker compose run --rm vagas-php collect all          # ou uma fonte: linkedin | gupy | remotar | ... | post
docker compose run --rm vagas-php list --q laravel --hours 24
docker compose run --rm vagas-php site-data            # regrava o que o site precisa do filtro
```

## Testes

```bash
cd web && composer install && composer test                                   # site (Pest)
cd collector && pip install -r requirements.txt -r requirements-dev.txt && pytest   # coletor
```

O CI (`.github/workflows/ci.yml`) roda os dois a cada push e pull request.

## Observações

- `.env`, `.session/` e `data/` estão no `.gitignore`; trate-os como senhas.
- **Use por sua conta e risco.** O projeto lê páginas e APIs públicas de terceiros:
  respeite os termos de uso e o `robots.txt` de cada site, mantenha os intervalos longos
  e não republique as vagas como se fossem suas. Os dados pertencem aos sites e às
  empresas que publicaram as vagas.
- Automação viola os Termos de Uso do LinkedIn. A fonte `post` usa a sua conta:
  mantenha intervalos longos (mínimo 2 h) ou desligue com `VAGAS_POSTS_ENABLED=false`.
  Só `post` usa a conta; as demais fontes não usam login.
- Portais avaliados e deixados de fora: **Indeed** (sem API nem RSS, bloqueia acesso
  automático com checagem anti-robô), **InfoJobs** e **GeekHunter** (o robots.txt proíbe
  a coleta das vagas).
- O LinkedIn muda o HTML com frequência; se a fonte `post` parar de trazer resultados,
  os seletores ficam em `collector/vagas_php/bot.py`.

## Licença

[MIT](LICENSE).
