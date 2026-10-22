"""Página /mercado-php (mercado de trabalho PHP no Brasil em números) e /llms.txt (resumo
do site para assistentes de IA, formato llmstxt.org).

Tudo renderizado no servidor, em frases com números e datas que buscadores e robôs de
IA possam citar ("Há 68 vagas PHP abertas no Brasil (publicadas nas últimas 72
horas), de 40 empresas; 61% remotas."). Os números vêm de Store.dashboard(), Store.companies() e
Store.recruiters(), com as mesmas regras do resto do site (vagas aceitas pelas regras,
não descartadas, sem repetição). Ficam em memória por CACHE_SECONDS: robôs pedem as
duas páginas várias vezes e os números só mudam a cada coleta.

Rotas: /mercado-php  página (static/mercado.html)
       /llms.txt     texto puro
"""

import time
from datetime import datetime, timedelta
from html import escape

from pymysql.err import ProgrammingError
from starlette.requests import Request
from starlette.responses import HTMLResponse, PlainTextResponse
from starlette.routing import Route

from . import dates, seo

PATH = "/mercado-php"
SITEMAP_PATHS = [PATH]
WEEKS = 8           # semanas na tabela de vagas novas por semana
CACHE_SECONDS = 300

SOURCE_NAMES = {"linkedin": "Vagas do LinkedIn", "gupy": "Gupy", "post": "Publicações do LinkedIn",
                "github": "GitHub", "remotar": "Remotar", "programathor": "Programathor",
                "catho": "Catho", "solides": "Sólides", "inhire": "InHire", "coodesh": "Coodesh",
                "nerdin": "Nerdin", "recrutei": "Recrutei", "upvagas": "UpVagas"}
MISSING = "Não informado"



def topics() -> list[dict]:
    """Temas de um filtro só (Laravel, Remoto, Sênior...) de web.THEMES, na ordem de lá:
    viram links nas tabelas, na lista de temas e no llms.txt."""
    from .web import THEMES  # import tardio: web.py importa este módulo
    return [{**t, "value": t["stack"] or t["workplace"] or t["seniority"]} for t in THEMES.values()
            if sum(bool(t[k]) for k in ("stack", "workplace", "seniority")) == 1]


def topic_paths() -> dict[str, str]:
    """"Laravel" -> "/vagas/laravel", "Remoto" -> "/vagas/remoto", "Sênior" -> "/vagas/php-senior"
    (stacks, modalidades e senioridades não repetem nomes entre si)."""
    return {t["value"]: t["path"] for t in topics()}

_cache: dict = {"at": 0.0, "data": None}


# --- dados ---------------------------------------------------------------------------

def market() -> dict:
    """Números da página, de cache se tiverem menos de CACHE_SECONDS. ProgrammingError
    (base ainda vazia) passa para quem chama."""
    if _cache["data"] is not None and time.monotonic() - _cache["at"] < CACHE_SECONDS:
        return _cache["data"]
    # Import tardio: web.py importa este módulo.
    from .web import (COMPANIES_DAYS, COMPANIES_MIN, RECRUITERS_DAYS, RECRUITERS_HIDE,
                      RECRUITERS_MIN, store)
    st = store()
    today = datetime.now(dates.BRASILIA).date()
    monday = today - timedelta(days=today.weekday())
    # Série diária desde a segunda-feira de WEEKS - 1 semanas atrás (a atual em andamento).
    dash = st.dashboard(7 * (WEEKS - 1) + today.weekday() + 1)
    weeks = []
    for i in range(WEEKS):
        start = monday - timedelta(weeks=WEEKS - 1 - i)
        days = [d for d in dash["daily"]
                if 0 <= (datetime.fromisoformat(d["day"]).date() - start).days < 7]
        weeks.append({"start": start, "end": start + timedelta(days=6),
                      "jobs": sum(n for d in days for k, n in d.items() if k != "day"),
                      "current": start == monday})
    since = dash["collecting_since"]
    since_day = datetime.fromisoformat(since).astimezone(dates.BRASILIA).date() if since else None
    if since_day:  # semanas inteiras antes da coleta começar não dizem nada
        weeks = [w for w in weeks if w["end"] >= since_day]
    oks = [r["last_ok_at"] for r in dash["runs"].values() if r["last_ok_at"]]
    data = {**dash, "weeks": weeks, "since_day": since_day,
            "updated": max(oks) if oks else dates.utc_iso(dates.now_utc()),
            "companies_list": st.companies(COMPANIES_DAYS, COMPANIES_MIN),
            "companies_days": COMPANIES_DAYS, "companies_min": COMPANIES_MIN,
            "recruiters_list": st.recruiters(RECRUITERS_DAYS, RECRUITERS_MIN, RECRUITERS_HIDE),
            "recruiters_days": RECRUITERS_DAYS, "recruiters_min": RECRUITERS_MIN,
            "sources_count": len(SOURCE_NAMES)}
    _cache.update(at=time.monotonic(), data=data)
    return data


