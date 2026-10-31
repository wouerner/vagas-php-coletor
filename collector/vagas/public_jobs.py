"""Busca de vagas no LinkedIn sem login, pelo endpoint público ("guest") de vagas.

Não usa navegador nem a sua conta: são requisições HTTP simples, as mesmas que a
página pública https://www.linkedin.com/jobs/search faz. Diferenças para a busca logada
(bot.LinkedInBot):

- a busca é por palavra-chave (a logada é semântica, por IA), então volta mais vagas;
- não há filtro de modalidade (remoto/híbrido/presencial): o LinkedIn ignora o filtro
  para visitantes e o cartão público não informa a modalidade;
- não há dados ligados ao seu perfil (conexões na empresa, vagas já vistas).
"""

import html
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

BASE_URL = "https://www.linkedin.com"
PAGE_SIZE = 10  # cartões por página no endpoint público
USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/140.0 Safari/537.36")

CARD = re.compile(r"<li>(.*?)</li>", re.S)
JOB_ID = re.compile(r'data-entity-urn="urn:li:jobPosting:(\d+)"')
TITLE = re.compile(r'<h3 class="base-search-card__title">(.*?)</h3>', re.S)
COMPANY = re.compile(r'<h4 class="base-search-card__subtitle">(.*?)</h4>', re.S)
COMPANY_URL = re.compile(r'<h4 class="base-search-card__subtitle">.*?href="([^"?]+)', re.S)
LOCATION = re.compile(r'<span class="job-search-card__location">(.*?)</span>', re.S)
POSTED = re.compile(r'<time class="job-search-card__listdate[^"]*" datetime="([^"]+)">(.*?)</time>', re.S)
BENEFIT = re.compile(r'<span class="job-posting-benefits__text">(.*?)</span>', re.S)
SALARY = re.compile(r'<span class="job-search-card__salary-info">(.*?)</span>', re.S)
TAG = re.compile(r"<[^>]+>|<!---->")


@dataclass
class PublicJob:
    id: str
    title: str | None
    company: str | None
    company_url: str | None
    location: str | None
    posted: str | None       # texto relativo, ex.: "há 7 horas"
    posted_date: str | None  # data ISO, ex.: "2026-10-09"
    benefits: str | None     # ex.: "Contratando ativamente", "Candidatura simplificada"
    salary: str | None
    url: str


def _text(match: re.Match | None) -> str | None:
    if not match:
        return None
    value = re.sub(r"\s+", " ", html.unescape(TAG.sub(" ", match.group(1)))).strip()
    return value or None


def _get(url: str, retries: int = 3) -> str:
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT, "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            # 429 = limite de requisições para visitantes; espera e tenta de novo.
            if e.code == 429 and attempt < retries - 1:
                time.sleep(5 * (attempt + 1))
                continue
            raise RuntimeError(f"LinkedIn respondeu HTTP {e.code} para {url}") from e
    raise RuntimeError(f"Sem resposta do LinkedIn para {url}")


def geo_id(location: str) -> str:
    """Resolve o nome de um lugar para o geoId do LinkedIn (melhor resultado)."""
    if location.isdigit():
        return location
    query = urllib.parse.urlencode({
        "origin": "jserp", "typeaheadType": "GEO", "query": location,
        "geoTypes": "POPULATED_PLACE,ADMIN_DIVISION_2,MARKET_AREA,COUNTRY_REGION"})
    hits = json.loads(_get(f"{BASE_URL}/jobs-guest/api/typeaheadHits?{query}") or "[]")
    if not hits:
        raise ValueError(f"Local não encontrado no LinkedIn: {location!r}")
    return hits[0]["id"]


def parse_cards(page: str) -> list[PublicJob]:
    jobs = []
    for card in CARD.findall(page):
        job_id = JOB_ID.search(card)
        if not job_id:
            continue
        posted = POSTED.search(card)
        company_url = COMPANY_URL.search(card)
        jobs.append(PublicJob(
            id=job_id.group(1),
            title=_text(TITLE.search(card)),
            company=_text(COMPANY.search(card)),
            company_url=company_url.group(1) if company_url else None,
            location=_text(LOCATION.search(card)),
            posted=_text(re.search(r">(.*)", posted.group(0), re.S)) if posted else None,
            posted_date=posted.group(1) if posted else None,
            benefits=_text(BENEFIT.search(card)),
            salary=_text(SALARY.search(card)),
            url=f"{BASE_URL}/jobs/view/{job_id.group(1)}/",
        ))
    return jobs


def search_jobs(keywords: str, hours: float | None = 24, location: str | None = None,
                easy_apply: bool = False, limit: int = 50, delay: float = 1.5) -> list[PublicJob]:
    """Busca vagas sem login. `hours`: publicadas nas últimas N horas (None = qualquer
    data); `location`: nome de um lugar ou geoId (padrão VAGAS_LINKEDIN_LOCATION ou
    "Brasil"); `easy_apply`: só candidatura simplificada."""
    params = {"keywords": keywords,
              "geoId": geo_id(location or os.getenv("VAGAS_LINKEDIN_LOCATION") or "Brasil")}
    if hours:
        params["f_TPR"] = f"r{int(hours * 3600)}"
    if easy_apply:
        params["f_AL"] = "true"

    jobs: dict[str, PublicJob] = {}
    start = 0
    while len(jobs) < limit:
        params["start"] = str(start)
        page = _get(f"{BASE_URL}/jobs-guest/jobs/api/seeMoreJobPostings/search?"
                    f"{urllib.parse.urlencode(params)}")
        cards = parse_cards(page)
        new = [j for j in cards if j.id not in jobs]
        for job in new:
            jobs[job.id] = job
        if not new or len(cards) < PAGE_SIZE:
            break  # fim dos resultados
        start += len(cards)
        time.sleep(delay)  # educado com o endpoint público (evita HTTP 429)
    return list(jobs.values())[:limit]


DESCRIPTION = re.compile(r'<div class="show-more-less-html__markup[^"]*">(.*?)</div>\s*'
                         r'(?:<button|</section>)', re.S)
CRITERIA = re.compile(r'description__job-criteria-subheader">\s*(.*?)\s*</h3>\s*<span[^>]*>'
                      r'\s*(.*?)\s*</span>', re.S)
BLOCK_TAG = re.compile(r"<\s*(br|/p|/li|/ul|/ol|/h\d|/div)\s*/?>", re.I)


def html_to_text(fragment: str) -> str:
    text = BLOCK_TAG.sub("\n", fragment)
    text = re.sub(r"<li[^>]*>", "• ", text)
    text = html.unescape(TAG.sub("", text))
    lines = [re.sub(r"[ \t\xa0]+", " ", line).strip() for line in text.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def job_details(job_id: str) -> dict:
    """Descrição completa e critérios (nível, tipo de emprego...) de uma vaga, sem login."""
    page = _get(f"{BASE_URL}/jobs-guest/jobs/api/jobPosting/{job_id}")
    desc = DESCRIPTION.search(page)
    return {
        "description": html_to_text(desc.group(1)) if desc else None,
        "criteria": {html.unescape(k): html.unescape(TAG.sub("", v)).strip()
                     for k, v in CRITERIA.findall(page)},
    }
