"""Página de cada vaga de portal (/vaga/<seq>-<título>), renderizada no servidor para
buscadores e robôs de IA, com JSON-LD JobPosting para o Google for Jobs.

Regras:
- seq inexistente, post do LinkedIn, vaga recusada pelo filtro ou descartada à mão: 404.
- título no endereço diferente do atual: 301 para o endereço de seo.job_path().
- a mesma vaga anunciada de novo (DEDUP: título + empresa + fonte): 301 para a mais recente.
- aberta (publicada há até MAX_AGE_HOURS e sem closed_at): página completa com JobPosting.
- encerrada: 200 com noindex, sem JobPosting (o Google pede tirar o markup de vagas
  expiradas), aviso e links para vagas parecidas abertas.

O JobPosting só sai com empresa conhecida (hiringOrganization é obrigatório): sem
empresa, empresa que não diz quem contrata (php.company_key) ou issue do GitHub (o campo
empresa vem de texto livre da issue), a página continua, sem o markup.

web.py registra `routes` e usa `sitemap_entries()` no sitemap."""

import re
from datetime import datetime, timedelta
from html import escape

from pymysql.err import ProgrammingError
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse
from starlette.routing import Route

from . import dates, php, seo
from .store import DEDUP

SOURCE_NAMES = {"linkedin": "LinkedIn", "gupy": "Gupy", "github": "GitHub", "inhire": "InHire",
                "solides": "Sólides", "catho": "Catho", "remotar": "Remotar",
                "programathor": "Programathor", "coodesh": "Coodesh", "nerdin": "Nerdin",
                "recrutei": "Recrutei", "upvagas": "UpVagas"}
EMPLOYMENT_TYPE = {"CLT": "FULL_TIME", "PJ": "CONTRACTOR", "Freelance": "CONTRACTOR"}

UF = {"AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB",
      "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"}
STATES = {"acre", "alagoas", "amapá", "amazonas", "bahia", "ceará", "distrito federal",
          "espírito santo", "goiás", "maranhão", "mato grosso", "mato grosso do sul",
          "minas gerais", "pará", "paraíba", "paraná", "pernambuco", "piauí", "rio de janeiro",
          "rio grande do norte", "rio grande do sul", "rondônia", "roraima", "santa catarina",
          "são paulo", "sergipe", "tocantins"}
CAPITAL_STATES = {"são paulo", "rio de janeiro"}
COUNTRY = {"brasil", "brazil", "br"}
NO_PLACE = COUNTRY | {"remoto", "remote", "home office", "anywhere"}
# Salário só vai para o JSON-LD no formato que os coletores gravam ("R$ 5.000",
# "R$ 4.001 a R$ 5.000", "US$ 7.083 a US$ 10.417 por mês", "... por ano", "... por hora")
# e com valores coerentes com o período. Sem período, só reais, tomados como salário
# mensal (o costume dos portais brasileiros); dólar sem período fica de fora.
SALARY = re.compile(r"(R\$|US\$) ?(\d{1,3}(?:\.\d{3})*)(?: a (R\$|US\$) ?(\d{1,3}(?:\.\d{3})*))?"
                    r"(?: por (m[eê]s|ano|hora))?")
CURRENCY = {"R$": "BRL", "US$": "USD"}
PERIOD = {"mês": "MONTH", "mes": "MONTH", "ano": "YEAR", "hora": "HOUR"}
SALARY_RANGE = {"MONTH": (500, 100_000), "YEAR": (5_000, 2_000_000), "HOUR": (5, 2_000)}
SIMILAR = 6


def _store():
    from .web import store  # import tardio: web.py importa este módulo
    return store()


# --- dados da vaga -------------------------------------------------------------------

def posted(job: dict) -> str:
    return job.get("posted_at") or job["first_seen"]


def is_open(job: dict) -> bool:
    return not job.get("closed_at") and posted(job) >= dates.cutoff()


def stacks(job: dict) -> list[str]:
    return [s for s in (job.get("stack") or "").split(",") if s]