# --- formatação ----------------------------------------------------------------------

def _local(iso: str) -> datetime:
    return datetime.fromisoformat(iso).astimezone(dates.BRASILIA)


def br_date(day) -> str:
    return day.strftime("%d/%m/%Y")


def br_when(iso: str) -> str:
    """"22/10/2026, 14h" (horário de Brasília)."""
    dt = _local(iso)
    return f"{br_date(dt)}, {dt.hour}h"


def pct(n: int, total: int) -> str:
    return f"{round(100 * n / total)}%" if total else "0%"


def vagas(n: int, word: str = "vaga") -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def _sorted(pairs) -> list[tuple[str, int]]:
    """Maiores primeiro, "Não informado" por último."""
    pairs = [(k, n) for k, n in pairs if n]
    return sorted(pairs, key=lambda p: (p[0] == MISSING, -p[1]))


def _label(name: str, paths: dict[str, str]) -> str:
    path = paths.get(name)
    return f'<a href="{path}">{escape(name)}</a>' if path else escape(name)


def table(pairs, total: int, head: str) -> str:
    """Tabela nome | vagas | % do total."""
    paths = topic_paths()
    rows = "".join(f'<tr><td>{_label(k, paths)}</td><td class="num">{n}</td>'
                   f'<td class="num">{pct(n, total)}</td></tr>' for k, n in pairs)
    return (f'<table><thead><tr><th>{escape(head)}</th><th class="num">Vagas</th>'
            f'<th class="num">%</th></tr></thead><tbody>{rows}</tbody></table>')


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " e " + items[-1]


def _get(pairs, key) -> int:
    return dict(pairs).get(key, 0)


def _empty(text: str) -> str:
    return f'<p class="muted">{escape(text)}</p>'


# --- frases --------------------------------------------------------------------------

def headline(d: dict) -> str:
    """A frase principal, em texto puro (página, description e llms.txt)."""
    k, total = d["kpis"], d["kpis"]["open"]
    text = f"Há {vagas(total)} PHP abertas no Brasil (publicadas nas últimas 72 horas)"
    if k["companies"]:
        text += f", de {k['companies']} empresa{'' if k['companies'] == 1 else 's'}"
    if total:
        text += f"; {pct(k['remote'], total)} remotas"
    return text + "."


