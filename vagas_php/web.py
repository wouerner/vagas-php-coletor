"""Site que lista as vagas PHP coletadas. Usa a base do coletor (MySQL) só para leitura.

Rotas: /             página (static/index.html), com as primeiras vagas já no HTML
       /api/jobs     vagas em JSON (filtros: q, source, workplace, seniority, stack, hours,
                     include_closed, limit, offset); `path` é a página da vaga no site
       /api/stats    totais por fonte, vagas abertas (open_total) e últimas coletas
       /vagas        temas (stack, modalidade, senioridade e combinações) com contagem
       /vagas/<tema> vagas abertas de um tema (static/tema.html), ex.: /vagas/laravel-remoto;
                     tema que não existe dá 404 (ver THEMES)
       /dashboard    dashboard (static/dashboard.html)
       /api/dashboard  números do dashboard (days: dias da série diária, 3-90) e próximas coletas
       /regras       regras de filtro (static/regras.html)
       /api/rules    as regras (de php.RULES), quantas vagas cada uma decidiu e as
                     descartadas à mão
       /recrutadores tech recruiters que mais publicam vagas PHP (static/recrutadores.html)
       /api/recruiters  a lista: últimos 90 dias, VAGAS_RECRUITERS_MIN vagas ou mais (padrão
                     2), sem os perfis de VAGAS_RECRUITERS_HIDE (URLs, separadas por vírgula)
       /empresas     empresas que mais anunciam vagas PHP (static/empresas.html)
       /api/companies  a lista: vagas de portais dos últimos 90 dias, 2 ou mais por empresa
       /sitemap.xml  páginas para buscadores (ver SITEMAP_PROVIDERS)
       /robots.txt   tudo liberado menos /api/, com o endereço do sitemap
       /mercado-php  números do mercado PHP em texto (mercado.py), e /llms.txt
       /vaga/<seq>-<título>  página de uma vaga de portal, com JobPosting (vaga.py)

As páginas saem com título, descrição, canonical e JSON-LD (seo.py) e com o conteúdo já
renderizado no servidor: robôs que não executam JavaScript leem as vagas. O JavaScript
das páginas continua atualizando a lista por cima.

Google Analytics: com VAGAS_GA_ID=G-XXXXXXXXXX as páginas recebem a tag (static/analytics.html,
com aviso de consentimento). ?print=1 tira a tag (print do dashboard para o post diário).

Uso: python -m vagas_php.web   (http://WEB_HOST:WEB_PORT/)
"""

import json
import os
import re
import unicodedata
from collections import Counter
from datetime import datetime
from html import escape
from pathlib import Path
from urllib.parse import urlencode

import uvicorn
from pymysql.err import ProgrammingError
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from starlette.routing import Route

from . import dates, mercado, php, seo, vaga
from .store import SOURCES, Store

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("VAGAS_DATA_DIR", ROOT / "data"))
STATIC = Path(__file__).resolve().parent / "static"

_store: Store | None = None



def store() -> Store:
    # Conecta na primeira requisição; as tabelas são criadas pelo coletor.
    global _store
    if _store is None:
        _store = Store(readonly=True, wait=0)
    return _store


def _number(value: str | None, default: float, low: float, high: float) -> float:
    try:
        return min(max(float(value), low), high)
    except (TypeError, ValueError):
        return default


def page(request: Request, name: str) -> HTMLResponse:
    """Página estática sem conteúdo renderizado no servidor (só a tag do GA)."""
    html = (STATIC / name).read_text()
    if seo.GA_ID and "print" not in request.query_params:
        tag = (STATIC / "analytics.html").read_text().replace("{GA_ID}", seo.GA_ID)
        html = html.replace("</head>", tag + "</head>", 1)
    return HTMLResponse(html)


# --- cards de vaga renderizados no servidor -------------------------------------------
# Mesmo HTML que card() de static/index.html monta no navegador: o JavaScript troca a
# lista inicial pela dele sem mudar nada na tela. Mudou um, mude o outro.

SOURCE_NAMES = {"linkedin": "Vaga LinkedIn", "gupy": "Gupy", "post": "Publicação LinkedIn",
                "github": "GitHub", "inhire": "InHire", "solides": "Sólides", "catho": "Catho",
                "remotar": "Remotar", "programathor": "Programathor", "coodesh": "Coodesh",
                "nerdin": "Nerdin", "recrutei": "Recrutei", "upvagas": "UpVagas"}
# Idade da vaga: até quantas horas, classe do card e nome da faixa.
AGE_BANDS = [(6, "new", "nova"), (24, "recent", "recente"), (48, "days", "1-2 dias"),
             (float("inf"), "old", "antiga")]
PAGE = 30  # vagas na primeira página da home (o mesmo PAGE do JavaScript)