def topic(job: dict) -> tuple[str, str]:
    """Tema principal (nome, caminho): a primeira stack além de PHP, ou PHP (/vagas)."""
    other = [s for s in stacks(job) if s != "PHP"]
    return (other[0], topic_path(other[0])) if other else ("PHP", "/vagas")


def topic_path(name: str) -> str:
    return "/vagas" if name == "PHP" else f"/vagas/{seo.slugify(name)}"


def employer(job: dict) -> str | None:
    """Empresa que contrata, para o hiringOrganization; None quando não dá para afirmar."""
    name = (job.get("company") or "").strip()
    if job.get("source") == "github" or not php.company_key(name):
        return None
    return name


def address(job: dict) -> dict:
    """PostalAddress a partir do texto de local ("São Paulo, SP", "Curitiba, Paraná, Brasil",
    "Brasília - DF", "São Paulo e Região"). O local das issues do GitHub é texto livre:
    fica só o país."""
    out = {"@type": "PostalAddress"}
    text = (job.get("location") or "").strip().rstrip(".")
    if job.get("source") != "github" and text and "/" not in text:
        parts = [p.strip() for p in re.split(r",| - ", text) if p.strip()]
        while parts and parts[-1].lower() in COUNTRY:
            parts.pop()
        parts = [re.sub(r"\s+e regi[aã]o$", "", p, flags=re.I) for p in parts]
        is_region = lambda p: p.upper() in UF or p.lower() in STATES  # noqa: E731
        region = next((p for p in parts[1:] if is_region(p)), None)
        if region:
            out["addressRegion"] = region.upper() if len(region) == 2 else region
        first = parts[0] if parts and parts[0].lower() not in NO_PLACE else None
        # "Rio Grande do Sul - RS" e "Minas Gerais" são só o estado; São Paulo e Rio de
        # Janeiro também são cidades.
        if first and is_region(first) and first.lower() not in CAPITAL_STATES:
            out.setdefault("addressRegion", first)
        elif first:
            out["addressLocality"] = first
    out["addressCountry"] = "BR"
    return out


def salary(job: dict) -> dict | None:
    m = SALARY.fullmatch((job.get("salary") or "").strip())
    if not m or (m.group(3) and m.group(3) != m.group(1)):
        return None
    currency = CURRENCY[m.group(1)]
    if not m.group(5) and currency != "BRL":
        return None
    unit = PERIOD[m.group(5).lower()] if m.group(5) else "MONTH"
    low = int(m.group(2).replace(".", ""))
    high = int(m.group(4).replace(".", "")) if m.group(4) else None
    floor, ceiling = SALARY_RANGE[unit]
    if not all(floor <= v <= ceiling for v in (low, high or low)) or (high and high < low):
        return None
    value = {"@type": "QuantitativeValue", "unitText": unit}
    if high and high != low:
        value.update(minValue=low, maxValue=high)
    else:
        value["value"] = low
    return {"@type": "MonetaryAmount", "currency": currency, "value": value}


# Markdown das issues do GitHub (e de alguns portais): títulos, negrito e links. Num
# texto que não é Markdown, "#vagas" no começo da linha é hashtag: aí o título precisa
# de espaço depois do "#".
MD_HEADING = re.compile(r"^#{1,6}\s+(.+)$")
MD_HEADING_LOOSE = re.compile(r"^#{1,6}\s*(.+)$")
MD_BOLD = re.compile(r"\*\*(.+?)\*\*")
MD_LINK = re.compile(r"\[([^\]]+)\]\(((?:https?://|mailto:)[^)\s]+)\)")


def _inline(line: str) -> str:
    """Uma linha já escapada com negrito e links do Markdown em HTML."""
    def link(m):
        text, url = m.group(1), m.group(2)
        if url.startswith("mailto:"):
            return text
        return f'<a href="{url}" rel="nofollow noopener" target="_blank">{text}</a>'
    return MD_BOLD.sub(r"<strong>\1</strong>", MD_LINK.sub(link, line))


