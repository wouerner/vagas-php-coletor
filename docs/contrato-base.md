# Contrato entre o coletor e o site

O coletor (`collector/`, Python) e o site (`web/`, PHP) não se chamam: conversam só pelo
MySQL. Este é o contrato. Mudou algo aqui, mude os dois lados no mesmo pull request.

## Quem escreve o quê

| Tabela | Coletor | Site |
|---|---|---|
| `jobs` | cria, insere e atualiza | lê |
| `runs` | cria e insere (uma linha por coleta) | lê (dashboard, última coleta) |
| `clicks` | cria | insere (`/out`) e lê (`/api/clicks`) |
| `site_meta` | cria e grava | lê |
| `indexing_log` | cria e grava (Indexing API) | não usa |

O coletor cria e migra as tabelas na subida (`Store.__init__`, `SCHEMA` e `_add_columns`
em `collector/vagas_php/store.py`). O site nunca cria tabela: se ela ainda não existe,
responde vazio (`Site::safe()` trata os erros `42S02` e `42S22`).

## Datas

Texto ISO 8601 em UTC com offset, `2026-10-30T12:00:00+00:00`, comparado como string.
O site converte para o horário de Brasília só na hora de mostrar.

## O que o site não calcula

O filtro de PHP (`collector/vagas_php/php.py`) é feito de expressões regulares em Python. O
site não roda o filtro. O coletor grava pronto o que o site precisa dele, em
`Store.publish_site_data()`, na subida do serviço, depois de cada coleta, depois de
`dismiss_job` e com `python -m vagas_php site-data`:

| Onde | Conteúdo | Usado em |
|---|---|---|
| `jobs.company_key` | `php.company_key(company)`: chave para agrupar a mesma empresa; `NULL` = o nome não diz quem contrata | `/empresas`, empresas nas páginas de tema, `hiringOrganization` do JobPosting |
| `jobs.author_recruiter` | `php.is_recruiter(author_headline)`: 1 se o headline do autor do post é de recrutamento | `/recrutadores` |
| `site_meta` `taxonomy` | `{"stacks": [...], "workplaces": [...], "seniorities": [...], "contracts": [...], "sources": [...]}`, na ordem do filtro | temas (`/vagas/<tema>`), validação de `source` |
| `site_meta` `rules` | `php.RULES`: grupo, id, efeito, título, texto e expressões de cada regra | `/regras`, `/api/rules` |
| `site_meta` `rule_counts` | `{"<id da regra>": n}`: quantos itens da base cada regra decidiu | `/regras`, `/api/rules` |
| `site_meta` `schedule` | próximas coletas por fonte (`enabled`, `running`, `interval_hours`, `active_hours`, `next_run`) e `updated_at`; regravado a cada minuto | `/api/dashboard` (`schedule`) |

`site_meta` tem `name` (chave), `value` (JSON) e `updated_at` (ISO UTC).

## Vagas que o site mostra

As duas consultas que definem "vaga aberta" ficam iguais nos dois lados (`DEDUP` em
`store.py` e em `web/src/Repo.php`):

- `relevant = 1 AND dismissed IS NULL AND closed_at IS NULL`;
- `COALESCE(posted_at, first_seen)` dentro de `VAGAS_MAX_AGE_HOURS` (padrão 72 h);
- só a linha mais recente (`max(seq)`) de cada fonte + título + empresa.

## Endereço da página de vaga

`/vaga/<seq>-<slug do título>`, só para vagas de portais (não para `source = 'post'`). O
coletor anuncia essas URLs ao Google (`indexing.job_path`) e o site as serve
(`Seo::jobPath`). Os dois lados testam contra `contracts/job_paths.json`: para mudar o
formato, mude o arquivo e os dois testes.
