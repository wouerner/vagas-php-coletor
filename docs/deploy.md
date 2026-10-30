# Deploy em produção

Como o site público está no ar hoje. O passo a passo para montar do zero fica no
[README](../README.md#produção-coolify); aqui ficam as escolhas da instalação atual.

Nada sigiloso entra neste arquivo: senhas, tokens, `DATABASE_URL`, IP do servidor e
IDs internos do Coolify e da Cloudflare ficam só nos painéis.

## Visão geral

```
visitante ──HTTPS──▶ Cloudflare (proxy) ──HTTPS──▶ Traefik (Coolify) ──HTTP:8000──▶ serviço web
                                                                                      │
                                                    serviço vagas-php (coletor) ──────┴──▶ MySQL 8
```

| Peça | O que é |
|---|---|
| Domínio | **https://vagasphp.wouerner.dev** |
| DNS e HTTPS público | Cloudflare, plano Free |
| Servidor e deploy | Coolify, build pack Docker Compose (`docker-compose.coolify.yml`) |
| Proxy reverso | Traefik do Coolify, com certificado Let's Encrypt |
| Base de dados | MySQL 8 em outro servidor (`DATABASE_URL`) |

## Cloudflare

Zona `wouerner.dev`, com os nameservers da Cloudflare.

| Tipo | Nome | Conteúdo | Proxy |
|---|---|---|---|
| A | `vagasphp` | IP do servidor do Coolify | **Proxied** (nuvem laranja) |

- **SSL/TLS: Full.** A Cloudflare fala HTTPS com o servidor. O visitante vê o certificado
  da Cloudflare (renovado por ela), e o trecho Cloudflare → servidor também é cifrado com
  o certificado do Let's Encrypt que o Traefik emite.
  - Não use **Flexible**: o trecho até o servidor ficaria em HTTP puro e o Traefik, que
    redireciona HTTP para HTTPS, entraria em loop.
  - **Full (strict)** também funcionaria com o certificado do Let's Encrypt, mas o modo
    vale para a zona toda e quebraria outros subdomínios dela.
- **Always Use HTTPS: desligado** na zona. O redirecionamento de `http://` para `https://`
  é feito pelo Traefik (o Coolify gera o redirect). Deixar o `http://` chegar no servidor
  também permite que o Let's Encrypt valide o domínio (desafio HTTP-01) com o proxy ligado.
- Com o proxy ligado, o DNS público mostra IPs da Cloudflare, não o do servidor. Por isso
  o IP não fica registrado no repositório.

## Coolify

- Recurso: repositório deste projeto, branch `main`, build pack **Docker Compose**,
  *Docker Compose Location* `/docker-compose.coolify.yml`.
- Domínio do serviço `web` (o site, em PHP, build de `web/`): `https://vagasphp.wouerner.dev`. A porta interna (8000) vem de
  `SERVICE_URL_WEB_8000` no compose, então não precisa ir no domínio. Com `http://` no
  lugar de `https://`, o Traefik não pede certificado e o site responde com o
  "TRAEFIK DEFAULT CERT".
- O serviço `vagas-php` (coletor e MCP, em Python, build de `collector/`) não tem domínio. MCP e noVNC ficam só no
  `127.0.0.1` do servidor (veja o README).
- Variáveis em *Environment Variables*, com os nomes do `.env.example`. A
  `VAGAS_DASHBOARD_URL` (usada pelo post diário do LinkedIn) aponta para
  `https://vagasphp.wouerner.dev/dashboard`. O token do origin trial do WebMCP (expira em
  30/03/2027; renove em https://developer.chrome.com/origintrials) vai em
  `VAGAS_ORIGIN_TRIAL`, no serviço `web`.
- **O deploy não é automático:** um push na `main` não publica nada. Faça o deploy pelo
  painel do Coolify (ou pela API). Quando o serviço sobe, ele reaplica os filtros às vagas
  e aos posts já salvos e regrava o que o site precisa do filtro (`site_meta`), então uma
  mudança de regra em `collector/vagas_php/php.py` vale para a base inteira e para o site.

## Buscadores

- Google Search Console e Bing Webmaster Tools: propriedade `vagasphp.wouerner.dev`
  (verificação por registro TXT na Cloudflare), com o sitemap
  `https://vagasphp.wouerner.dev/sitemap.xml` enviado. A busca do ChatGPT usa o índice do Bing.
- Cloudflare, *Caching → Configuration → Crawler Hints*: ligado, avisa os buscadores
  (IndexNow) quando uma página muda. Não há API para isso; é no painel.
- O `robots.txt` servido é o do site (`/robots.txt`) com os *content signals* da Cloudflare
  por cima (*Managed robots.txt*). Os robôs de IA não são bloqueados (*AI Crawl Control*
  desligado), para o site poder aparecer nas respostas do ChatGPT.

## Conferir depois de um deploy

```bash
curl -sI https://vagasphp.wouerner.dev/ | grep -iE '^(HTTP|server)'   # HTTP/2 200, server: cloudflare
curl -s -o /dev/null -w '%{http_code} %{redirect_url}\n' http://vagasphp.wouerner.dev/   # 302 para https
curl -s https://vagasphp.wouerner.dev/api/stats | head -c 300
```

## Trocar de domínio

1. Na Cloudflare, crie o registro A do novo nome apontando para o servidor, primeiro como
   **DNS only**.
2. No Coolify, troque o domínio do serviço `web` (sempre com `https://`) e faça o deploy.
3. Confira se o servidor já tem certificado do Let's Encrypt para o nome e ligue o proxy
   (**Proxied**).
4. Atualize a `VAGAS_DASHBOARD_URL` no Coolify e no `.env` local, e o domínio no Google
   Analytics (`VAGAS_GA_ID`), se estiver em uso.

O domínio anterior (`*.sslip.io` gerado pelo Coolify) foi desativado. Ele passa a dar 404
se não estiver na lista de domínios do serviço.
