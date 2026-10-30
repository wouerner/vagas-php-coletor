"""Vagas do portal da Sólides (vagas.solides.com.br), pela mesma API JSON que o site usa,
sem login. A busca por termo olha título e descrição, e os resultados vêm do mais recente
para o mais antigo (só a data, sem hora): a paginação para ao passar do início da janela."""

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date

from .public_jobs import USER_AGENT, html_to_text

API = "https://vagas.solides.com.br/api/vacancies"
PAGE_SIZE = 20  # a API recusa páginas maiores
DEFAULT_TERMS = "php,laravel,symfony,codeigniter,wordpress,magento,drupal"

WORKPLACE = {"remoto": "Remoto", "hibrido": "Híbrido", "presencial": "Presencial"}


@dataclass
class SolidesJob:
    id: int
    title: str
    company: str | None
    location: str | None
    workplace: str | None
    contract: str | None
    seniority: str | None
    salary: str | None
    description: str | None
    published: str          # data (AAAA-MM-DD, Brasília)
    url: str


def _get(params: dict) -> dict:
    req = urllib.request.Request(f"{API}?{urllib.parse.urlencode(params)}", headers={
        "User-Agent": USER_AGENT, "Accept": "application/json",
        "Referer": "https://vagas.solides.com.br/"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and attempt < 2:
                time.sleep(5 * (attempt + 1))
                continue
            raise RuntimeError(f"Sólides respondeu HTTP {e.code}") from e
        if data.get("error"):
            raise RuntimeError(f"Sólides: {data['error']}")
        return data
    raise RuntimeError("Sem resposta da Sólides")


def terms() -> list[str]:
    return [t.strip() for t in (os.getenv("VAGAS_SOLIDES_TERMS") or DEFAULT_TERMS).split(",")
            if t.strip()]


def _contract(types: list[dict]) -> str | None:
    names = " ".join(t.get("name") or "" for t in types).lower()
    for key, label in (("clt", "CLT"), ("efetiv", "CLT"), ("pj", "PJ"),
                       ("freela", "Freelance"), ("autônom", "Freelance")):
        if key in names:
            return label
    return None


def _salary(s: dict | None) -> str | None:
    if not s or not s.get("showRangeToApplicant"):
        return None
    low, high = s.get("initialRange") or 0, s.get("finalRange") or 0
    fmt = lambda v: f"R$ {v:,.0f}".replace(",", ".")  # noqa: E731
    if low and high and high != low:
        return f"{fmt(low)} a {fmt(high)}"
    return fmt(high or low) if (high or low) else None


def search(term: str, since: date, max_pages: int = 10) -> list[SolidesJob]:
    """Vagas com `term` publicadas desde o dia `since` (data de Brasília)."""
    jobs = []
    for page in range(1, max_pages + 1):
        data = _get({"page": page, "take": PAGE_SIZE, "title": term})
        items = data.get("data") or []
        for it in items:
            published = it.get("createdAt") or ""
            if published[:10] < since.isoformat():
                return jobs  # daqui para frente, só mais antigas
            city, state = (it.get("city") or {}).get("name"), (it.get("state") or {}).get("code")
            workplace = "Remoto" if it.get("homeOffice") else WORKPLACE.get(it.get("jobType") or "")
            seniority = ", ".join(s.get("name") or "" for s in it.get("seniority") or []) or None
            jobs.append(SolidesJob(
                id=it["id"], title=(it.get("title") or "").strip(),
                company=it.get("companyName"),
                location=" - ".join(x for x in (city, state) if x) or None,
                workplace=workplace, contract=_contract(it.get("recruitmentContractType") or []),
                seniority=seniority, salary=_salary(it.get("salary")),
                description=html_to_text(it.get("description") or "") or None,
                published=published[:10],
                url=f"https://{it.get('slug') or 'solides'}.vagas.solides.com.br/vaga/{it['id']}",
            ))
        if page >= (data.get("totalPages") or 1) or len(items) < PAGE_SIZE:
            break
        time.sleep(1)
    return jobs
