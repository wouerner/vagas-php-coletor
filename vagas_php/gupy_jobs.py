"""Vagas do portal da Gupy (portal.gupy.io), pela mesma API JSON que o site usa, sem
login. A busca é só no título, então buscamos também termos amplos ("desenvolvedor",
"backend"...) e o filtro de PHP decide pela descrição. Os resultados vêm do mais
recente para o mais antigo: a paginação para ao passar do início da janela."""

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime

from .public_jobs import USER_AGENT, html_to_text

API = "https://portal.gupy.io/api/job-search/jobs"
PAGE_SIZE = 100
DEFAULT_TERMS = "php,laravel,symfony,wordpress,magento,drupal,desenvolvedor,desenvolvedora,backend,full stack"

WORKPLACE = {"remote": "Remoto", "hybrid": "Híbrido", "on-site": "Presencial"}
# Tipo da vaga na Gupy -> contratação / senioridade.
CONTRACT = {"vacancy_type_effective": "CLT", "vacancy_legal_entity": "PJ",
            "vacancy_type_freelancer": "Freelance"}
INTERNSHIP = {"vacancy_type_internship", "vacancy_type_trainee"}


@dataclass
class GupyJob:
    id: int
    title: str
    company: str | None
    location: str | None
    workplace: str | None
    contract: str | None
    internship: bool
    description: str | None
    published: str          # ISO UTC
    url: str


def _get(params: dict) -> dict:
    req = urllib.request.Request(f"{API}?{urllib.parse.urlencode(params)}", headers={
        "User-Agent": USER_AGENT, "Accept": "application/json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 2:
                time.sleep(5 * (attempt + 1))
                continue
            raise RuntimeError(f"Gupy respondeu HTTP {e.code}") from e
    raise RuntimeError("Sem resposta da Gupy")


def terms() -> list[str]:
    return [t.strip() for t in (os.getenv("VAGAS_GUPY_TERMS") or DEFAULT_TERMS).split(",")
            if t.strip()]


def search(term: str, since: datetime, max_pages: int = 5) -> list[GupyJob]:
    """Vagas com `term` no título publicadas desde `since` (datetime com fuso)."""
    jobs = []
    for page in range(max_pages):
        data = _get({"jobName": term, "limit": PAGE_SIZE, "offset": page * PAGE_SIZE,
                     "sortBy": "publishedDate", "sortOrder": "desc"})
        items = data.get("data") or []
        for it in items:
            published = datetime.fromisoformat(it["publishedDate"].replace("Z", "+00:00"))
            if published < since:
                return jobs  # daqui para frente, só mais antigas
            place = ", ".join(x for x in (it.get("city"), it.get("state")) if x) or None
            jobs.append(GupyJob(
                id=it["id"], title=(it.get("name") or "").strip(),
                company=it.get("careerPageName"), location=place,
                workplace=WORKPLACE.get(it.get("workplaceType") or ""),
                contract=CONTRACT.get(it.get("type") or ""),
                internship=it.get("type") in INTERNSHIP,
                description=html_to_text(it.get("description") or "") or None,
                published=published.isoformat(timespec="seconds"),
                url=(it.get("jobUrl") or "").split("?")[0],
            ))
        if len(items) < PAGE_SIZE:
            break
        time.sleep(1)
    return jobs
