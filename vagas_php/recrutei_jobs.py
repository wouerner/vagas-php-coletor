"""Vagas do portal da Recrutei (empregos.recrutei.com.br), ATS com um portal único das
empresas clientes, sem login. A busca do site é proibida no robots.txt (?q=, ?keyword=),
então a lista vem do sitemap de vagas (com a data da última alteração); a página de cada
vaga traz um JSON-LD JobPosting com a data de publicação."""

import re

from . import jobposting

SITEMAP = "https://empregos.recrutei.com.br/sitemap-vagas-{}.xml"
ENTRY = re.compile(r"<loc>(https://empregos\.recrutei\.com\.br/vaga/[^/<]+/(\d+)-([^<]*))</loc>\s*"
                   r"(?:<lastmod>([\d-]+)[^<]*</lastmod>)?")


def list_jobs(max_pages: int = 5) -> list[tuple[int, str, str, str | None]]:
    """(id, título aproximado (do endereço), URL, última alteração AAAA-MM-DD)."""
    jobs = []
    for n in range(1, max_pages + 1):
        try:
            body = jobposting.fetch(SITEMAP.format(n), "Recrutei")
        except RuntimeError:
            if n == 1:
                raise
            break  # não há mais páginas do sitemap
        page = [(int(job_id), slug.replace("-", " "), url, lastmod)
                for url, job_id, slug, lastmod in ENTRY.findall(body)]
        if not page:
            break
        jobs += page
    return jobs


def job_details(url: str) -> dict:
    post = jobposting.find(jobposting.fetch(url, "Recrutei"))
    if not post:
        raise RuntimeError(f"Recrutei: {url} sem JobPosting")
    return jobposting.fields(post)