def sections(d: dict) -> dict[str, str]:
    """HTML (escapado) de cada marca <!--ssr:...--> de static/mercado.html."""
    k, total = d["kpis"], d["kpis"]["open"]
    when = br_when(d["updated"])
    out = {"updated": f'Atualizado em <time datetime="{escape(d["updated"])}">{escape(when)}</time>.'}

    resumo = [f"{escape(headline(d))} Dados de {escape(when)} (horário de Brasília)."]
    resumo.append(f"Nas últimas 24 horas foram publicadas {vagas(k['new_24h'], 'vaga')} PHP novas; "
                  f"nas 24 horas anteriores, {k['prev_24h']}.")
    # Semanas completas: nem a atual nem a do começo da coleta (só parte dela foi coletada).
    full = [w for w in d["weeks"] if not w["current"]
            and not (d["since_day"] and w["start"] < d["since_day"])]
    if full:
        w = full[-1]
        resumo.append(f"Na semana de {br_date(w['start'])} a {br_date(w['end'])} foram publicadas "
                      f"{vagas(w['jobs'])} PHP novas.")
    out["resumo"] = "".join(f"<p>{p}</p>" for p in resumo)

    # Semanas
    if d["weeks"]:
        rows = []
        for w in d["weeks"]:
            label = f"{w['start']:%d/%m} a {w['end']:%d/%m/%Y}"
            notes = []
            if w["current"]:
                notes.append("em andamento")
            if d["since_day"] and w["start"] < d["since_day"] <= w["end"]:
                notes.append(f"coleta começou em {d['since_day']:%d/%m}")
            if notes:
                label += f" ({', '.join(notes)})"
            rows.append(f'<tr><td>{escape(label)}</td><td class="num">{w["jobs"]}</td></tr>')
        text = ""
        if len(full) >= 2:
            a, b = full[-2], full[-1]
            text = (f"<p>Na semana de {br_date(b['start'])} a {br_date(b['end'])} foram "
                    f"publicadas {vagas(b['jobs'])} PHP novas; na semana anterior, {a['jobs']}.")
            avg = sum(w["jobs"] for w in full) / len(full)
            text += (f" Média das últimas {len(full)} semanas completas: "
                     f"{round(avg)} vagas por semana.</p>")
        out["semanas"] = (text + '<table><thead><tr><th>Semana (segunda a domingo)</th>'
                          f'<th class="num">Vagas novas</th></tr></thead><tbody>{"".join(rows)}'
                          '</tbody></table><p class="muted">Pela data de publicação, incluindo '
                          'vagas que já saíram do ar.</p>')
    else:
        out["semanas"] = _empty("Ainda não há semanas de coleta.")

    if not total:
        for key in ("modalidade", "contrato", "senioridade", "stacks"):
            out[key] = _empty("Nenhuma vaga aberta nas últimas 72 horas.")
    else:
        base = f"Das {vagas(total)} PHP abertas nas últimas 72 horas"
        wp = d["workplace"]
        parts = [f"{_get(wp, w)} ({pct(_get(wp, w), total)}) são {word}" for w, word in
                 (("Remoto", "remotas"), ("Híbrido", "híbridas"), ("Presencial", "presenciais"))]
        text = f"{base}, {_join(parts)}"
        if (miss := _get(wp, MISSING)):
            text += f"; {miss} não informa{'' if miss == 1 else 'm'} a modalidade"
        out["modalidade"] = (f"<p>{escape(text)}.</p>"
                             + table(_sorted(wp), total, "Modalidade"))

        ct = d["contract"]
        informed = total - _get(ct, MISSING)
        if informed:
            text = (f"Entre as vagas PHP abertas que informam o regime de contratação "
                    f"({informed} de {total}), {pct(_get(ct, 'CLT'), informed)} são CLT e "
                    f"{pct(_get(ct, 'PJ'), informed)} são PJ")
            if _get(ct, "Freelance"):
                text += f"; {pct(_get(ct, 'Freelance'), informed)} são freelance"
            text += f". {pct(total - informed, total)} das vagas não dizem o regime."
        else:
            text = "Nenhuma das vagas abertas informa o regime de contratação."
        out["contrato"] = f"<p>{escape(text)}</p>" + table(_sorted(ct), total, "Contratação")

        sen = [p for p in _sorted(d["seniority"]) if p[0] != MISSING]
        if sen:
            text = (f"A senioridade mais pedida nas vagas PHP abertas é {sen[0][0].lower()} "
                    f"({pct(sen[0][1], total)} das vagas)")
            if len(sen) > 1:
                text += ", seguida de " + _join([f"{s.lower()} ({pct(n, total)})" for s, n in sen[1:3]])
            text += "."
        else:
            text = "As vagas abertas não informam a senioridade."
        out["senioridade"] = f"<p>{escape(text)}</p>" + table(_sorted(d["seniority"]), total, "Senioridade")

        stacks = d["stack"]
        if stacks:
            text = ("Entre as vagas PHP abertas, "
                    + _join([f"{s} aparece em {pct(n, total)}" if i == 0 else f"{s} em {pct(n, total)}"
                             for i, (s, n) in enumerate(stacks[:3])]) + ".")
            out["stacks"] = (f"<p>{escape(text)}</p>" + table(stacks, total, "Framework / plataforma")
                             + '<p class="muted">Uma vaga pode citar mais de uma; as demais '
                               'pedem PHP sem framework citado.</p>')
        else:
            out["stacks"] = _empty("As vagas abertas não citam frameworks além do PHP.")

    # Empresas
    cs, cdays = d["companies_list"], d["companies_days"]
    if cs:
        top = cs[:10]
        text = (f"Nos últimos {cdays} dias, a empresa que mais anunciou vagas PHP foi "
                f"{top[0]['name']} ({vagas(top[0]['jobs'])})")
        if len(top) > 1:
            text += ", seguida de " + _join([f"{c['name']} ({c['jobs']})" for c in top[1:3]])
        items = "".join(f"<li>{escape(c['name'])}: {vagas(c['jobs'])}"
                        + (f" · {escape(', '.join(c['stack'][:3]))}" if c["stack"] else "")
                        + "</li>" for c in top)
        out["empresas"] = (f"<p>{escape(text)}.</p><ol>{items}</ol>"
                           f'<p><a href="/empresas">Ver todas as {len(cs)} empresas com '
                           f'{d["companies_min"]} ou mais vagas</a></p>')
    else:
        out["empresas"] = (_empty(f"Ainda não há empresas com {d['companies_min']} ou mais vagas "
                                  f"nos últimos {cdays} dias.")
                           + '<p><a href="/empresas">Página de empresas</a></p>')

    # Recrutadores
    rs, rdays = d["recruiters_list"], d["recruiters_days"]
    if rs:
        items = "".join(f"<li>{escape(r['name'] or 'Sem nome')}: {vagas(r['jobs'])}</li>" for r in rs[:5])
        out["recrutadores"] = (f"<p>{len(rs)} tech recruiter{'' if len(rs) == 1 else 's'} "
                               f"publicaram {d['recruiters_min']} ou mais vagas PHP no LinkedIn nos "
                               f"últimos {rdays} dias. Os que mais publicaram:</p><ol>{items}</ol>"
                               '<p><a href="/recrutadores">Ver todos os recrutadores</a></p>')
    else:
        out["recrutadores"] = (_empty(f"Ainda não há tech recruiters com {d['recruiters_min']} ou mais "
                                      f"vagas PHP publicadas no LinkedIn nos últimos {rdays} dias.")
                               + '<p><a href="/recrutadores">Página de recrutadores</a></p>')

    # Fontes
    src = [(SOURCE_NAMES.get(s, s), n) for s, n in sorted(d["by_source"], key=lambda p: -p[1]) if n]
    if src and total:
        text = (f"As vagas abertas vêm de {len(src)} das {d['sources_count']} fontes coletadas; "
                f"a maior é {src[0][0]}, com {pct(src[0][1], total)}.")
        out["fontes"] = f"<p>{escape(text)}</p>" + table(src, total, "Fonte")
    else:
        out["fontes"] = _empty("Nenhuma vaga aberta nas últimas 72 horas.")
    out["fontes"] += (f"<p class=\"muted\">Fontes coletadas: {escape(_join(list(SOURCE_NAMES.values())))}.</p>")

    out["temas"] = "".join(
        f'<p>{escape(group)}:</p><div class="topics">'
        + "".join(f'<a href="{escape(t["path"])}">{escape(t["value"])}</a>'
                  for t in topics() if t["group"] == group) + "</div>"
        for group in dict.fromkeys(t["group"] for t in topics()))

    since = f"desde {br_date(d['since_day'])}" if d["since_day"] else "desde o início da coleta"
    out["metodologia"] = (
        "<ul>"
        f"<li>Vagas coletadas várias vezes ao dia de {d['sources_count']} fontes públicas "
        f"(portais de vagas, publicações do LinkedIn e repositórios de vagas no GitHub), {escape(since)}.</li>"
        '<li>Entram só vagas de engenharia de software com PHP, segundo as '
        '<a href="/regras">regras de filtro do site</a>; o que não é vaga é descartado à mão.</li>'
        "<li>A mesma vaga anunciada várias vezes (por cidade, por exemplo) conta uma vez.</li>"
        f"<li>Vagas abertas: publicadas nas últimas {round(d['max_age_hours'])} horas e ainda no ar. "
        "Modalidade, contratação, senioridade e stack saem do texto da vaga; quando a vaga não "
        "diz, conta como não informado.</li>"
        "<li>Os números são do que o site coleta, não do mercado inteiro: servem para comparar "
        "proporções e tendências.</li>"
        f"<li>Última coleta usada: {escape(when)} (horário de Brasília). O código do site é "
        "aberto.</li>"
        "</ul>")
    return out


