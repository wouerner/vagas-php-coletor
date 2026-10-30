"""Vagas da Nerdin (nerdin.com.br), portal só de vagas de TI, sem login. A busca
(vagas.php?busca=<termo>, permitida no robots.txt) lista as vagas abertas da mais nova para
a mais antiga; a página de cada vaga traz um JSON-LD JobPosting com a data de publicação."""

import os
import re
import time
import urllib.parse

from . import jobposting

BASE = "https://www.nerdin.com.br"
DEFAULT_TERMS = "php,laravel,symfony,codeigniter,wordpress,magento,drupal"
JOB_LINK = re.compile(r'href="(?:/|https://www\.nerdin\.com\.br/)?vaga_emprego/vaga-([a-z0-9-]+)-(\d+)\.php"')


def terms() -> list[str]:
    return [t.strip() for t in (os.getenv("VAGAS_NERDIN_TERMS") or DEFAULT_TERMS).split(",")
            if t.strip()]


def search(term: str) -> list[tuple[int, str, str]]:
    """(id, título aproximado (do endereço), URL) das vagas abertas com `term`."""
    body = jobposting.fetch(f"{BASE}/vagas.php?{urllib.parse.urlencode({'busca': term})}", "Nerdin")
    return list({int(job_id): (int(job_id), slug.replace("-", " "),
                               f"{BASE}/vaga_emprego/vaga-{slug}-{job_id}.php")
                 for slug, job_id in JOB_LINK.findall(body)}.values())


def search_all() -> list[tuple[int, str, str]]:
    found: dict[int, tuple[int, str, str]] = {}
    for term in terms():
        for job in search(term):
            found.setdefault(job[0], job)
        time.sleep(1.5)
    return list(found.values())


def job_details(url: str) -> dict:
    post = jobposting.find(jobposting.fetch(url, "Nerdin"))
    if not post:
        raise RuntimeError(f"Nerdin: {url} sem JobPosting")
    return jobposting.fields(post)