def description_html(text: str | None, markdown: bool = False) -> str:
    """Texto coletado -> HTML simples: parágrafos nas linhas em branco, <br> nas quebras,
    <h3> nos títulos do Markdown, <strong> e links. Tudo escapado antes. `markdown`: o
    texto é Markdown (GitHub), e "#Título" sem espaço também vira título."""
    heading = MD_HEADING_LOOSE if markdown else MD_HEADING
    out = []
    for block in re.split(r"\n\s*\n", (text or "").replace("\r\n", "\n").strip()):
        lines = []
        for raw in block.split("\n"):
            line = escape(raw.strip())
            if not line:
                continue
            if m := heading.match(line):
                if lines:
                    out.append("<p>" + "<br>\n".join(lines) + "</p>")
                    lines = []
                title = re.sub(r"^\*\*(.+)\*\*$", r"\1", m.group(1).strip().rstrip("#").strip())
                out.append(f"<h3>{_inline(title)}</h3>")
            else:
                lines.append(_inline(line))
        if lines:
            out.append("<p>" + "<br>\n".join(lines) + "</p>")
    return "\n".join(out)


def job_posting(job: dict, base_url: str) -> dict | None:
    """JSON-LD JobPosting (diretrizes do Google for Jobs) de uma vaga aberta; None sem
    empresa, sem título ou sem descrição, que o Google exige."""
    company = employer(job)
    if not (company and job.get("title") and (job.get("description") or "").strip()):
        return None
    start = datetime.fromisoformat(posted(job))
    data = {
        "@context": "https://schema.org", "@type": "JobPosting",
        "title": job["title"].strip(),
        "description": description_html(job["description"]),
        "datePosted": dates.utc_iso(start),
        "validThrough": dates.utc_iso(start + timedelta(hours=dates.MAX_AGE_HOURS)),
        "hiringOrganization": {"@type": "Organization", "name": company},
        "identifier": {"@type": "PropertyValue",
                       "name": SOURCE_NAMES.get(job["source"], job["source"]), "value": job["id"]},
        "directApply": False,
        "url": base_url + seo.job_path(job),
    }
    if kind := EMPLOYMENT_TYPE.get(job.get("contract")):
        data["employmentType"] = kind
    if job.get("workplace") == "Remoto":
        data["jobLocationType"] = "TELECOMMUTE"
        data["applicantLocationRequirements"] = {"@type": "Country", "name": "Brasil"}
    else:
        data["jobLocation"] = {"@type": "Place", "address": address(job)}
    if pay := salary(job):
        data["baseSalary"] = pay
    return data


def similar(store, job: dict) -> list[dict]:
    """Vagas abertas de portais parecidas: mesma stack principal e senioridade; completa
    com a mesma stack."""
    name, _ = topic(job)
    seen, out = {job["seq"]}, []
    for seniority in ([job["seniority"]] if job.get("seniority") else []) + [None]:
        for r in store.query_jobs(stack=name, seniority=seniority, limit=40):
            if r["source"] != "post" and r["seq"] not in seen and len(out) < SIMILAR:
                seen.add(r["seq"])
                out.append(r)
    return out


# --- HTML ----------------------------------------------------------------------------

def br_datetime(iso: str) -> str:
    dt = datetime.fromisoformat(iso).astimezone(dates.BRASILIA)
    return dt.strftime("%d/%m/%Y às %H:%M")


def place(job: dict) -> str | None:
    """"Remoto", "Híbrido · São Paulo, SP", "São Paulo, SP"..."""
    loc = (job.get("location") or "").strip()
    if job.get("source") == "github" and "/" in loc:  # nome do repositório
        loc = ""
    if job.get("workplace") == "Remoto" and loc.lower() in NO_PLACE:
        loc = ""
    return " · ".join(p for p in (job.get("workplace"), loc) if p) or None