def _when(iso: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return None


def _age(iso: str | None) -> dict | None:
    """Texto curto ("40 min", "5 h", "1 d 3 h"), faixa de cor e data em Brasília."""
    if not (when := _when(iso)):
        return None
    minutes = max(0, int((dates.now_utc() - when).total_seconds() // 60))
    h = minutes / 60
    text = (f"{minutes} min" if minutes < 60 else f"{int(h)} h" if h < 24
            else f"{int(h // 24)} d" + (f" {int(h % 24)} h" if int(h % 24) else ""))
    band, label = next((band, label) for limit, band, label in AGE_BANDS if h < limit)
    return {"text": text, "band": band, "label": label,
            "at": when.astimezone(dates.BRASILIA).strftime("%d/%m, %H:%M")}


def _ago(iso: str | None) -> str | None:
    if not (when := _when(iso)):
        return None
    h = int((dates.now_utc() - when).total_seconds() // 3600)
    return "há menos de 1 h" if h < 1 else f"há {h} h" if h < 48 else f"há {h // 24} dias"


def _safe_url(url: str | None) -> str | None:
    return url if url and re.match(r"https?://", url, re.I) else None


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def _fmt(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def with_path(rows: list[dict]) -> list[dict]:
    """Acrescenta `path`, a página da vaga no site (None para posts do LinkedIn)."""
    return [{**r, "path": seo.job_path(r)} for r in rows]


def job_card(job: dict) -> str:
    e = escape
    url, path = _safe_url(job.get("url")), job.get("path")
    title = e(job.get("title") or "(sem título)")
    who = " · ".join(x for x in (job.get("company"),
                                 job.get("author") if job.get("source") == "post" else None,
                                 job.get("location")) if x)
    a = _age(job.get("posted_at") or job.get("first_seen"))
    tags = [f'<span class="tag src">{e(SOURCE_NAMES.get(job["source"], job["source"]))}</span>']
    if job.get("closed_at"):
        tags.append('<span class="tag closed">encerrada</span>')
    if job.get("workplace"):
        remote = " remote" if job["workplace"] == "Remoto" else ""
        tags.append(f'<span class="tag{remote}">{e(job["workplace"])}</span>')
    for t in (job.get("seniority"), job.get("contract"), job.get("salary"),
              *(job.get("stack") or "").split(",")):
        if t:
            tags.append(f'<span class="tag">{e(t)}</span>')
    # Vaga de portal: o título leva à página da vaga no site e o anúncio original fica
    # na linha de baixo. Post do LinkedIn: o título leva ao post.
    if path:
        link = f'<a class="page" href="{e(path)}">{title}</a>'
    elif url:
        link = f'<a href="{e(url)}" target="_blank" rel="noopener">{title}</a>'
    else:
        link = title
    meta = e(" · ".join(x for x in (who, a and f"publicada em {a['at']} (Brasília)") if x))
    if path and url:
        meta += (" · " if meta else "") + (f'<a href="{e(url)}" target="_blank" '
                                          f'rel="noopener">ver anúncio original</a>')
    age = (f'<span class="age" title="Vaga {a["label"]}: publicada há {a["text"]}">'
           f'{a["text"]}</span>') if a else ""
    desc = (f'<details><summary>Descrição</summary><div class="desc">{e(job["description"])}'
            f'</div></details>') if job.get("description") else ""
    band = f" {a['band']}" if a else ""
    return (f'<li class="job{band}" data-id="{e(job["id"])}"><div class="head"><h2>{link}</h2>'
            f'{age}</div><div class="meta">{meta}</div><div class="tags">{"".join(tags)}</div>'
            f'{desc}</li>')


def open_jobs() -> list[dict]:
    """Todas as vagas abertas (últimas 72 h, sem repetidas), com `path`."""
    try:
        return with_path(store().query_jobs(limit=1000))
    except ProgrammingError:  # tabelas ainda não criadas pelo coletor
        return []


def _job_list(request: Request, name: str, jobs: list[dict]) -> dict:
    """JSON-LD ItemList das vagas de uma página (página da vaga no site, ou o post)."""
    base = seo.site_url(request)
    return {"@context": "https://schema.org", "@type": "ItemList", "name": name,
            "numberOfItems": len(jobs),
            "itemListElement": [{"@type": "ListItem", "position": i,
                                 "url": base + j["path"] if j["path"] else _safe_url(j["url"]),
                                 "name": j.get("title") or "(sem título)"}
                                for i, j in enumerate(jobs, 1)]}


# --- páginas por tema (/vagas/laravel-remoto) -----------------------------------------
# Uma por stack, modalidade e senioridade (de php.py) e as combinações abaixo, que têm
# volume de vagas para valer uma página. Endereços estáveis: tema sem vaga aberta continua
# existindo, com o aviso e os temas relacionados.

THEME_STACK_WORKPLACE = {"Laravel": ("Remoto", "Híbrido", "Presencial"), "Symfony": ("Remoto",),
                         "WordPress": ("Remoto",), "Magento": ("Remoto",),
                         "CodeIgniter": ("Remoto",), "Drupal": ("Remoto",)}
THEME_STACK_SENIORITY = {"Laravel": ("Júnior", "Pleno", "Sênior")}
THEME_SENIORITY_WORKPLACE = {"Júnior": ("Remoto",), "Pleno": ("Remoto",), "Sênior": ("Remoto",)}
WORKPLACE_PLURAL = {"Remoto": "remotas", "Híbrido": "híbridas", "Presencial": "presenciais"}
THEME_GROUPS = ("Por stack", "Por modalidade", "Por senioridade", "Combinações")


def _theme_name(stack: str | None, workplace: str | None, seniority: str | None) -> str:
    """"Vagas Laravel remotas", "Vagas PHP sênior remotas", "Vagas de estágio em PHP"."""
    tech = stack or "PHP"
    if seniority == "Estágio":
        name = f"Vagas de estágio em {tech}"
    else:
        name = " ".join(x for x in ("Vagas", tech, seniority and seniority.lower()) if x)
    if workplace:
        name += " " + WORKPLACE_PLURAL.get(workplace, workplace.lower())
    return name


def _build_themes() -> tuple[dict[str, dict], dict[str, str]]:
    """Temas por slug e os apelidos (/vagas/junior -> /vagas/php-junior: toda vaga do site
    é PHP, as duas seriam a mesma página)."""
    stacks = [s for s in php.PHP_STACK if s != "PHP"]
    workplaces = [label for label, _ in php.WORKPLACE]
    levels = [label for label, _ in php.SENIORITY]
    combos = ([(0, s, None, None) for s in stacks]
              + [(1, None, w, None) for w in workplaces]
              + [(2, None, None, lv) for lv in levels]
              + [(3, s, w, None) for s, ws in THEME_STACK_WORKPLACE.items() for w in ws]
              + [(3, s, None, lv) for s, lvs in THEME_STACK_SENIORITY.items() for lv in lvs]
              + [(3, None, w, lv) for lv, ws in THEME_SENIORITY_WORKPLACE.items() for w in ws])
    themes, aliases = {}, {}
    for group, stack, workplace, level in combos:
        assert stack in stacks + [None] and workplace in workplaces + [None] \
            and level in levels + [None], (stack, workplace, level)
        parts = (seo.slugify(stack) if stack else "php" if level else None,
                 level and seo.slugify(level), workplace and seo.slugify(workplace))
        slug = "-".join(p for p in parts if p)
        themes[slug] = {"slug": slug, "path": f"/vagas/{slug}", "group": THEME_GROUPS[group],
                        "name": _theme_name(stack, workplace, level),
                        "stack": stack, "workplace": workplace, "seniority": level}
    for level in levels:
        aliases[seo.slugify(level)] = f"php-{seo.slugify(level)}"
    return themes, aliases


THEMES, THEME_ALIASES = _build_themes()


def _matches(theme: dict, job: dict) -> bool:
    return ((not theme["stack"] or theme["stack"] in (job.get("stack") or "").split(","))
            and (not theme["workplace"] or job.get("workplace") == theme["workplace"])
            and (not theme["seniority"] or job.get("seniority") == theme["seniority"]))


def _dims(theme: dict) -> set:
    return {(k, theme[k]) for k in ("stack", "workplace", "seniority") if theme[k]}


def _related(theme: dict, counts: Counter, limit: int = 16) -> list[dict]:
    """Temas com vaga aberta mais gerais (Laravel para Laravel remotas), mais específicos e
    vizinhos (mesmo tipo de filtro, um valor diferente: Symfony remotas)."""
    mine = _dims(theme)

    def rank(other):
        dims = _dims(other)
        if dims < mine:
            return 0
        if dims > mine:
            return 1
        if {k for k, _ in dims} == {k for k, _ in mine} and len(dims & mine) == len(mine) - 1:
            return 2
        return None

    near = [(r, t) for t in THEMES.values() if t is not theme and (r := rank(t)) is not None]
    near = [(r, t) for r, t in near if counts[t["slug"]]]
    near.sort(key=lambda rt: (rt[0], -counts[rt[1]["slug"]]))
    return [t for _, t in near[:limit]]


def _theme_links(themes, counts: Counter) -> str:
    return "".join(f'<a href="{t["path"]}"{"" if counts[t["slug"]] else " class=zero"}>'
                   f'{escape(t["name"])} <span class="n">{counts[t["slug"]]}</span></a>'
                   for t in themes)


def _theme_counts(jobs: list[dict]) -> Counter:
    return Counter(t["slug"] for t in THEMES.values() for j in jobs if _matches(t, j))


def _top_companies(jobs: list[dict], n: int = 5) -> list[tuple[str, int]]:
    """Empresas com mais vagas, agrupadas como na página /empresas (php.company_key). Issues
    do GitHub ficam de fora: a "empresa" delas sai do título e muitas vezes é o local."""
    names, count = {}, Counter()
    for j in jobs:
        if j["source"] != "github" and (key := php.company_key(j.get("company"))):
            names.setdefault(key, j["company"].strip())
            count[key] += 1
    return [(names[k], c) for k, c in count.most_common(n)]


def _and(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " e " + items[-1]


def _theme_intro(theme: dict, jobs: list[dict], last_90: int) -> tuple[str, str]:
    """Parágrafos da página (HTML) e a meta description, com os números atuais."""
    name = theme["name"][0].lower() + theme["name"][1:]
    tech = theme["stack"] or "PHP"
    hours = int(dates.MAX_AGE_HOURS)
    about = (f"Vagas de engenharia de software com {escape(tech)} coletadas do LinkedIn, Gupy, "
             f"Sólides, Catho, Remotar, Programathor, Coodesh e de outros sites de vagas, além "
             f"de publicações de recrutadores. A lista é atualizada várias vezes por dia.")
    history = (f"Nos últimos 90 dias o site recebeu {_plural(last_90, 'vaga', 'vagas')} deste tema."
               if last_90 else "")
    if not jobs:
        text = (f"<p>Não há {escape(name)} abertas agora (publicadas nas últimas {hours} horas). "
                f"{history} Veja os temas relacionados abaixo ou "
                f'<a href="/">todas as vagas PHP</a>.</p><p>{about}</p>')
        desc = (f"{theme['name']}: nenhuma aberta nas últimas {hours} h. "
                + (f"{last_90} nos últimos 90 dias. " if last_90 else "")
                + "Veja vagas PHP relacionadas, atualizadas várias vezes por dia.")
        return text, desc
    n = len(jobs)
    facts = [f"<b>{_plural(n, 'vaga aberta', 'vagas abertas')}</b>, publicadas nas últimas "
             f"{hours} horas."]
    if not theme["workplace"]:
        remote = sum(j.get("workplace") == "Remoto" for j in jobs)
        facts.append(f"{round(100 * remote / n)}% são remotas ({remote} de {n}).")
    contracts = Counter(j["contract"] for j in jobs if j.get("contract")).most_common()
    if contracts:
        rest = n - sum(c for _, c in contracts)
        facts.append("Contratação: " + _and([f"{k} ({c})" for k, c in contracts])
                     + (f"; {_plural(rest, 'não informa', 'não informam')}." if rest else "."))
    if not theme["seniority"]:
        levels = Counter(j["seniority"] for j in jobs if j.get("seniority")).most_common()
        if levels:
            rest = n - sum(c for _, c in levels)
            facts.append("Senioridade: " + _and([f"{k.lower()} ({c})" for k, c in levels])
                         + (f"; {_plural(rest, 'não informa', 'não informam')}." if rest else "."))
    companies = _top_companies(jobs)
    if companies:
        facts.append("Empresas que mais anunciam: "
                     + _and([escape(f"{c} ({k})" if k > 1 else c) for c, k in companies]) + ".")
    text = f"<p>{' '.join(facts)} {history}</p><p>{about}</p>"
    desc = (f"{n} {name} abertas, publicadas nas últimas {hours} h" if n > 1
            else f"{theme['name']}: 1 aberta, publicada nas últimas {hours} h")
    if not theme["workplace"]:
        desc += f", {round(100 * sum(j.get('workplace') == 'Remoto' for j in jobs) / n)}% remotas"
    if companies:
        desc += ". Empresas: " + _and([c for c, _ in companies[:3]])
    return text, desc + ". Atualizado várias vezes por dia."


def _facets() -> list[dict]:
    try:
        return store().job_facets(90)
    except ProgrammingError:
        return []


def _theme_html(request: Request, *, title: str, description: str, path: str, h1: str,
                crumb: str, intro: str, jobs: list[dict], more: str, related: str,
                jsonld=None, noindex: bool = False, status: int = 200) -> HTMLResponse:
    content = {"h1": escape(h1), "crumb": crumb, "intro": intro,
               "list": "".join(job_card(j) for j in jobs), "more": more, "related": related}
    return HTMLResponse(seo.render(request, "tema.html", title=title, description=description,
                                   path=path, content=content, jsonld=jsonld, noindex=noindex),
                        status_code=status)


def _all_themes_html(counts: Counter) -> str:
    out = []
    for group in THEME_GROUPS:
        themes = [t for t in THEMES.values() if t["group"] == group]
        out.append(f'<section class="themes"><h2>{group}</h2>'
                   f'<nav>{_theme_links(themes, counts)}</nav></section>')
    return "".join(out)


async def themes_page(request: Request):
    jobs = open_jobs()
    counts = _theme_counts(jobs)
    title = "Vagas PHP por tema: Laravel, Symfony, WordPress, remotas, júnior e sênior | Vagas PHP"
    description = (f"{len(jobs)} vagas PHP abertas agora, separadas por stack (Laravel, Symfony, "
                   f"WordPress, Magento...), modalidade (remoto, híbrido, presencial) e senioridade.")
    base = seo.site_url(request)
    jsonld = [seo.breadcrumbs(request, ("Vagas PHP", "/"), ("Temas", "/vagas")),
              {"@context": "https://schema.org", "@type": "ItemList", "name": "Vagas PHP por tema",
               "itemListElement": [{"@type": "ListItem", "position": i, "url": base + t["path"],
                                    "name": t["name"]}
                                   for i, t in enumerate(THEMES.values(), 1)]}]
    intro = (f"<p>As <b>{_plural(len(jobs), 'vaga aberta', 'vagas abertas')}</b> do site "
             f"(publicadas nas últimas {int(dates.MAX_AGE_HOURS)} horas), separadas por tema. "
             f"O número ao lado de cada tema é quantas estão abertas agora.</p>")
    return _theme_html(request, title=title, description=description, path="/vagas",
                       h1="Vagas PHP por tema", crumb="Temas", intro=intro, jobs=[], more="",
                       related=_all_themes_html(counts), jsonld=jsonld)


async def theme_page(request: Request):
    slug = request.path_params["slug"]
    if slug in THEME_ALIASES:
        return RedirectResponse(f"/vagas/{THEME_ALIASES[slug]}", status_code=301)
    jobs = open_jobs()
    counts = _theme_counts(jobs)
    if not (theme := THEMES.get(slug)):
        intro = '<p>Esse tema não existe. Escolha um dos temas abaixo ou veja <a href="/">todas as vagas PHP</a>.</p>'
        return _theme_html(request, title="Tema não encontrado | Vagas PHP",
                           description="Tema de vagas PHP não encontrado.", path="/vagas",
                           h1="Tema não encontrado", crumb='<a href="/vagas">Temas</a>',
                           intro=intro, jobs=[], more="", related=_all_themes_html(counts),
                           noindex=True, status=404)
    mine = [j for j in jobs if _matches(theme, j)][:100]
    last_90 = sum(_matches(theme, j) for j in _facets())
    intro, description = _theme_intro(theme, mine, last_90)
    title = (f"{theme['name']}: {_plural(len(mine), 'aberta', 'abertas')} agora | Vagas PHP"
             if mine else f"{theme['name']} | Vagas PHP")
    params = {k: theme[k] for k in ("stack", "workplace", "seniority") if theme[k]}
    more = (f'<a href="/?{escape(urlencode(params))}">Ver na página inicial, com filtros e '
            f'atualização automática</a>') if mine else ""
    related = (f'<section class="themes"><h2>Temas relacionados</h2><nav>'
               f'{_theme_links(_related(theme, counts), counts)}'
               f'<a href="/vagas">Todos os temas</a></nav></section>')
    jsonld = [seo.breadcrumbs(request, ("Vagas PHP", "/"), ("Temas", "/vagas"),
                              (theme["name"], theme["path"]))]
    if mine:
        jsonld.append(_job_list(request, theme["name"], mine))
    return _theme_html(request, title=title, description=description, path=theme["path"],
                       h1=theme["name"], crumb=f'<a href="/vagas">Temas</a> › {escape(theme["name"])}',
                       intro=intro, jobs=mine, more=more, related=related, jsonld=jsonld)


# --- páginas ---------------------------------------------------------------------------

def _job_filters(p) -> dict:
    """Filtros de /api/jobs (e da home, que mostra a mesma lista no HTML)."""
    return dict(q=p.get("q") or None, workplace=p.get("workplace") or None,
                seniority=p.get("seniority") or None, stack=p.get("stack") or None,
                hours=_number(p.get("hours"), 72, 1, 72),
                include_closed=p.get("include_closed") in ("1", "true"))


def _form_state(html: str, p) -> str:
    """Marca no formulário da home os filtros da URL (/?stack=Laravel), para a página sem
    JavaScript mostrar o que a lista está filtrando. O JavaScript lê os mesmos da URL."""
    for name in ("workplace", "seniority", "stack", "hours"):
        if not (value := p.get(name)):
            continue
        m = re.search(rf'<select name="{name}".*?</select>', html, re.S)
        options = re.sub(r" selected(?=>)", "", m.group(0))
        # <option>Remoto</option> ou <option value="24">...</option>
        chosen = re.sub(rf'<option( value="{re.escape(escape(value))}")?>(?(1)|{re.escape(escape(value))}<)',
                        lambda o: o.group(0).replace("<option", "<option selected", 1), options, count=1)
        if chosen != options:
            html = html[:m.start()] + chosen + html[m.end():]
    if (source := p.get("source")) in SOURCES:
        html = html.replace('name="source" value="" checked', 'name="source" value=""', 1)
        html = html.replace(f'name="source" value="{source}"', f'name="source" value="{source}" checked', 1)
    if q := p.get("q"):
        html = html.replace('<input type="search" name="q"', f'<input type="search" name="q" value="{escape(q)}"', 1)
    return html


async def index(request: Request):
    p = request.query_params
    source = p.get("source") if p.get("source") in SOURCES else None
    try:
        rows = with_path(store().query_jobs(source=source, **_job_filters(p), limit=PAGE))
        st = store().stats()
    except ProgrammingError:
        rows, st = [], {"open_total": 0, "last_runs": {}}
    total = st["open_total"]
    stats_html = f"<span><b>{total}</b> vagas abertas na base</span>"
    runs = sorted(r["finished_at"] for r in st["last_runs"].values() if r and r["ok"])
    if runs:
        stats_html += f"<span>última coleta {escape(_ago(runs[-1]) or '')}</span>"
    counts = _theme_counts(open_jobs())  # contagem dos temas: sempre sem filtro
    singles = [t for t in THEMES.values() if t["group"] != "Combinações"]
    themes_html = _theme_links(singles, counts) + '<a href="/vagas">Todos os temas</a>'
    title = "Vagas PHP, Laravel e Symfony — remotas e no Brasil | Vagas PHP"
    description = (f"{total} vagas PHP abertas, publicadas nas últimas {int(dates.MAX_AGE_HOURS)} h: "
                   f"Laravel, Symfony, WordPress e mais, remotas, híbridas e presenciais. "
                   f"Do LinkedIn, Gupy, Sólides, Catho, Remotar e outros sites, atualizadas "
                   f"várias vezes por dia.")
    base = seo.site_url(request)
    jsonld = [{"@context": "https://schema.org", "@type": "WebSite", "name": seo.SITE_NAME,
               "url": base + "/", "inLanguage": "pt-BR"},
              _job_list(request, "Vagas PHP abertas", rows)]
    html = seo.render(request, "index.html", title=title, description=description, path="/",
                      content={"list": "".join(job_card(j) for j in rows)
                               or '<li class="empty">Nenhuma vaga encontrada com esses filtros.</li>',
                               "stats": stats_html, "themes": themes_html},
                      jsonld=jsonld)
    return HTMLResponse(_form_state(html, p))


async def jobs(request: Request):
    p = request.query_params
    source = p.get("source") or None
    if source and source not in SOURCES:
        return JSONResponse({"error": f"source deve ser {', '.join(SOURCES)}"}, status_code=400)
    limit = int(_number(p.get("limit"), 50, 1, 200))
    try:
        rows = store().query_jobs(source=source, **_job_filters(p), limit=limit + 1,
                                  offset=int(_number(p.get("offset"), 0, 0, 1e6)))
    except ProgrammingError:  # tabelas ainda não criadas pelo coletor
        rows = []
    return JSONResponse({"jobs": with_path(rows[:limit]), "has_more": len(rows) > limit,
                         "max_age_hours": dates.MAX_AGE_HOURS})


async def dashboard_page(request: Request):
    try:
        total = store().open_count()
    except ProgrammingError:
        total = 0
    description = (f"Mercado de vagas PHP em números: {total} vagas abertas nas últimas "
                   f"{int(dates.MAX_AGE_HOURS)} h, vagas novas por dia, por site, modalidade, "
                   f"senioridade, contratação, stack e empresas.")
    return HTMLResponse(seo.render(
        request, "dashboard.html", path="/dashboard", description=description,
        title="Dashboard de vagas PHP: vagas por dia, stack e modalidade | Vagas PHP",
        jsonld=seo.breadcrumbs(request, ("Vagas PHP", "/"), ("Dashboard", "/dashboard"))))


def schedule() -> dict | None:
    """Próximas coletas, gravadas pelo coletor em data/schedule.json (a cada minuto)."""
    try:
        return json.loads((DATA_DIR / "schedule.json").read_text())
    except (OSError, ValueError):
        return None


async def dashboard(request: Request):
    days = int(_number(request.query_params.get("days"), 14, 3, 90))
    try:
        return JSONResponse({**store().dashboard(days), "schedule": schedule()})
    except ProgrammingError:
        return JSONResponse({"error": "base ainda vazia"}, status_code=503)


# Grupos da página /regras: id em php.RULES, título e explicação.
RULE_GROUPS = [
    ("vagas", "Vagas de portais", "LinkedIn Vagas, Gupy, Sólides, Catho, Remotar, Programathor, "
     "Coodesh, Nerdin, Recrutei, UpVagas, páginas de carreira de empresas na InHire e issues dos "
     "repositórios de vagas no GitHub."),
    ("posts", "Publicações do LinkedIn", "Posts que anunciam vagas. Precisam falar de PHP, "
     "anunciar uma vaga e não ser outra coisa."),
    ("empresas", "Empresas", "Quem aparece na página de empresas, entre as vagas de portais aceitas."),
    ("recrutadores", "Recrutadores", "Quem aparece na página de recrutadores, entre os autores das "
     "publicações aceitas."),
]


def _alternatives(rx: str) -> list[str]:
    """Separa uma expressão regular nas alternativas de primeiro nível ("a|b|(c|d)" -> a, b,
    (c|d)), tirando o grupo e os \\b que envolvem tudo: fica mais fácil de ler."""
    s = rx.removeprefix("\\b").removesuffix("\\b")
    if s.startswith("(") and s.endswith(")"):
        depth, i, wrapped = 0, 0, True
        while i < len(s):
            if s[i] == "\\":
                i += 2
                continue
            if s[i] == "(":
                depth += 1
            elif s[i] == ")":
                depth -= 1
                if depth == 0 and i < len(s) - 1:
                    wrapped = False
                    break
            i += 1
        if wrapped:
            s = s[1:-1].removeprefix("?:")
    parts, depth, cur, i = [], 0, "", 0
    while i < len(s):
        c = s[i]
        if c == "\\":
            cur += s[i:i + 2]
            i += 2
            continue
        if c in "([":
            depth += 1
        elif c in ")]":
            depth -= 1
        if c == "|" and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += c
        i += 1
    parts.append(cur)
    return [p for p in parts if p]


def _rules_html(counts: dict) -> str:
    out = []
    for key, title, note in RULE_GROUPS:
        out.append(f'<h2>{escape(title)}</h2><p class="group-note">{escape(note)}</p>')
        for i, r in enumerate((r for r in php.RULES if r["group"] == key), 1):
            n = counts.get(r["id"])
            badge = "✓ aceita" if r["effect"] == "aceita" else "✕ recusa"
            count = f'<span class="count">{_fmt(n)} na base</span>' if n is not None else ""
            chips = "".join(f"<code>{escape(a)}</code>" for p in r["patterns"]
                            for a in _alternatives(p))
            details = (f'<details><summary>Expressões usadas</summary><div class="chips">{chips}'
                       f'</div></details>') if r["patterns"] else ""
            out.append(f'<section class="card rule"><div class="n">{i}</div><div><h3>'
                       f'{escape(r["title"])}<span class="badge {r["effect"]}">{badge}</span>'
                       f'{count}</h3><p>{escape(r["text"])}</p>{details}</div></section>')
    return "".join(out)


def _dismissed_html(dismissed: list[dict]) -> str:
    if not dismissed:
        return '<p style="margin:0;color:var(--muted)">Nenhuma até agora.</p>'
    rows = ["<table><tr><th>Quando</th><th>Item</th><th>Motivo</th></tr>"]
    for j in dismissed:
        at, _, reason = j["dismissed"].partition(" ")
        when = _when(at)
        when = when.astimezone(dates.BRASILIA).strftime("%d/%m/%Y %H:%M") if when else at
        url, title = _safe_url(j.get("url")), escape(j.get("title") or j.get("url") or "—")
        item = f'<a href="{escape(url)}" target="_blank" rel="noopener">{title}</a>' if url else title
        rows.append(f"<tr><td>{escape(when)}</td><td>{item}</td><td>{escape(reason or '—')}</td></tr>")
    return "".join(rows) + "</table>"


async def rules_page(request: Request):
    try:
        stats = store().rule_stats()
    except ProgrammingError:
        stats = {"counts": {}, "dismissed": []}
    html = seo.render(
        request, "regras.html", path="/regras",
        title="Como as vagas PHP são filtradas: as regras do site | Vagas PHP",
        description="As regras que decidem quais vagas e publicações de PHP, Laravel e Symfony "
                    "aparecem no site, geradas do próprio código do filtro, e os sites que não "
                    "coletamos.",
        content={"max_age": str(int(dates.MAX_AGE_HOURS)), "groups": _rules_html(stats["counts"]),
                 "dismissed": _dismissed_html(stats["dismissed"])},
        jsonld=seo.breadcrumbs(request, ("Vagas PHP", "/"), ("Regras", "/regras")))
    return HTMLResponse(html)


async def rules(request: Request):
    try:
        stats = store().rule_stats()
    except ProgrammingError:
        stats = {"counts": {}, "dismissed": []}
    return JSONResponse({"rules": php.RULES, **stats, "max_age_hours": dates.MAX_AGE_HOURS})


RECRUITERS_DAYS = 90
RECRUITERS_MIN = max(int(os.getenv("VAGAS_RECRUITERS_MIN") or 2), 1)
RECRUITERS_HIDE = [u.strip() for u in os.getenv("VAGAS_RECRUITERS_HIDE", "").split(",") if u.strip()]


def _br_date(iso: str | None) -> str:
    when = _when(iso)
    return when.astimezone(dates.BRASILIA).strftime("%d/%m/%Y") if when else ""


def _recruiters() -> list[dict]:
    try:
        return store().recruiters(RECRUITERS_DAYS, RECRUITERS_MIN, RECRUITERS_HIDE)
    except ProgrammingError:
        return []


def _recruiter_card(p: dict, i: int) -> str:
    e = escape
    url = _safe_url(p["url"])
    name = e(p["name"] or p["url"])
    name = f'<a href="{e(url)}" target="_blank" rel="nofollow noopener">{name}</a>' if url else name
    headline = f'<p class="headline">{e(p["headline"])}</p>' if p["headline"] else ""
    chips = (f'<div class="chips">{"".join(f"<span class=chip>{e(s)}</span>" for s in p["stack"])}'
             f'</div>') if p["stack"] else ""
    return (f'<section class="card person"><div class="n">{i}</div><div><h2>{name}</h2>'
            f'{headline}<p class="meta">Última vaga em {_br_date(p["last_posted"])}</p>{chips}'
            f'</div><div class="jobs"><b>{p["jobs"]}</b><span>{"vaga" if p["jobs"] == 1 else "vagas"}'
            f'</span></div></section>')


async def recruiters_page(request: Request):
    people = _recruiters()
    cards = "".join(_recruiter_card(p, i) for i, p in enumerate(people, 1)) or (
        '<section class="card"><p style="margin:0;color:var(--muted)">Ainda não há recrutadores '
        'com vagas suficientes no período. Volte em alguns dias.</p></section>')
    description = (f"{_plural(len(people), 'tech recruiter', 'tech recruiters')} que mais "
                   f"publicaram vagas PHP, Laravel e Symfony no LinkedIn nos últimos "
                   f"{RECRUITERS_DAYS} dias. Siga esses perfis para ver as vagas assim que saem.")
    html = seo.render(
        request, "recrutadores.html", path="/recrutadores", description=description,
        title="Tech recruiters de vagas PHP para seguir no LinkedIn | Vagas PHP",
        content={"list": cards, "days": str(RECRUITERS_DAYS), "min": str(RECRUITERS_MIN)},
        jsonld=seo.breadcrumbs(request, ("Vagas PHP", "/"), ("Recrutadores", "/recrutadores")))
    return HTMLResponse(html)


async def recruiters(request: Request):
    return JSONResponse({"recruiters": _recruiters(), "days": RECRUITERS_DAYS,
                         "min_jobs": RECRUITERS_MIN})


COMPANIES_DAYS, COMPANIES_MIN = 90, 2


def _companies() -> list[dict]:
    try:
        return store().companies(COMPANIES_DAYS, COMPANIES_MIN)
    except ProgrammingError:
        return []


def _fold(text: str) -> str:
    """Sem acentos e minúsculo, para a busca da página /empresas."""
    return "".join(c for c in unicodedata.normalize("NFD", text)
                   if not unicodedata.combining(c)).lower()


def _company_card(c: dict, i: int) -> str:
    e = escape
    remote = dict(c["workplace"]).get("Remoto")
    meta = [f"Última vaga em {_br_date(c['last_posted'])}"]
    if remote:
        meta.append("todas remotas" if remote == c["jobs"] else _plural(remote, "remota", "remotas"))
    chips = [*c["stack"], *(SOURCE_NAMES.get(s, s).removeprefix("Vaga ") for s in c["sources"])]
    open_link = ""
    when = _when(c["last_posted"])
    if when and (dates.now_utc() - when).total_seconds() < dates.MAX_AGE_HOURS * 3600:
        open_link = f'<p class="meta"><a href="/?{e(urlencode({"q": c["name"]}))}">Ver vagas abertas</a></p>'
    text = _fold(" ".join([c["name"], *c["stack"], *c["sources"], *(w for w, _ in c["workplace"])]))
    return (f'<section class="card company" data-text="{e(text)}"><div class="n">{i}</div><div>'
            f'<h2>{e(c["name"])}</h2><p class="meta">{e(" · ".join(meta))}</p><div class="chips">'
            f'{"".join(f"<span class=chip>{e(s)}</span>" for s in chips)}</div>{open_link}</div>'
            f'<div class="jobs"><b>{c["jobs"]}</b><span>{"vaga" if c["jobs"] == 1 else "vagas"}'
            f'</span></div></section>')


async def companies_page(request: Request):
    rows = _companies()
    cards = "".join(_company_card(c, i) for i, c in enumerate(rows, 1)) or (
        '<section class="card"><p style="margin:0;color:var(--muted)">Ainda não há empresas com '
        'vagas suficientes no período.</p></section>')
    top = _and([f"{c['name']} ({c['jobs']})" for c in rows[:3]]) if rows else ""
    description = (f"Ranking de {_plural(len(rows), 'empresa', 'empresas')} que mais anunciaram "
                   f"vagas PHP, Laravel e Symfony nos últimos {COMPANIES_DAYS} dias"
                   + (f": {top}." if top else "."))
    base = seo.site_url(request)
    jsonld = [seo.breadcrumbs(request, ("Vagas PHP", "/"), ("Empresas", "/empresas")),
              {"@context": "https://schema.org", "@type": "ItemList",
               "name": "Empresas que mais anunciam vagas PHP", "url": base + "/empresas",
               "itemListElement": [{"@type": "ListItem", "position": i,
                                    "item": {"@type": "Organization", "name": c["name"]}}
                                   for i, c in enumerate(rows[:50], 1)]}]
    html = seo.render(
        request, "empresas.html", path="/empresas", description=description,
        title="Empresas que mais contratam devs PHP | Vagas PHP",
        content={"list": cards, "days": str(COMPANIES_DAYS), "min": str(COMPANIES_MIN)},
        jsonld=jsonld)
    return HTMLResponse(html)


async def companies(request: Request):
    return JSONResponse({"companies": _companies(), "days": COMPANIES_DAYS,
                         "min_jobs": COMPANIES_MIN, "max_age_hours": dates.MAX_AGE_HOURS})


async def stats(request: Request):
    try:
        return JSONResponse(store().stats())
    except ProgrammingError:
        return JSONResponse({"sources": {}, "last_runs": {}, "open_total": 0})


# --- sitemap e robots ------------------------------------------------------------------
# Cada provedor é uma função sem argumentos que devolve [(caminho, lastmod ISO ou None)].
# Acrescente provedores em SITEMAP_PROVIDERS; caminho repetido vale uma vez (o primeiro).

PAGES = ("/", "/vagas", "/dashboard", "/empresas", "/recrutadores", "/regras", "/mercado-php")


def _newest(jobs: list[dict]) -> str | None:
    return max((j.get("posted_at") or j["first_seen"] for j in jobs), default=None)


def sitemap_pages() -> list[tuple[str, str | None]]:
    newest = _newest(open_jobs())
    return [(path, newest if path in ("/", "/vagas") else None) for path in PAGES]


def sitemap_themes() -> list[tuple[str, str | None]]:
    jobs = open_jobs()
    return [(t["path"], _newest([j for j in jobs if _matches(t, j)])) for t in THEMES.values()]


def sitemap_jobs() -> list[tuple[str, str | None]]:
    return vaga.sitemap_entries(store())


SITEMAP_PROVIDERS = [sitemap_pages, sitemap_themes, sitemap_jobs]


async def sitemap(request: Request):
    base, entries = seo.site_url(request), {}
    for provider in SITEMAP_PROVIDERS:
        for path, lastmod in provider():
            entries.setdefault(path, lastmod)
    urls = []
    for path, lastmod in entries.items():
        mod = f"<lastmod>{escape(lastmod)}</lastmod>" if lastmod else ""
        urls.append(f"<url><loc>{escape(base + path)}</loc>{mod}</url>")
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
           + "\n".join(urls) + "\n</urlset>\n")
    return Response(xml, media_type="application/xml")


async def robots(request: Request):
    return Response(f"User-agent: *\nAllow: /\nDisallow: /api/\n\n"
                    f"Sitemap: {seo.site_url(request)}/sitemap.xml\n", media_type="text/plain")


app = Starlette(routes=[
    Route("/", index),
    Route("/api/jobs", jobs),
    Route("/api/stats", stats),
    Route("/vagas", themes_page),
    Route("/vagas/{slug}", theme_page),
    Route("/dashboard", dashboard_page),
    Route("/api/dashboard", dashboard),
    Route("/regras", rules_page),
    Route("/api/rules", rules),
    Route("/recrutadores", recruiters_page),
    Route("/api/recruiters", recruiters),
    Route("/empresas", companies_page),
    Route("/api/companies", companies),
    Route("/sitemap.xml", sitemap),
    Route("/robots.txt", robots),
    *mercado.routes,  # /mercado-php e /llms.txt
    *vaga.routes,     # /vaga/<seq>-<título>
])


if __name__ == "__main__":
    uvicorn.run(app, host=os.getenv("WEB_HOST", "127.0.0.1"), port=int(os.getenv("WEB_PORT", 8780)),
                proxy_headers=True)
