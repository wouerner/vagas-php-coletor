# vagas-php

Coleta e lista **vagas de engenharia de software com PHP** (PHP, Laravel, Symfony,
CodeIgniter, Hyperf...). Mesma arquitetura do projeto [`../linkedin`](../linkedin)
(Python + Playwright em Docker, servidor MCP, coleta agendada, MySQL 8), com um site
para navegar pelas vagas.

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
(`vagas_php/php.py`):

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
uma regra, atualize o texto dela em `RULES`.

Issues fechadas no GitHub ficam marcadas como encerradas e saem do site.

## Configuração

O `.env` tem as credenciais do LinkedIn (copiadas de `../linkedin/.env`) e os ajustes
das fontes; veja `.env.example`. Ajustes feitos pela ferramenta MCP
`configure_scheduler` ficam em `data/config.json` e têm precedência sobre o `.env`.

## Serviço (Docker)

```bash
docker compose up -d --build   # coletor + site
docker compose logs -f         # acompanha as coletas
docker compose down
```

Portas (escolhidas para rodar junto com o projeto linkedin; só o site fica aberto na rede,
o resto só em `127.0.0.1`):

| | linkedin | vagas-php | variável |
|---|---|---|---|
| site | | `8780`: http://192.168.15.10:8780 (aberto na rede: `WEB_BIND=0.0.0.0` no `.env`) | `WEB_PUBLISH_PORT`, `WEB_BIND` |
| MCP | `8765` | `8766`: http://localhost:8766/mcp | `MCP_PUBLISH_PORT` |
| noVNC | `6080` | `6081`: http://localhost:6081/vnc.html | `NOVNC_PUBLISH_PORT` |
| VNC | `5900` | `5901` | `VNC_PUBLISH_PORT` |

### Sessão do LinkedIn

O container monta `./.session`, um perfil do Chromium próprio, copiado do projeto
`../linkedin` (mude com `LINKEDIN_SESSION_PATH`). Como cada projeto tem a sua trava
`.session/.bot.lock`, os dois podem abrir navegadores ao mesmo tempo na mesma conta.
Para voltar a compartilhar o login e a trava, use
`LINKEDIN_SESSION_PATH=../linkedin/.session`. Se o LinkedIn pedir verificação
(2FA/captcha), conclua pelo noVNC: http://localhost:6081/vnc.html.

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
6 = domingo), um post na conta da sessão do bot (`vagas_php/linkedin_post.py`):

- imagem: print do topo do dashboard (números, vagas por site e vagas novas por dia);
- texto: resumo do dia (vagas abertas, novas em 24 h, remotas, empresas), fontes, filtro,
  hashtags e "Deus seja Louvado" no fim.

Antes de publicar, confere se o texto aparece uma vez só (o LinkedIn pode restaurar um
rascunho) e se a imagem foi anexada; se não, não publica. No máximo um post por dia: se
falhar, tenta de novo a cada 30 min, até 3 vezes, nas 3 h seguintes ao horário. Prévia,
imagem, texto e confirmação de cada dia ficam em `data/linkedin_posts/AAAA-MM-DD/`, e o
histórico em `data/linkedin_posts.json`.

## Site

`http://localhost:8780`: busca por texto e filtros de fonte, modalidade, senioridade,
stack e período (1, 4, 6, 24, 48 ou 72 h; os filtros ficam na URL, para compartilhar). API em JSON:

- `GET /api/jobs?q=laravel&source=github&workplace=Remoto&seniority=Pleno&stack=Laravel&hours=24&limit=30&offset=0`
- `GET /api/stats`

**Google Analytics**: com `VAGAS_GA_ID=G-XXXXXXXXXX` as páginas recebem a tag do GA
(`vagas_php/static/analytics.html`) com aviso de cookies (LGPD, *Consent Mode*): sem aceite,
o GA não grava cookies. Sem a variável (padrão local), nada é carregado. O print do
dashboard para o post diário abre `?print=1`, que fica sem a tag.

## Dashboard