def page_title(job: dict, is_open_: bool) -> str:
    title = (job.get("title") or "Vaga PHP").strip()
    if job.get("company"):
        title += f" — {job['company'].strip()}"
    if job.get("workplace"):
        title += f" ({job['workplace']})"
    return title + ("" if is_open_ else " · encerrada") + f" | {seo.SITE_NAME}"


def summary(job: dict, limit: int = 150) -> str:
    """Resumo para a meta description: cargo, empresa, modalidade e o começo do texto."""
    facts = [job.get(k) for k in ("seniority", "workplace", "contract") if job.get(k)]
    head = f"Vaga {job.get('title') or 'PHP'}".strip()
    if job.get("company"):
        head += f" na {job['company'].strip()}"
    head += (f" ({', '.join(facts)})" if facts else "") + ". "
    text = head + re.sub(r"\s+", " ", job.get("description") or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit - 1].rsplit(" ", 1)[0].rstrip(",.;:-") + "…"


def _row(label: str, value: str | None) -> str:
    return f"<dt>{escape(label)}</dt><dd>{escape(value)}</dd>" if value else ""


def similar_html(items: list[dict], heading: str) -> str:
    if not items:
        return '<span id="parecidas"></span>' 
    lis = []
    for r in items:
        company = r.get("company") if r.get("source") != "github" else None  # texto livre lá
        meta = " · ".join(escape(p) for p in (company, place(r), r.get("seniority")) if p)
        lis.append(f'<li><a href="{escape(seo.job_path(r))}">{escape(r.get("title") or "Vaga PHP")}</a>'
                   + (f'<span class="meta">{meta}</span>' if meta else "") + "</li>")
    return (f'<section class="card similar" id="parecidas"><h2>{escape(heading)}</h2>'
            f'<ul>{"".join(lis)}</ul></section>')


def job_html(job: dict, is_open_: bool, others: list[dict]) -> str:
    name, path = topic(job)
    source = SOURCE_NAMES.get(job["source"], job["source"])
    out = []
    if not is_open_:
        out.append('<p class="closed" role="status"><strong>Esta vaga não está mais aberta.</strong> '
                   f'Ela foi publicada há mais de {dates.MAX_AGE_HOURS:g} horas ou foi encerrada '
                   'na fonte. <a href="#parecidas">Veja vagas parecidas abertas</a>.</p>')
        out.append(similar_html(others, "Vagas parecidas abertas"))
    out.append(f'<article class="card job{"" if is_open_ else " closed-job"}">')
    out.append(f'<h1 class="title">{escape(job.get("title") or "Vaga PHP")}</h1>')
    if job.get("company"):
        out.append(f'<p class="company">{escape(job["company"])}</p>')
    out.append('<dl class="facts">'
               + _row("Local", place(job)) + _row("Senioridade", job.get("seniority"))
               + _row("Contratação", job.get("contract")) + _row("Salário", job.get("salary"))
               + f'<dt>Publicada</dt><dd><time datetime="{escape(posted(job))}">'
               f'{escape(br_datetime(posted(job)))}</time> (horário de Brasília)</dd>'
               + _row("Fonte", source) + "</dl>")
    if stacks(job):
        out.append('<div class="chips">' + "".join(
            f'<a class="chip" href="{escape(topic_path(s))}">{escape(s)}</a>' for s in stacks(job))
            + "</div>")
    if job.get("url") and is_open_:
        out.append(f'<p class="apply"><a class="button" href="{escape(job["url"])}" '
                   f'rel="nofollow noopener" target="_blank">Candidatar-se no site original '
                   f'({escape(source)})</a></p>')
    if (job.get("description") or "").strip():
        md = job["source"] == "github"
        out.append(f'<h2>Descrição</h2><div class="description">'
                   f'{description_html(job["description"], markdown=md)}</div>')
    if job.get("url") and not is_open_:
        out.append(f'<p class="meta">Anúncio original: <a href="{escape(job["url"])}" '
                   f'rel="nofollow noopener" target="_blank">{escape(source)}</a></p>')
    out.append("</article>")
    if is_open_:
        out.append(similar_html(others, "Vagas parecidas"))
    out.append(f'<p class="more"><a href="{escape(path)}">Mais vagas {escape(name)}</a>'
               ' · <a href="/">Todas as vagas abertas</a></p>')
    return "\n".join(out)


