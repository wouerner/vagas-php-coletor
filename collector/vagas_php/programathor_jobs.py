"""Vagas da Programathor (programathor.com.br), portal só de vagas de programação, sem
login. As listas por tecnologia (/jobs-php, /jobs-laravel...) não seguem a ordem de
publicação (vagas antigas ainda abertas aparecem no meio): a data vem do JSON-LD
JobPosting da página de cada vaga, baixada só para as vagas novas."""

import os
import re
import time

from . import jobposting

BASE = "https://programathor.com.br"
DEFAULT_PAGES = ("jobs-php,jobs-laravel,jobs-symfony,jobs-codeigniter,jobs-wordpress,jobs-magento,"
                 "jobs-drupal")
JOB_LINK = re.compile(r'href="/jobs/(\d+)-([a-z0-9-]*)"')
# O título do JobPosting termina com a categoria da vaga ("... - Full Stack").
CATEGORY = re.compile(r"\s+-\s+(Full Stack|Back-End|Front-End|Mobile|DevOps|Dados|Data|QA|"
                      r"Testes|Gestão|Design|Infraestrutura|Segurança|Games|Outros)$", re.I)


def pages() -> list[str]:
    return [t.strip() for t in (os.getenv("VAGAS_PROGRAMATHOR_PAGES") or DEFAULT_PAGES)
            .split(",") if t.strip()]


def list_jobs(page: str, max_pages: int = 3) -> list[tuple[int, str, str]]:
    """(id, título aproximado (do endereço), URL) das vagas abertas de uma lista."""
    found: dict[int, tuple[int, str, str]] = {}
    for n in range(1, max_pages + 1):
        body = jobposting.fetch(f"{BASE}/{page}" + (f"?page={n}" if n > 1 else ""), "Programathor")
        new = 0
        for job_id, slug in JOB_LINK.findall(body):
            if int(job_id) not in found:
                found[int(job_id)] = (int(job_id), slug.replace("-", " "),
                                      f"{BASE}/jobs/{job_id}-{slug}")
                new += 1
        if not new:
            break
        time.sleep(2)
    return list(found.values())


def job_details(url: str) -> dict:
    post = jobposting.find(jobposting.fetch(url, "Programathor"))
    if not post:
        raise RuntimeError(f"Programathor: {url} sem JobPosting")
    job = jobposting.fields(post)
    job["title"] = CATEGORY.sub("", job["title"])
    return job