def description(d: dict) -> str:
    text = headline(d)
    sen = [p for p in _sorted(d["seniority"]) if p[0] != MISSING]
    if d["stack"] and d["kpis"]["open"]:
        text += f" {d['stack'][0][0]} em {pct(d['stack'][0][1], d['kpis']['open'])}."
    if sen:
        text += f" Senioridade mais pedida: {sen[0][0].lower()}."
    return text + f" Atualizado em {br_when(d['updated'])}."


def jsonld(request: Request, d: dict) -> list[dict]:
    base = seo.site_url(request)
    site = {"@type": "Organization", "name": seo.SITE_NAME, "url": base + "/"}
    since = d["since_day"].isoformat() if d["since_day"] else None
    dataset = {
        "@context": "https://schema.org", "@type": "Dataset",
        "name": "Vagas de emprego PHP no Brasil",
        "description": ("Vagas de engenharia de software com PHP (Laravel, Symfony, WordPress e "
                        "outros) anunciadas no Brasil, coletadas várias vezes ao dia de portais de "
                        "vagas, publicações do LinkedIn e repositórios do GitHub, com modalidade "
                        "(remoto, híbrido, presencial), contratação (CLT, PJ), senioridade e stack. "
                        + headline(d)),
        "url": base + PATH, "inLanguage": "pt-BR", "isAccessibleForFree": True,
        "creator": site, "publisher": site,
        "dateModified": d["updated"],
        "spatialCoverage": {"@type": "Place", "name": "Brasil"},
        "keywords": ["vagas PHP", "mercado de trabalho PHP", "Laravel", "Symfony", "WordPress",
                     "vagas remotas", "desenvolvedor PHP", "Brasil"],
        "variableMeasured": ["vagas abertas", "vagas novas por semana", "modalidade",
                             "regime de contratação", "senioridade", "stack", "empresa", "fonte"],
        "distribution": [
            {"@type": "DataDownload", "encodingFormat": "application/json",
             "contentUrl": base + "/api/dashboard", "name": "Números do mercado"},
            {"@type": "DataDownload", "encodingFormat": "application/json",
             "contentUrl": base + "/api/jobs", "name": "Vagas abertas"},
            {"@type": "DataDownload", "encodingFormat": "application/json",
             "contentUrl": base + "/api/companies", "name": "Empresas que mais anunciam"},
        ],
    }
    if since:
        dataset["temporalCoverage"] = f"{since}/.."
    return [seo.breadcrumbs(request, ("Vagas PHP", "/"), ("Mercado de trabalho PHP", PATH)), dataset]


