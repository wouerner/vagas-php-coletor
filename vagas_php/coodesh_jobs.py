"""Vagas da Coodesh (coodesh.com), plataforma de vagas de tecnologia, sem login. Todas as
vagas abertas estão no sitemap /sitemaps/jobs.xml (com a data da última alteração); a
página de cada vaga traz um JSON-LD JobPosting com a data de publicação."""

import re

from . import jobposting

SITEMAP = "https://coodesh.com/sitemaps/jobs.xml"
ENTRY = re.compile(r"<loc>(https://coodesh\.com/jobs/([a-z0-9-]+)-(\d+))</loc>\s*"
                   r"(?:<lastmod>([\d-]+)</lastmod>)?")


def list_jobs() -> list[tuple[int, str, str, str | None]]:
    """(id, título aproximado (do endereço), URL, última alteração AAAA-MM-DD)."""
    body = jobposting.fetch(SITEMAP, "Coodesh")
    return [(int(job_id), slug.replace("-", " "), url, lastmod)
            for url, slug, job_id, lastmod in ENTRY.findall(body)]


def job_details(url: str) -> dict:
    post = jobposting.find(jobposting.fetch(url, "Coodesh"))
    if not post:
        raise RuntimeError(f"Coodesh: {url} sem JobPosting")
    return jobposting.fields(post)
