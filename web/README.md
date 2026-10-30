# web/ — site do Vagas PHP (PHP 8.5)

Lê as vagas que o coletor (`../collector`, Python) grava no MySQL e serve o site, a API JSON,
o sitemap e as páginas para buscadores. Sem framework: um roteador pequeno
(`src/Http/`), PDO e templates HTML com marcas `<!--ssr:nome-->` que recebem o conteúdo
renderizado no servidor. O contrato com o coletor está em
[`../docs/contrato-base.md`](../docs/contrato-base.md).

```bash
composer install
DATABASE_URL=mysql://vagas:vagas@127.0.0.1:3307/vagas composer serve   # http://127.0.0.1:8780
composer test
```

Extensões: `intl`, `mbstring`, `pdo_mysql`. Variáveis: `DATABASE_URL` (obrigatória),
`VAGAS_SITE_URL`, `VAGAS_GA_ID`, `VAGAS_ORIGIN_TRIAL`, `VAGAS_MAX_AGE_HOURS`,
`VAGAS_RECRUITERS_MIN`, `VAGAS_RECRUITERS_HIDE` (veja o `.env.example` da raiz).

A imagem Docker (`Dockerfile`) usa Apache na porta 8000.
