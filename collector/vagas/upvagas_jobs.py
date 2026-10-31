"""Vagas da UpVagas (upvagas.com.br), portal de vagas remotas (muitas de empresas de fora
abertas a quem mora no Brasil), sem login. O site é um WordPress: a API pública
/wp-json/wp/v2/job-listings busca por termo no título e na descrição e devolve as vagas da
mais nova para a mais antiga, com data e hora."""

import html
import json
import time
import urllib.parse
from dataclasses import dataclass
from datetime import datetime

from . import config, jobposting
from .public_jobs import html_to_text

API = "https://upvagas.com.br/wp-json/wp/v2/job-listings"
PAGE_SIZE = 50
CONTRACT = {5: "Freelance"}  # job-types: 5 = Freelancer (os outros são jornada, não contrato)
INTERNSHIP = 6               # job-types: 6 = Estágio
WORKPLACE = {"remoto": "Remoto", "hibrido": "Híbrido", "presencial": "Presencial"}


@dataclass
class UpvagasJob:
    id: int
    title: str
    company: str | None
    location: str | None
    workplace: str | None
    contract: str | None
    internship: bool
    salary: str | None
    description: str | None
    published: str          # ISO UTC
    url: str


def terms() -> list[str]:
    """Termos buscados: VAGAS_UPVAGAS_TERMS, senão a configuração (config.py)."""
    return config.search("upvagas", "VAGAS_UPVAGAS_TERMS")


def search(term: str, since: datetime, max_pages: int = 4) -> list[UpvagasJob]:
    """Vagas abertas com `term` publicadas desde `since` (UTC)."""
    jobs = []
    for page in range(1, max_pages + 1):
        params = {"search": term, "per_page": PAGE_SIZE, "page": page, "orderby": "date",
                  "order": "desc"}
        try:
            items = json.loads(jobposting.fetch(f"{API}?{urllib.parse.urlencode(params)}", "UpVagas"))
        except RuntimeError as e:
            if "HTTP 400" in str(e):  # página além da última
                break
            raise
        for it in items:
            published = (it.get("date_gmt") or "") + "+00:00"
            if published < since.isoformat(timespec="seconds"):
                return jobs  # daqui para frente, só mais antigas
            meta = it.get("meta") or {}
            if not isinstance(meta, dict) or meta.get("_filled"):
                continue
            types = it.get("job-types") or []
            mode = WORKPLACE.get(it.get("upv_work_mode") or "")
            salary = (meta.get("_job_salary") or "").strip()
            jobs.append(UpvagasJob(
                id=it["id"], title=html.unescape(it["title"]["rendered"]).strip(),
                company=(meta.get("_company_name") or "").strip() or None,
                location=(meta.get("_job_location") or "").strip() or None,
                workplace=mode or ("Remoto" if meta.get("_remote_position") else None),
                contract=next((CONTRACT[t] for t in types if t in CONTRACT), None),
                internship=INTERNSHIP in types,
                salary=f"{meta.get('_job_salary_currency') or ''} {salary}".strip() if salary else None,
                description=html_to_text((it.get("content") or {}).get("rendered") or "") or None,
                published=published, url=it["link"]))
        if len(items) < PAGE_SIZE:
            break
        time.sleep(1)
    return jobs