`http://192.168.15.10:8780/dashboard` (ou o link no topo do site): vagas abertas,
novas nas últimas 24 h, remotas e empresas; **pizza de vagas por site**; **vagas novas
por dia** (colunas empilhadas por fonte, 7/14/30 dias, dia de Brasília); modalidade,
senioridade, contratação, frameworks e empresas com mais vagas; e a saúde da coleta
de cada fonte. Os números vêm de `GET /api/dashboard?days=14`.

Para mostrar a defasagem dos dados, o topo do dashboard traz a
**última e a próxima captura**, e a tabela de saúde mostra a próxima coleta de cada fonte,
já ajustada à janela de horário. O coletor grava a agenda em `data/schedule.json` a cada
minuto. Se o arquivo ficar mais de 5 min sem atualizar, o dashboard avisa que o coletor
parece parado.

## Base de dados (MySQL 8)

As vagas e as execuções ficam num MySQL 8.0.19+ apontado por
`DATABASE_URL=mysql://usuario:senha@host:3306/base` (senha com caracteres especiais vai
codificada, ex.: `@` -> `%40`). Bancos gerenciados (Vultr, RDS...) exigem TLS: acrescente
`?ssl-mode=REQUIRED` (cifra a conexão) ou `?ssl-mode=VERIFY_CA&ssl-ca=/caminho/ca.pem`
(também valida o certificado). O coletor cria as tabelas na subida e espera até 2 min o
banco aceitar conexões; o site só lê. Em `data/` continuam só os arquivos do coletor
(`config.json`, `schedule.json`, posts diários).

No `docker-compose.yml` local o MySQL sobe junto (serviço `mysql`, volume `mysql-data`,
porta `127.0.0.1:3307` para inspecionar) e a `DATABASE_URL` já vem pronta.

Para trazer uma base SQLite antiga (`data/vagas.db`), com o coletor parado:

```bash
docker compose stop vagas-php
docker compose run --rm --no-deps vagas-php migrate-sqlite data/vagas.db   # --force apaga o que já houver no MySQL
docker compose up -d
```

## Produção (Coolify)

Use `docker-compose.coolify.yml`:

1. Suba o projeto num repositório Git **privado** (o `.gitignore` já tira `.env`, `.session/` e `data/`).
2. No Coolify: *New Resource → Private Repository*, build pack **Docker Compose**,
   *Docker Compose Location* `/docker-compose.coolify.yml`.
3. Crie no MySQL 8 do outro servidor a base e um usuário com permissão total nela
   (`CREATE DATABASE vagas CHARACTER SET utf8mb4; CREATE USER 'vagas'@'%' IDENTIFIED BY '...';
   GRANT ALL ON vagas.* TO 'vagas'@'%';`) e libere a porta 3306 para o servidor do Coolify.
4. Em *Environment Variables* preencha `DATABASE_URL` (obrigatória), `LINKEDIN_EMAIL`, `LINKEDIN_PASSWORD` e o
   que quiser mudar (os padrões são os do `.env.example`). As publicações (`post`)
   começam **desligadas** (`VAGAS_POSTS_ENABLED=false`).
5. No serviço `web`, defina o domínio com a porta interna: `https://vagas.seudominio.com:8000`.
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
```

## Observações

- `.env`, `.session/` e `data/` estão no `.gitignore`; trate-os como senhas.
- Automação viola os Termos de Uso do LinkedIn. A fonte `post` usa a sua conta:
  mantenha intervalos longos (mínimo 2 h) ou desligue com `VAGAS_POSTS_ENABLED=false`.
  Só `post` usa a conta; as demais fontes não usam login.
- Portais avaliados e deixados de fora: **Indeed** (sem API nem RSS, bloqueia acesso
  automático com checagem anti-robô), **InfoJobs** e **GeekHunter** (o robots.txt proíbe
  a coleta das vagas).
- O LinkedIn muda o HTML com frequência; se a fonte `post` parar de trazer resultados,
  os seletores ficam em `vagas_php/bot.py` (os mesmos do projeto linkedin).