# --- rotas ---------------------------------------------------------------------------

async def mercado_page(request: Request):
    title = "Mercado de trabalho PHP no Brasil"
    try:
        d = market()
    except ProgrammingError:  # tabelas ainda não criadas pelo coletor
        html = seo.render(request, "mercado.html", title=title, path=PATH, noindex=True,
                          description="Números do mercado de trabalho PHP no Brasil.",
                          content={"resumo": _empty("Base ainda vazia: volte depois da primeira coleta.")})
        return HTMLResponse(html, status_code=503)
    html = seo.render(request, "mercado.html", title=f"{title} · {seo.SITE_NAME}",
                      description=description(d), path=PATH, content=sections(d),
                      jsonld=jsonld(request, d))
    return HTMLResponse(html)


def llms_text(request: Request) -> str:
    base = seo.site_url(request)
    lines = [f"# {seo.SITE_NAME}", "",
             "> Vagas de emprego para devs PHP no Brasil (Laravel, Symfony, WordPress...), "
             "coletadas várias vezes ao dia de portais de vagas, do LinkedIn e do GitHub.", ""]
    try:
        d = market()
    except ProgrammingError:
        d = None
    if d:
        k = d["kpis"]
        text = (f"{headline(d)} Nas últimas 24 horas foram publicadas {vagas(k['new_24h'])} novas.")
        if d["stack"] and k["open"]:
            text += (" Stacks mais pedidas: "
                     + _join([f"{s} ({pct(n, k['open'])})" for s, n in d["stack"][:3]]) + ".")
        since = f" Coleta desde {br_date(d['since_day'])}." if d["since_day"] else ""
        lines += [f"{text} Dados de {br_when(d['updated'])} (horário de Brasília).{since} "
                  f"Os números são do que o site coleta de {d['sources_count']} fontes, não do "
                  "mercado inteiro.", ""]
    lines += [
        "## Páginas", "",
        f"- [Vagas PHP abertas]({base}/): vagas PHP publicadas nas últimas 72 horas, com filtros",
        f"- [Mercado de trabalho PHP no Brasil]({base}{PATH}): números atuais: vagas abertas, "
        "vagas por semana, remoto x presencial, CLT x PJ, senioridade, stacks e empresas",
        f"- [Empresas]({base}/empresas): empresas que mais anunciaram vagas PHP nos últimos 90 dias",
        f"- [Recrutadores]({base}/recrutadores): tech recruiters que mais publicam vagas PHP no LinkedIn",
        f"- [Regras]({base}/regras): como o site decide o que é vaga PHP",
        f"- [Dashboard]({base}/dashboard): gráficos das vagas por fonte e por dia, e estado das coletas",
        "", "## Vagas por tema", "",
        *[f"- [{t['name']}]({base}{t['path']}): vagas abertas nas últimas 72 horas" for t in topics()],
        "", "## API JSON pública", "",
        f"- [{base}/api/jobs]({base}/api/jobs): vagas abertas (últimas 72 h). Parâmetros: q (busca), "
        "source (linkedin, gupy, post, github...), workplace (Remoto, Híbrido, Presencial), "
        "seniority (Estágio, Júnior, Pleno, Sênior, Especialista), stack (Laravel, Symfony...), "
        "hours (1-72), include_closed (1), limit (1-200), offset",
        f"- [{base}/api/companies]({base}/api/companies): empresas com 2 ou mais vagas PHP nos últimos 90 dias",
        f"- [{base}/api/recruiters]({base}/api/recruiters): tech recruiters com vagas PHP nos últimos 90 dias",
        f"- [{base}/api/dashboard]({base}/api/dashboard): números do mercado (vagas abertas, modalidade, "
        "contratação, senioridade, stacks, fontes) e série diária; days (3-90) muda o período da série",
        "",
    ]
    return "\n".join(lines)


async def llms_txt(request: Request):
    return PlainTextResponse(llms_text(request), media_type="text/plain; charset=utf-8")


routes = [Route(PATH, mercado_page), Route("/llms.txt", llms_txt)]