def crumbs_html(items: list[tuple[str, str]]) -> str:
    links = [f'<a href="{escape(p)}">{escape(n)}</a>' for n, p in items[:-1]]
    return ('<nav class="crumbs" aria-label="Caminho">' + " › ".join(links)
            + f' › <span aria-current="page">{escape(items[-1][0])}</span></nav>')


def not_found(request: Request) -> HTMLResponse:
    html = seo.render(
        request, "vaga.html", title=f"Vaga não encontrada | {seo.SITE_NAME}",
        description="Esta vaga não existe ou foi retirada do site.", path=request.url.path,
        noindex=True,
        content={"vaga": '<article class="card job"><h1 class="title">Vaga não encontrada</h1>'
                         '<p>Esta vaga não existe ou foi retirada do site.</p>'
                         '<p><a href="/">Ver as vagas abertas</a></p></article>'})
    return HTMLResponse(html, status_code=404)


# --- rotas ---------------------------------------------------------------------------

async def job_page(request: Request):
    m = re.fullmatch(r"(\d{1,18})(?:-.*)?", request.path_params["ref"])
    if not m:
        return not_found(request)
    store = _store()
    try:
        row = store.execute("SELECT * FROM jobs WHERE seq = ?", (int(m.group(1)),)).fetchone()
        job = dict(row) if row else None
        if not job or job["source"] == "post" or not job["relevant"] or job["dismissed"]:
            return not_found(request)
        # Anunciada de novo (outro id, mesmo título e empresa): vale a mais recente.
        newest = store.execute(
            "SELECT max(seq) FROM jobs WHERE source = ? AND lower(COALESCE(title, '')) = lower(?) "
            "AND lower(COALESCE(company, author, '')) = lower(?)",
            (job["source"], job["title"] or "", job["company"] or job["author"] or "")).fetchone()[0]
        if newest and newest != job["seq"]:
            other = store.execute("SELECT seq, source, title FROM jobs WHERE seq = ?",
                                  (newest,)).fetchone()
            return RedirectResponse(seo.job_path(dict(other)), status_code=301)
        path = seo.job_path(job)
        if request.url.path != path:
            return RedirectResponse(path, status_code=301)
        open_ = is_open(job)
        others = similar(store, job)
    except ProgrammingError:  # tabelas ainda não criadas pelo coletor
        return not_found(request)

    name, tpath = topic(job)
    title = (job.get("title") or "Vaga PHP").strip()
    trail = [("Início", "/"), ("Vagas", "/vagas")]
    if tpath != "/vagas":
        trail.append((name, tpath))
    trail.append((title, path))
    jsonld = [seo.breadcrumbs(request, *trail)]
    if open_ and (posting := job_posting(job, seo.site_url(request))):
        jsonld.insert(0, posting)
    html = seo.render(request, "vaga.html", title=page_title(job, open_),
                      description=summary(job), path=path, jsonld=jsonld, noindex=not open_,
                      content={"crumbs": crumbs_html(trail), "vaga": job_html(job, open_, others)})
    return HTMLResponse(html)


routes = [Route("/vaga/{ref}", job_page)]


def sitemap_entries(store) -> list[tuple[str, str]]:
    """(caminho, lastmod ISO) das vagas abertas de portais, para o sitemap."""
    try:
        rows = store.execute(
            f"""SELECT seq, source, title, COALESCE(posted_at, first_seen) AS posted FROM jobs
                WHERE source != 'post' AND relevant = 1 AND dismissed IS NULL
                  AND closed_at IS NULL AND COALESCE(posted_at, first_seen) >= ? AND {DEDUP}
                ORDER BY posted DESC""", (dates.cutoff(),))
    except ProgrammingError:
        return []
    return [(seo.job_path(dict(r)), r["posted"]) for r in rows]
